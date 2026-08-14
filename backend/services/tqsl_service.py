import ctypes
import ctypes.util
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


class TQSLUnavailable(RuntimeError):
    """Raised when TrustedQSL cannot perform the requested operation."""


class TQSLService:
    DEFAULT_LOCATIONS = (
        Path("TrustedQSL") / "tqsl.exe",
        Path("TrustedQSL") / "tqsl",
    )

    class _Date(ctypes.Structure):
        _fields_ = [("year", ctypes.c_int), ("month", ctypes.c_int), ("day", ctypes.c_int)]

    def __init__(self, runner=None):
        self.runner = runner or subprocess.run

    def _version(self, executable):
        try:
            result = self.runner(
                [str(executable), "-v"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        output = "\n".join(
            value for value in (getattr(result, "stdout", ""), getattr(result, "stderr", "")) if value
        )
        match = re.search(r"\b\d+(?:\.\d+){1,3}\b", output)
        return match.group(0) if match else None

    @staticmethod
    def _candidate_paths(search_drives=None):
        candidates = []
        for variable in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
            value = os.environ.get(variable)
            if value:
                base = Path(value)
                candidates.extend(base / location for location in TQSLService.DEFAULT_LOCATIONS)

        for name in ("tqsl", "tqsl.exe"):
            found = shutil.which(name)
            if found:
                candidates.append(Path(found))

        if search_drives:
            for drive in search_drives:
                if not isinstance(drive, str) or not drive.strip():
                    continue
                root = Path(drive).expanduser()
                for prefix in (Path(), Path("Program Files"), Path("Program Files (x86)")):
                    candidates.extend(root / prefix / location for location in TQSLService.DEFAULT_LOCATIONS)

        seen = set()
        for candidate in candidates:
            key = os.path.normcase(str(candidate))
            if key not in seen:
                seen.add(key)
                yield candidate

    def find_tqsl(self, search_drives=None):
        for candidate in self._candidate_paths(search_drives):
            if candidate.is_file():
                return {"tqsl_path": str(candidate), "version": self._version(candidate)}
        raise TQSLUnavailable("未找到 TQSL")

    def _resolve_path(self, tqsl_path=None):
        if tqsl_path:
            candidate = Path(tqsl_path).expanduser()
            if candidate.is_file():
                return candidate
            raise TQSLUnavailable("TQSL 路径不存在")
        return Path(self.find_tqsl()["tqsl_path"])

    @staticmethod
    def _decode(buffer):
        return buffer.value.decode("utf-8", errors="replace")

    def _load_library(self, executable):
        directory = Path(executable).parent
        candidates = [
            directory / "tqsllib2.dll",
            directory / "libtqsllib.so",
            directory / "libtqsllib.dylib",
        ]
        discovered = ctypes.util.find_library("tqsllib2") or ctypes.util.find_library("tqsllib")
        if discovered:
            candidates.append(discovered)
        errors = []
        for candidate in candidates:
            if isinstance(candidate, Path) and not candidate.is_file():
                continue
            try:
                if os.name == "nt":
                    if hasattr(os, "add_dll_directory"):
                        with os.add_dll_directory(str(directory)):
                            return ctypes.WinDLL(str(candidate))
                    return ctypes.WinDLL(str(candidate))
                return ctypes.CDLL(str(candidate))
            except OSError as exc:
                errors.append(str(exc))
        detail = f": {'; '.join(errors)}" if errors else ""
        raise TQSLUnavailable(f"无法加载 TQSL 证书库{detail}")

    def _configure_library(self, library):
        functions = {
            "tqsl_init": ([], ctypes.c_int),
            "tqsl_getErrorString": ([], ctypes.c_char_p),
            "tqsl_initStationLocationCapture": ([ctypes.POINTER(ctypes.c_void_p)], ctypes.c_int),
            "tqsl_endStationLocationCapture": ([ctypes.POINTER(ctypes.c_void_p)], ctypes.c_int),
            "tqsl_getNumStationLocations": ([ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)], ctypes.c_int),
            "tqsl_getStationLocationName": ([ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int], ctypes.c_int),
            "tqsl_getStationLocationCallSign": ([ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int], ctypes.c_int),
            "tqsl_selectCertificates": (
                [
                    ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)),
                    ctypes.POINTER(ctypes.c_int),
                    ctypes.c_char_p,
                    ctypes.c_int,
                    ctypes.POINTER(self._Date),
                    ctypes.c_void_p,
                    ctypes.c_int,
                ],
                ctypes.c_int,
            ),
            "tqsl_getCertificateCallSign": ([ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int], ctypes.c_int),
            "tqsl_getCertificateNotAfterDate": ([ctypes.c_void_p, ctypes.POINTER(self._Date)], ctypes.c_int),
            "tqsl_freeCertificateList": ([ctypes.POINTER(ctypes.c_void_p), ctypes.c_int], None),
        }
        try:
            for name, (argtypes, restype) in functions.items():
                function = getattr(library, name)
                function.argtypes = argtypes
                function.restype = restype
        except AttributeError as exc:
            raise TQSLUnavailable(f"TQSL 证书库缺少函数: {exc}") from exc
        return library

    @staticmethod
    def _library_error(library):
        try:
            library.tqsl_getErrorString.restype = ctypes.c_char_p
            value = library.tqsl_getErrorString()
            return value.decode("utf-8", errors="replace") if value else "TQSL 操作失败"
        except (AttributeError, ValueError):
            return "TQSL 操作失败"

    def _station_locations(self, library):
        location = ctypes.c_void_p()
        locations = {}
        try:
            if library.tqsl_initStationLocationCapture(ctypes.byref(location)) != 0:
                return locations
            count = ctypes.c_int()
            if library.tqsl_getNumStationLocations(location, ctypes.byref(count)) != 0:
                return locations
            for index in range(count.value):
                name = ctypes.create_string_buffer(512)
                callsign = ctypes.create_string_buffer(64)
                if library.tqsl_getStationLocationName(location, index, name, len(name)) != 0:
                    continue
                if library.tqsl_getStationLocationCallSign(location, index, callsign, len(callsign)) != 0:
                    continue
                locations.setdefault(self._decode(callsign).upper(), []).append(self._decode(name))
        finally:
            if location.value:
                library.tqsl_endStationLocationCapture(ctypes.byref(location))
        return locations

    def list_certificates(self, tqsl_path=None):
        executable = self._resolve_path(tqsl_path)
        library = self._configure_library(self._load_library(executable))
        cert_list = ctypes.POINTER(ctypes.c_void_p)()
        cert_count = ctypes.c_int()
        try:
            if library.tqsl_init() != 0:
                raise TQSLUnavailable(self._library_error(library))
            flags = 1 | 2 | 4
            result = library.tqsl_selectCertificates(
                ctypes.byref(cert_list), ctypes.byref(cert_count), None, 0, None, None, flags
            )
            if result != 0:
                raise TQSLUnavailable(self._library_error(library))
            locations = self._station_locations(library)
            certs = []
            for index in range(cert_count.value):
                certificate = cert_list[index]
                callsign = ctypes.create_string_buffer(64)
                expires = self._Date()
                if library.tqsl_getCertificateCallSign(certificate, callsign, len(callsign)) != 0:
                    continue
                call = self._decode(callsign)
                expire = None
                if library.tqsl_getCertificateNotAfterDate(certificate, ctypes.byref(expires)) == 0:
                    expire = f"{expires.year:04d}-{expires.month:02d}-{expires.day:02d}"
                stations = locations.get(call.upper()) or [""]
                certs.extend(
                    {"callsign": call, "station": station, "expire": expire}
                    for station in stations
                )
            return {"certs": certs}
        except (AttributeError, OSError, ValueError) as exc:
            raise TQSLUnavailable(f"TQSL 证书查询失败: {exc}") from exc
        finally:
            if cert_list:
                try:
                    library.tqsl_freeCertificateList(cert_list, cert_count.value)
                except (AttributeError, OSError, ValueError):
                    pass

    def sign_adif(self, adif_data, tqsl_path=None, station_location=None, duplicate_strategy="skip"):
        executable = self._resolve_path(tqsl_path)
        with tempfile.TemporaryDirectory(prefix="hamlog-tqsl-") as directory:
            input_path = Path(directory) / "upload.adi"
            output_path = Path(directory) / "upload.tq8"
            input_path.write_bytes(adif_data)
            actions = {"skip": "compliant", "replace": "all", "ask": "ask"}
            if duplicate_strategy not in actions:
                raise ValueError("duplicate_strategy 非法")
            command = [str(executable), "-q", "-d", "-a", actions[duplicate_strategy]]
            if station_location:
                command.extend(["-l", station_location])
            command.extend(["-o", str(output_path), str(input_path)])
            try:
                result = self.runner(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise TQSLUnavailable(f"TQSL 签名失败: {exc}") from exc
            if getattr(result, "returncode", 1) not in {0, 9} or not output_path.is_file():
                message = getattr(result, "stderr", "").strip() or "TQSL 未生成签名文件"
                raise TQSLUnavailable(message)
            return output_path.read_bytes()
