"""
QRZ.com 网页爬虫 —— 考虑反爬措施的完整实现

实测反爬机制(2026-08 通过 curl 探测):
  1. UA 校验:无浏览器 UA → 302 跳转到 index.html
  2. HEAD 方法禁用:返回 405 Method Not Allowed,只能用 GET
  3. 登录表单带 nojs token:必须先 GET 登录页提取该 token 才能登录
  4. 登录墙:Email / 详细地址 / Name 等字段需登录后可见
  5. Biography 通过 iframe + Base64 内嵌 JS 加载,非独立请求
  6. 隐式频率限制:需限速,建议 ≥3s/次

用法:
    python qrz_scraper.py --callsign W1AW
    python qrz_scraper.py --callsign W1AW --username USER --password PASS
    python qrz_scraper.py --callsigns W1AW,K1AAA,N1BCD --username USER --password PASS --output out.json
"""

import argparse
import base64
import csv
import json
import random
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# 必须带真实浏览器 UA,否则被 302 拦截
DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

LOGIN_URL = "https://www.qrz.com/login"
DB_URL = "https://www.qrz.com/db/{call}"


class QRZScraper:
    def __init__(self, username=None, password=None, delay=(3.0, 6.0)):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": DEFAULT_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.qrz.com/",
            }
        )
        self.username = username
        self.password = password
        self.delay = delay  # 随机延迟区间,规避频控
        self.logged_in = False

    def _sleep(self):
        time.sleep(random.uniform(*self.delay))

    # ---------- 登录 ----------
    def login(self):
        """登录 QRZ。需先 GET 登录页提取 nojs token。"""
        if not (self.username and self.password):
            print("[!] 未提供账号密码,将以游客模式运行(详细字段不可见)")
            return False

        r = self.session.get(LOGIN_URL, timeout=20)
        if r.status_code != 200:
            raise RuntimeError(f"获取登录页失败: {r.status_code}")

        # 提取 nojs 隐藏字段(每次会变)
        soup = BeautifulSoup(r.text, "lxml")
        nojs = soup.find("input", {"name": "nojs"})
        if not nojs:
            raise RuntimeError("未找到 nojs token,页面结构可能已变化")
        nojs_val = nojs.get("value", "")

        data = {
            "nojs": nojs_val,
            "login_ref": "",
            "username": self.username,
            "password": self.password,
            "2fcode": "",          # 若开启两步验证需填入
            "trustdevice": "yes",  # 信任本设备,减少后续验证
            "target": "/",
            "flush": "1",
        }
        r = self.session.post(LOGIN_URL, data=data, timeout=20, allow_redirects=True)
        self.logged_in = "logout" in r.text.lower() or "logout" in r.url.lower()
        if self.logged_in:
            print(f"[+] 登录成功: {self.username}")
        else:
            print("[-] 登录失败,请检查账号密码/是否需要 2FA")
        self._sleep()
        return self.logged_in

    # ---------- 查询呼号 ----------
    def lookup(self, callsign):
        """抓取单个呼号详情页并解析字段。"""
        url = DB_URL.format(call=callsign.upper())
        r = self.session.get(url, timeout=20)

        if r.status_code == 302 or "index.html" in r.url:
            # 命中 UA 校验/被重定向
            raise RuntimeError(
                f"被重定向到 {r.url},通常是 UA 被拦截或触发反爬"
            )
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} for {url}")

        return self._parse(r.text, callsign)

    def _parse(self, html, callsign):
        soup = BeautifulSoup(html, "lxml")
        result = {"callsign": callsign.upper()}

        # 主体数据在 id=calldata 的容器里
        body = soup.select_one("#calldata") or soup.select_one("#csbody")
        text = body.get_text(" ", strip=True) if body else ""

        # 国家:页面里 "W1AW USA" 这样紧挨着
        m = re.search(rf"{callsign}\s+([A-Z][A-Z\s]{1,30})", text)
        if m:
            result["country"] = m.group(1).strip()

        # QSL 信息
        qsl = re.search(r"QSL[:：]\s*(.{5,200}?)(?=Email|Page|Lookups|$)", text)
        if qsl:
            result["qsl"] = qsl.group(1).strip()

        # 页面管理员
        mgr = re.search(r"Page managed by\s+([A-Z0-9]+)", text)
        if mgr:
            result["page_manager"] = mgr.group(1)

        # 查询次数
        lookups = re.search(r"Lookups[:：]\s*([\d,]+)", text)
        if lookups:
            result["lookups"] = lookups.group(1)

        # 登录后可见字段:Email / 地址等。游客模式页面会显示 "Login required"
        email_match = re.search(r"Email[:：]\s*([^\s]+@[^\s]+)", text)
        if email_match:
            result["email"] = email_match.group(1)
        elif "Login required to view" in text:
            result["email"] = None  # 需登录

        # 地址块(登录后通常在特定结构里,这里做兜底正则)
        addr = re.search(
            r"(?:Address|Addr)[:：]\s*(.{5,120}?)(?=Email|Grid|County|Page|$)",
            text,
            re.I,
        )
        if addr:
            result["address"] = addr.group(1).strip()

        # Grid / County / Class / Expires —— 登录后才有,这里尝试抓取
        for key, pattern in [
            ("grid", r"Grid[:：]\s*([A-Z]{2}\d{2}[a-z]{2})"),
            ("county", r"County[:：]\s*(.{2,40}?)(?=Grid|Class|Expires|Page|$)"),
            ("license_class", r"Class[:：]\s*(Technician|General|Extra|Advanced|Novice|Club)"),
            ("expires", r"Expires[:：]\s*(\d{4}-\d{2}-\d{2})"),
        ]:
            m = re.search(pattern, text, re.I)
            if m:
                result[key] = m.group(1).strip()

        # Biography:内嵌在 JS 的 Base64.decode("...") 里
        result["bio"] = self._extract_bio(html)

        result["logged_in"] = self.logged_in
        return result

    def _extract_bio(self, html):
        """Biography 通过 iframe + JS Base64 内嵌加载,从 HTML 里直接提取。"""
        # 匹配 Base64.decode("....")
        m = re.search(r'Base64\.decode\("([A-Za-z0-9+/=]+)"\)', html)
        if not m:
            return None
        try:
            raw = base64.b64decode(m.group(1)).decode("utf-8", errors="ignore")
            # 去掉 HTML 标签得到纯文本
            return BeautifulSoup(raw, "lxml").get_text("\n", strip=True)
        except Exception as e:
            return f"<bio decode error: {e}>"

    # ---------- 批量 ----------
    def lookup_many(self, callsigns, output=None, fmt="json"):
        results = []
        for i, call in enumerate(callsigns, 1):
            call = call.strip()
            if not call:
                continue
            print(f"[{i}/{len(callsigns)}] 查询 {call} ...")
            try:
                res = self.lookup(call)
                results.append(res)
                print(f"    -> {res.get('country', '?')} | lookups={res.get('lookups', '?')}")
            except Exception as e:
                print(f"    [x] 失败: {e}")
                results.append({"callsign": call, "error": str(e)})
            self._sleep()

        if output:
            self._save(results, output, fmt)
        return results

    @staticmethod
    def _save(results, output, fmt):
        path = Path(output)
        if fmt == "json":
            path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        elif fmt == "csv":
            keys = sorted({k for r in results for k in r})
            with path.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=keys)
                w.writeheader()
                for r in results:
                    w.writerow(r)
        print(f"[+] 已保存 {len(results)} 条到 {path}")


def main():
    ap = argparse.ArgumentParser(description="QRZ.com 呼号爬虫")
    ap.add_argument("--callsign", help="单个呼号")
    ap.add_argument("--callsigns", help="逗号分隔的多个呼号")
    ap.add_argument("--username", help="QRZ 用户名(可选,登录后可见更多字段)")
    ap.add_argument("--password", help="QRZ 密码")
    ap.add_argument("--output", "-o", help="输出文件路径")
    ap.add_argument("--format", default="json", choices=["json", "csv"])
    args = ap.parse_args()

    if not args.callsign and not args.callsigns:
        ap.error("至少指定 --callsign 或 --callsigns")

    scraper = QRZScraper(args.username, args.password)
    if args.username:
        scraper.login()

    if args.callsign:
        res = scraper.lookup(args.callsign)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        if args.output:
            scraper._save([res], args.output, args.format)
    else:
        calls = [c.strip() for c in args.callsigns.split(",") if c.strip()]
        scraper.lookup_many(calls, args.output, args.format)


if __name__ == "__main__":
    main()
