"""QRZ.com client with optional authenticated lookup and injectable HTTP session."""

import base64
import random
import re
import time

import requests
from bs4 import BeautifulSoup


DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
LOGIN_URL = "https://www.qrz.com/login"
DB_URL = "https://www.qrz.com/db/{callsign}"


class QRZError(RuntimeError):
    pass


class QRZAuthenticationError(QRZError):
    pass


class QRZNotFoundError(QRZError):
    pass


class QRZClient:
    def __init__(self, username=None, password=None, session=None, delay=(3.0, 6.0), proxies=None, timeout=20):
        self.username = username
        self.password = password
        self.session = session or requests.Session()
        self.delay = delay
        self.proxies = proxies
        self.timeout = timeout
        self.logged_in = False
        self.session.headers.update({
            "User-Agent": DEFAULT_UA,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.qrz.com/",
        })

    def _request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", self.timeout)
        if self.proxies:
            kwargs.setdefault("proxies", self.proxies)
        try:
            return self.session.request(method, url, **kwargs)
        except requests.RequestException as exc:
            raise QRZError(f"QRZ 网络请求失败: {exc}") from exc

    def _sleep(self):
        if self.delay and max(self.delay) > 0:
            time.sleep(random.uniform(*self.delay))

    def login(self):
        if not self.username or not self.password:
            raise QRZAuthenticationError("未配置 QRZ 凭据")
        response = self._request("GET", LOGIN_URL)
        if response.status_code != 200:
            raise QRZAuthenticationError(f"获取 QRZ 登录页失败: HTTP {response.status_code}")
        token = BeautifulSoup(response.text, "lxml").find("input", {"name": "nojs"})
        if not token or not token.get("value"):
            raise QRZAuthenticationError("QRZ 登录页缺少 nojs token")
        response = self._request(
            "POST",
            LOGIN_URL,
            data={
                "nojs": token["value"],
                "login_ref": "",
                "username": self.username,
                "password": self.password,
                "2fcode": "",
                "trustdevice": "yes",
                "target": "/",
                "flush": "1",
            },
            allow_redirects=True,
        )
        self.logged_in = "logout" in response.text.lower() or "logout" in response.url.lower()
        if not self.logged_in:
            raise QRZAuthenticationError("QRZ 登录失败，请检查账号、密码或两步验证")
        self._sleep()
        return True

    def lookup(self, callsign, login=False):
        callsign = str(callsign).strip().upper()
        if not callsign:
            raise ValueError("callsign 不能为空")
        if len(callsign) > 20 or not re.fullmatch(r"[A-Z0-9]+(?:/[A-Z0-9]+)*", callsign):
            raise ValueError("callsign 格式非法")
        if login and not self.logged_in:
            self.login()
        response = self._request("GET", DB_URL.format(callsign=callsign), allow_redirects=False)
        location = response.headers.get("Location", "")
        if response.status_code in {301, 302, 303, 307, 308}:
            raise QRZError(f"QRZ 将请求重定向到 {location or '未知地址'}，可能触发了访问限制")
        if response.status_code == 404:
            raise QRZNotFoundError("呼号不存在")
        if response.status_code != 200:
            raise QRZError(f"QRZ 返回 HTTP {response.status_code}")
        result = self.parse(response.text, callsign)
        result.update({
            "callsign": callsign,
            "url": DB_URL.format(callsign=callsign),
            "found": True,
            "logged_in": self.logged_in,
        })
        self._sleep()
        return result

    @staticmethod
    def parse(html, callsign):
        soup = BeautifulSoup(html, "lxml")
        body = soup.select_one("#calldata") or soup.select_one("#csbody")
        text = body.get_text(" ", strip=True) if body else ""
        if not body or "callsign not found" in text.lower() or "not found in our database" in text.lower():
            raise QRZNotFoundError("呼号不存在")
        result = {
            "country": None,
            "qsl_info": None,
            "name": None,
            "qth": None,
            "grid": None,
            "email": None,
            "license_class": None,
            "previous_call": None,
            "lotw": bool(re.search(r"\bLoTW\b", text, re.IGNORECASE)),
            "eqsl": bool(re.search(r"\beQSL\b", text, re.IGNORECASE)),
        }
        country = re.search(
            rf"\b{re.escape(callsign)}\s+([A-Z][A-Z\s]{{1,40}}?)(?=\s+(?:QSL|Email|Page|Lookups|Grid|Class)[:：]|$)",
            text,
            re.IGNORECASE,
        )
        qsl = re.search(r"QSL[:：]\s*(.{1,200}?)(?=Email|Page|Lookups|$)", text, re.IGNORECASE)
        email = re.search(r"Email[:：]\s*([^\s]+@[^\s]+)", text, re.IGNORECASE)
        grid = re.search(r"Grid[:：]\s*([A-R]{2}\d{2}[A-Xa-x]{0,2})", text)
        license_class = re.search(r"Class[:：]\s*([A-Za-z]+)", text, re.IGNORECASE)
        if country:
            result["country"] = country.group(1).strip()
        if qsl:
            result["qsl_info"] = qsl.group(1).strip()
        if email:
            result["email"] = email.group(1)
        if grid:
            result["grid"] = grid.group(1)
        if license_class:
            result["license_class"] = license_class.group(1)
        bio = re.search(r'Base64\.decode\(["\']([A-Za-z0-9+/=]+)["\']\)', html)
        result["bio"] = None
        if bio:
            try:
                decoded = base64.b64decode(bio.group(1)).decode("utf-8", errors="replace")
                result["bio"] = BeautifulSoup(decoded, "lxml").get_text("\n", strip=True)
            except (ValueError, TypeError):
                pass
        image = soup.select_one("#calldata img[src], #csbody img[src]")
        result["image_url"] = image.get("src") if image else None
        result["has_biography"] = bool(result["bio"])
        result["has_detail"] = any(result.get(key) for key in ("email", "grid", "license_class", "qth", "name"))
        return result
