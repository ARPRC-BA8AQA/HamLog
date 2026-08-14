import platform
import hashlib
import re
import subprocess
import inspect
from pathlib import Path
from threading import Thread
from urllib.parse import urlparse

try:
    import requests
except ImportError:  # pragma: no cover - exercised on minimal installations
    requests = None


class UpdateUnavailable(RuntimeError):
    """Raised when update metadata or an update package is unavailable."""


class UpdateService:
    DEFAULT_CHECK_URL = "https://api.github.com/repos/ARPRC-BA8AQA/HamLog/releases/latest"

    def __init__(self, http_get=None, launcher=None):
        self.http_get = http_get
        self.launcher = launcher or subprocess.Popen

    def available(self):
        return self.http_get is not None or requests is not None

    def _get(self, url, **kwargs):
        if not self.available():
            raise UpdateUnavailable("更新网络依赖不可用")
        try:
            return (self.http_get or requests.get)(url, **kwargs)
        except Exception as exc:
            raise UpdateUnavailable(f"更新服务器不可达: {exc}") from exc

    @staticmethod
    def _version_tuple(value):
        match = re.search(r"\d+(?:\.\d+)*", str(value))
        return tuple(int(part) for part in match.group(0).split(".")) if match else None

    def check(self, current_version, check_url=None, timeout=10):
        if not isinstance(current_version, str) or not current_version.strip():
            raise ValueError("current_version 不能为空")
        response = self._get(check_url or self.DEFAULT_CHECK_URL, timeout=float(timeout))
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code < 200 or status_code >= 300:
            raise UpdateUnavailable(f"更新服务器返回 HTTP {status_code}")
        try:
            payload = response.json()
        except (ValueError, AttributeError) as exc:
            raise UpdateUnavailable("更新信息格式无效") from exc
        if not isinstance(payload, dict):
            raise UpdateUnavailable("更新信息格式无效")
        latest = payload.get("latest_version") or payload.get("tag_name") or payload.get("version")
        if not isinstance(latest, str) or not latest.strip():
            raise UpdateUnavailable("更新信息缺少版本号")
        current = current_version.strip()
        latest_numbers = self._version_tuple(latest)
        current_numbers = self._version_tuple(current)
        has_update = latest != current
        if latest_numbers and current_numbers:
            width = max(len(latest_numbers), len(current_numbers))
            has_update = latest_numbers + (0,) * (width - len(latest_numbers)) > current_numbers + (0,) * (width - len(current_numbers))
        assets = payload.get("assets") if isinstance(payload.get("assets"), list) else []
        exe_url = payload.get("exe_url")
        if not exe_url:
            for asset in assets:
                if isinstance(asset, dict) and str(asset.get("name", "")).lower().endswith(".exe"):
                    exe_url = asset.get("browser_download_url") or asset.get("url")
                    break
        return {
            "has_update": has_update,
            "latest_version": latest,
            "force_update": bool(payload.get("force_update", False)),
            "changelog": payload.get("changelog") or payload.get("body") or "",
            "exe_url": exe_url,
            "sha256": payload.get("sha256") or next((asset.get("sha256") or asset.get("digest", "").removeprefix("sha256:") for asset in assets if isinstance(asset, dict) and (asset.get("browser_download_url") or asset.get("url")) == exe_url), None),
        }

    @staticmethod
    def validate_download_url(exe_url):
        parsed = urlparse(str(exe_url))
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("exe_url 必须是 HTTP/HTTPS 地址")

    def download(self, exe_url, destination, progress, expected_sha256=None):
        self.validate_download_url(exe_url)
        if expected_sha256 is not None and not re.fullmatch(r"[0-9a-fA-F]{64}", str(expected_sha256)):
            raise ValueError("sha256 必须是 64 位十六进制字符串")
        response = self._get(exe_url, stream=True, timeout=60)
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code < 200 or status_code >= 300:
            raise UpdateUnavailable(f"更新下载失败: HTTP {status_code}")
        total = int(getattr(response, "headers", {}).get("content-length", 0) or 0)
        received = 0
        digest = hashlib.sha256()
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            with destination.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 64):
                    if not chunk:
                        continue
                    output.write(chunk)
                    digest.update(chunk)
                    received += len(chunk)
                    percent = min(int(received * 100 / total), 100) if total else 0
                    progress(percent, 0)
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise UpdateUnavailable(f"更新下载失败: {exc}") from exc
        finally:
            close = getattr(response, "close", None)
            if close:
                close()
        actual = digest.hexdigest()
        if expected_sha256 and actual.casefold() != str(expected_sha256).casefold():
            destination.unlink(missing_ok=True)
            raise UpdateUnavailable("更新安装包 SHA-256 校验失败")
        progress(100, 0)
        return destination

    def install(self, package_path):
        if platform.system() != "Windows":
            raise UpdateUnavailable("当前平台不支持安装 Windows 更新包")
        package_path = Path(package_path)
        if not package_path.is_file():
            raise UpdateUnavailable("更新安装包不存在")
        try:
            self.launcher([str(package_path)])
        except (OSError, subprocess.SubprocessError) as exc:
            raise UpdateUnavailable(f"启动更新安装包失败: {exc}") from exc


def start_download(service, exe_url, destination, task, expected_sha256=None):
    def worker():
        task.update({"status": "downloading", "error": None})
        try:
            progress = lambda percent, speed: task.update(
                {"status": "downloading", "percent": percent, "speed_kbps": speed}
            )
            parameters = inspect.signature(service.download).parameters
            if "expected_sha256" in parameters:
                service.download(exe_url, destination, progress, expected_sha256=expected_sha256)
            else:
                service.download(exe_url, destination, progress)
        except Exception as exc:
            task.update({"status": "error", "error": str(exc)})
        else:
            task.update({"status": "done", "percent": 100, "speed_kbps": 0, "error": None})

    thread = Thread(target=worker, name="hamlog-update-download", daemon=True)
    thread.start()
    return thread
