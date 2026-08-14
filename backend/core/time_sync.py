import datetime as _datetime
import ctypes
import platform
import shutil
import subprocess

try:
    import ntplib
except ImportError:  # pragma: no cover - exercised when optional dependency is absent
    ntplib = None


class TimeSyncUnavailable(RuntimeError):
    """Raised when NTP or system clock synchronization is unavailable."""


class TimeSyncService:
    DEFAULT_SERVERS = ("ntp.ntsc.ac.cn", "pool.ntp.org")

    def __init__(self, ntp_client=None, command_runner=None, system_name=None):
        self.ntp_client = ntp_client
        self.command_runner = command_runner or subprocess.run
        self.system_name = system_name or platform.system()

    def _client(self):
        if self.ntp_client is not None:
            return self.ntp_client
        if ntplib is None:
            raise TimeSyncUnavailable("ntplib 依赖不可用")
        return ntplib.NTPClient()

    def _query(self, servers, timeout):
        client = self._client()
        failures = []
        for server in servers:
            try:
                response = client.request(server, version=3, timeout=float(timeout))
                return server, float(response.offset) * 1000
            except Exception as exc:
                failures.append(f"{server}: {exc}")
        detail = "; ".join(failures) or "没有可用的 NTP 服务器"
        raise TimeSyncUnavailable(f"NTP 不可达: {detail}")

    def _run(self, command):
        try:
            result = self.command_runner(
                command,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise TimeSyncUnavailable(f"系统授时命令不可用: {exc}") from exc
        if getattr(result, "returncode", 1) != 0:
            message = getattr(result, "stderr", "").strip() or "系统授时失败"
            raise TimeSyncUnavailable(message)
        return result

    def _apply_clock(self, offset_ms, auto_elevate):
        if abs(offset_ms) < 1:
            return True
        if self.system_name == "Windows":
            if not auto_elevate:
                raise TimeSyncUnavailable("授时需要管理员权限")
            try:
                is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
            except (AttributeError, OSError):
                is_admin = False
            if is_admin:
                self._run(["w32tm", "/resync"])
            else:
                powershell = shutil.which("powershell") or shutil.which("pwsh")
                if not powershell:
                    raise TimeSyncUnavailable("无法启动 Windows 管理员提权")
                self._run(
                    [
                        powershell,
                        "-NoProfile",
                        "-Command",
                        "Start-Process w32tm -ArgumentList '/resync' -Verb RunAs -Wait",
                    ]
                )
            return True
        if self.system_name == "Linux":
            if not shutil.which("date"):
                raise TimeSyncUnavailable("系统授时命令不可用")
            target = _datetime.datetime.now(_datetime.timezone.utc) + _datetime.timedelta(milliseconds=offset_ms)
            self._run(["date", "-u", "-s", target.strftime("%Y-%m-%d %H:%M:%S")])
            return True
        raise TimeSyncUnavailable("当前平台不支持系统授时")

    def sync(self, servers=None, timeout=2, auto_elevate=True):
        if not isinstance(servers, (list, tuple)) or not servers:
            raise ValueError("servers 必须是非空数组")
        servers = [server.strip() for server in servers if isinstance(server, str) and server.strip()]
        if not servers:
            raise ValueError("servers 必须是非空数组")
        server, offset_ms = self._query(servers[:10], timeout)
        elevated = self._apply_clock(offset_ms, bool(auto_elevate))
        return {
            "offset_ms": round(offset_ms),
            "synced": True,
            "server": server,
            "elevated": elevated,
        }
