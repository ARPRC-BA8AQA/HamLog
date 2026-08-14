import re

try:
    import requests
except ImportError:  # pragma: no cover - exercised on minimal installations
    requests = None


class LoTWUnavailable(RuntimeError):
    """Raised when the LoTW network dependency cannot be used."""


class LoTWService:
    DEFAULT_UPLOAD_URL = "https://lotw.arrl.org/lotw/upload"

    def __init__(self, http_post=None):
        self.http_post = http_post

    def available(self):
        return self.http_post is not None or requests is not None

    def upload(self, tq8_data, upload_url=None, timeout=60):
        if not self.available():
            raise LoTWUnavailable("LoTW 网络依赖不可用")
        post = self.http_post or requests.post
        try:
            response = post(
                upload_url or self.DEFAULT_UPLOAD_URL,
                files={"upfile": ("hamlog.tq8", tq8_data, "application/octet-stream")},
                timeout=float(timeout),
            )
        except Exception as exc:
            raise LoTWUnavailable(f"LoTW 上传失败: {exc}") from exc
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code < 200 or status_code >= 300:
            raise LoTWUnavailable(f"LoTW 上传失败: HTTP {status_code}")

        text = str(getattr(response, "text", ""))
        status = re.search(
            r"<!--\s*[^A-Za-z0-9]*UPL\b[^A-Za-z0-9]*([^-]+?)\s*-->",
            text,
            re.IGNORECASE,
        )
        message = re.search(
            r"<!--\s*[^A-Za-z0-9]*UPLMESSAGE\b[^A-Za-z0-9]*(.+?)\s*-->",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if not status:
            raise LoTWUnavailable("LoTW 返回了无法识别的上传结果")
        accepted = status.group(1).strip().lower() == "accepted"
        response_message = message.group(1).strip() if message else status.group(1).strip()
        return {
            "uploaded": None if accepted else 0,
            "duplicates": 0,
            "errors": [] if accepted else [response_message or "LoTW 拒绝了上传"],
            "message": response_message or ("上传完成" if accepted else "LoTW 拒绝了上传"),
        }
