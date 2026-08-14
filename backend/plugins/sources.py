"""Plugin source cache and archive installation helpers.

The API module deliberately contains only request validation and response
formatting. This module owns the on-disk/plugin-cache contract so it can be
tested without a Flask request.
"""

from __future__ import annotations

import hashlib
import io
import ipaddress
import json
import re
import shutil
import socket
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


OFFICIAL_SOURCE_ID = "official"
SOURCE_API_VERSION = "1"
PLUGIN_ID = re.compile(r"^[a-z][a-z0-9_-]{2,39}$")
SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")


class SourceError(Exception):
    def __init__(self, message, code=503, data=None):
        super().__init__(message)
        self.code = code
        self.data = data


class InstallError(SourceError):
    pass


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def valid_plugin_id(plugin_id):
    return isinstance(plugin_id, str) and bool(PLUGIN_ID.fullmatch(plugin_id))


def valid_version(version):
    return isinstance(version, str) and bool(SEMVER.fullmatch(version))


def version_key(version):
    """Return a semver-comparable tuple, or None for malformed cache data."""
    match = SEMVER.fullmatch(version or "")
    if not match:
        return None
    major, minor, patch, prerelease = match.groups()
    parts = []
    if prerelease:
        for part in prerelease.split("."):
            parts.append((0, int(part)) if part.isdigit() else (1, part))
    return (int(major), int(minor), int(patch), not bool(prerelease), parts)


def is_newer(latest, current):
    latest_key = version_key(latest)
    current_key = version_key(current)
    return bool(latest_key and current_key and latest_key > current_key)


def ensure_official_source(db):
    db.execute(
        """INSERT OR IGNORE INTO plugin_sources
           (id, name, url, source_type, enabled)
           VALUES (?, ?, ?, 'official', 1)""",
        (OFFICIAL_SOURCE_ID, "HamLog 官方插件源", OFFICIAL_SOURCE_ID),
    )
    db.commit()


def _url_error(exc):
    if isinstance(exc, HTTPError):
        return f"插件源 HTTP 错误: {exc.code}"
    return f"插件源不可用: {exc}"


def fetch_bytes(url, max_bytes, timeout=15):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SourceError("只允许 HTTP/HTTPS URL", 400)
    hostname = (parsed.hostname or "").casefold()
    if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(".localhost"):
        raise SourceError("禁止访问本机插件源地址", 400)
    try:
        address = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        address = None
    if address and (address.is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_reserved):
        raise SourceError("禁止访问内网插件源地址", 400)
    if not address:
        try:
            resolved = {ipaddress.ip_address(item[4][0]) for item in socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
        except (OSError, ValueError) as exc:
            raise SourceError(f"插件源域名无法解析: {exc}", 503) from exc
        if any(item.is_private or item.is_loopback or item.is_link_local or item.is_multicast or item.is_reserved for item in resolved):
            raise SourceError("插件源域名解析到内网地址", 400)
    try:
        with urlopen(
            Request(url, headers={"User-Agent": "HamLog-Plugin/1"}),
            timeout=max(1.0, min(float(timeout), 60.0)),
        ) as response:
            final_url = response.geturl()
            final_host = urlparse(final_url).hostname
            if final_host and final_host.casefold() != hostname:
                raise SourceError("插件源不允许跨域重定向", 400)
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > max_bytes:
                raise SourceError("下载内容超过大小限制", 400)
            chunks = []
            total = 0
            while True:
                chunk = response.read(min(64 * 1024, max_bytes - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise SourceError("下载内容超过大小限制", 400)
                chunks.append(chunk)
            return b"".join(chunks)
    except SourceError:
        raise
    except (HTTPError, URLError, OSError, TimeoutError, ValueError) as exc:
        raise SourceError(_url_error(exc), 503) from exc


def _configured_official_index(config):
    direct = config.get("PLUGIN_OFFICIAL_INDEX")
    if isinstance(direct, dict):
        return direct
    plugin_config = (config.get("HAMLOG_CONFIG") or {}).get("plugins", {})
    configured = plugin_config.get("official_index")
    if isinstance(configured, dict):
        return configured
    return None


def _official_url(config):
    direct = config.get("PLUGIN_OFFICIAL_URL")
    if isinstance(direct, str) and direct:
        return direct
    plugin_config = (config.get("HAMLOG_CONFIG") or {}).get("plugins", {})
    configured = plugin_config.get("official_url")
    return configured if isinstance(configured, str) and configured else None


def _source_index(source, config):
    if source["id"] == OFFICIAL_SOURCE_ID:
        configured_index = _configured_official_index(config)
        if configured_index is not None:
            return configured_index
        official_url = _official_url(config)
        if official_url:
            try:
                return json.loads(fetch_bytes(
                    official_url,
                    int(config.get("PLUGIN_MAX_INDEX_BYTES", 5 * 1024 * 1024)),
                    config.get("PLUGIN_NETWORK_TIMEOUT", 15),
                ).decode("utf-8"))
            except (UnicodeDecodeError, ValueError) as exc:
                raise SourceError("官方插件源索引不是有效 JSON", 422) from exc
        # A distribution can omit its index and still expose the built-in
        # source. It remains a valid, empty offline cache in that case.
        return {
            "source_type": "official",
            "name": "HamLog 官方插件源",
            "api_version": SOURCE_API_VERSION,
            "updated_at": source.get("updated_at") or utc_now(),
            "plugins": [],
        }
    raw = fetch_bytes(
        source["url"],
        int(config.get("PLUGIN_MAX_INDEX_BYTES", 5 * 1024 * 1024)),
        config.get("PLUGIN_NETWORK_TIMEOUT", 15),
    )
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SourceError("插件源索引不是有效 JSON", 422) from exc


def _iso_timestamp(value):
    if not isinstance(value, str) or not value:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _normalize_plugin(item, source_type):
    if not isinstance(item, dict):
        raise SourceError("插件源包含非法插件条目", 422)
    plugin_id = item.get("id")
    if not valid_plugin_id(plugin_id):
        raise SourceError("插件源包含非法插件 ID", 422)
    if not isinstance(item.get("name"), str) or not item["name"].strip():
        raise SourceError(f"插件 {plugin_id} 缺少有效 name", 422)
    if not valid_version(item.get("version")):
        raise SourceError(f"插件 {plugin_id} 版本不是有效语义化版本", 422)
    for field in ("permissions", "sensitive_permissions"):
        if field in item and not isinstance(item[field], list):
            raise SourceError(f"插件 {plugin_id} 的 {field} 必须是数组", 422)
    result = dict(item)
    result["id"] = plugin_id
    result["permissions"] = list(item.get("permissions") or [])
    result["sensitive_permissions"] = list(item.get("sensitive_permissions") or [])
    result["source_type"] = source_type
    # Ratings and verification are authoritative only for the official source.
    if source_type != "official":
        result["verified"] = False
    result.setdefault("rating", None)
    result.setdefault("author_rating", None)
    result.setdefault("badges", [])
    rating = result.get("rating")
    if rating is not None:
        if not isinstance(rating, dict):
            raise SourceError(f"插件 {plugin_id} 的 rating 必须是对象或 null", 422)
        score, count, level = rating.get("score"), rating.get("count"), rating.get("level")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= float(score) <= 5:
            raise SourceError(f"插件 {plugin_id} 的 rating.score 非法", 422)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise SourceError(f"插件 {plugin_id} 的 rating.count 非法", 422)
        if level not in {"bronze", "silver", "gold", "platinum"}:
            raise SourceError(f"插件 {plugin_id} 的 rating.level 非法", 422)
    author_rating = result.get("author_rating")
    if author_rating is not None and not isinstance(author_rating, dict):
        raise SourceError(f"插件 {plugin_id} 的 author_rating 必须是对象或 null", 422)
    if not isinstance(result.get("badges"), list) or any(not isinstance(badge, str) for badge in result["badges"]):
        raise SourceError(f"插件 {plugin_id} 的 badges 必须是字符串数组", 422)
    return result


def validate_index(index, expected_type):
    if not isinstance(index, dict):
        raise SourceError("插件源索引必须是 JSON 对象", 422)
    if index.get("api_version") not in {SOURCE_API_VERSION, 1}:
        raise SourceError("插件源 API 版本不兼容", 422)
    if not _iso_timestamp(index.get("updated_at")):
        raise SourceError("插件源缺少有效 updated_at", 422)
    if not isinstance(index.get("name"), str) or not index["name"].strip():
        raise SourceError("插件源缺少有效 name", 422)
    declared_type = index.get("source_type")
    if declared_type not in {"official", "third_party"}:
        raise SourceError("插件源 source_type 非法", 422)
    if expected_type == "official" and declared_type != "official":
        raise SourceError("官方源索引必须声明 source_type=official", 422)
    if expected_type == "third_party":
        # A third-party URL cannot promote itself to an official trust domain.
        source_type = "third_party"
    else:
        source_type = "official"
    plugins = index.get("plugins")
    if not isinstance(plugins, list) or len(plugins) > 1000:
        raise SourceError("插件源 plugins 必须是数组且不超过 1000 项", 422)
    normalized = [_normalize_plugin(item, source_type) for item in plugins]
    for item in normalized:
        item.setdefault("updated_at", index["updated_at"])
    ids = [item["id"] for item in normalized]
    if len(ids) != len(set(ids)):
        raise SourceError("插件源包含重复插件 ID", 422)
    normalized_index = dict(index)
    normalized_index["source_type"] = source_type
    normalized_index["api_version"] = SOURCE_API_VERSION
    normalized_index["plugins"] = normalized
    return normalized_index


def _source_row(db, source_id):
    row = db.execute("SELECT * FROM plugin_sources WHERE id=?", (source_id,)).fetchone()
    return dict(row) if row else None


def source_payload(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "url": row["url"],
        "source_type": row["source_type"],
        "enabled": bool(row["enabled"]),
        "updated_at": row["updated_at"],
        "cached_at": row["cached_at"],
    }


def refresh_source(db, source_id, config):
    source = _source_row(db, source_id)
    if not source:
        raise SourceError("插件源不存在", 404)
    if source_id == OFFICIAL_SOURCE_ID and source.get("index_json") and _configured_official_index(config) is None and _official_url(config) is None:
        cached_at = utc_now()
        db.execute("UPDATE plugin_sources SET cached_at=?,last_error=NULL WHERE id=?", (cached_at, source_id))
        db.commit()
        return {"id": source_id, "updated_at": source.get("updated_at"), "cached_at": cached_at}
    try:
        index = validate_index(_source_index(source, config), source["source_type"])
        cached_at = utc_now()
        if source.get("index_json") and source.get("updated_at") and _timestamp(index["updated_at"]) < _timestamp(source["updated_at"]):
            db.execute(
                "UPDATE plugin_sources SET cached_at=?,last_error=NULL WHERE id=?",
                (cached_at, source_id),
            )
            db.commit()
            return {"id": source_id, "updated_at": source["updated_at"], "cached_at": cached_at}
        encoded = json.dumps(index, ensure_ascii=False, separators=(",", ":"))
        db.execute(
            """UPDATE plugin_sources
               SET name=?, source_type=?, updated_at=?, cached_at=?, index_json=?, last_error=NULL
               WHERE id=?""",
            (index["name"], index["source_type"], index["updated_at"], cached_at, encoded, source_id),
        )
        db.execute("DELETE FROM plugin_market_cache WHERE source_id=?", (source_id,))
        for item in index["plugins"]:
            db.execute(
                """INSERT INTO plugin_market_cache(source_id,plugin_id,item_json,cached_at)
                   VALUES(?,?,?,?)""",
                (source_id, item["id"], json.dumps(item, ensure_ascii=False, separators=(",", ":")), cached_at),
            )
        db.commit()
        return {"id": source_id, "updated_at": index["updated_at"], "cached_at": cached_at}
    except SourceError as exc:
        db.execute("UPDATE plugin_sources SET last_error=? WHERE id=?", (str(exc), source_id))
        db.commit()
        raise


def refresh_sources(db, config, source_id=None):
    ensure_official_source(db)
    if source_id:
        sources = [_source_row(db, source_id)]
        if not sources[0]:
            raise SourceError("插件源不存在", 404)
    else:
        sources = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM plugin_sources WHERE enabled=1 ORDER BY id"
            ).fetchall()
        ]
    refreshed = []
    updated_at = {}
    errors = []
    for source in sources:
        try:
            result = refresh_source(db, source["id"], config)
            refreshed.append(result["id"])
            updated_at[result["id"]] = result["updated_at"]
        except SourceError as exc:
            errors.append({"id": source["id"], "error": str(exc), "code": exc.code})
    if errors:
        raise SourceError("部分插件源刷新失败", 503, {"refreshed": refreshed, "updated_at": updated_at, "errors": errors})
    return {"refreshed": refreshed, "updated_at": updated_at}


def add_source(db, name, url, config):
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 200:
        raise SourceError("name 不能为空且不能超过 200 个字符", 400)
    if not isinstance(url, str) or not url:
        raise SourceError("url 不能为空", 400)
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SourceError("url 必须是 HTTP/HTTPS 地址", 400)
    if db.execute("SELECT 1 FROM plugin_sources WHERE url=?", (url,)).fetchone():
        raise SourceError("插件源已存在", 409)
    source_id = "src_" + uuid.uuid4().hex[:12]
    # Fetch and validate before making the source visible to the rest of the app.
    source = {"id": source_id, "url": url, "source_type": "third_party"}
    index = validate_index(_source_index(source, config), "third_party")
    cached_at = utc_now()
    db.execute(
        """INSERT INTO plugin_sources(id,name,url,source_type,enabled,updated_at,cached_at,index_json)
           VALUES(?,?,?,?,1,?,?,?)""",
        (source_id, name.strip(), url, "third_party", index["updated_at"], cached_at,
         json.dumps(index, ensure_ascii=False, separators=(",", ":"))),
    )
    for item in index["plugins"]:
        db.execute(
            """INSERT INTO plugin_market_cache(source_id,plugin_id,item_json,cached_at)
               VALUES(?,?,?,?)""",
            (source_id, item["id"], json.dumps(item, ensure_ascii=False, separators=(",", ":")), cached_at),
        )
    db.commit()
    return source_payload(_source_row(db, source_id))


def list_sources(db):
    ensure_official_source(db)
    return [source_payload(dict(row)) for row in db.execute("SELECT * FROM plugin_sources ORDER BY id").fetchall()]


def cached_items(db, source_id=None, enabled_only=True):
    params = []
    clauses = []
    if source_id:
        clauses.append("c.source_id=?")
        params.append(source_id)
    if enabled_only:
        clauses.append("s.enabled=1")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    rows = db.execute(
        """SELECT c.source_id,c.plugin_id,c.item_json,c.cached_at,s.source_type,s.updated_at
           FROM plugin_market_cache c JOIN plugin_sources s ON s.id=c.source_id""" + where,
        params,
    ).fetchall()
    return [
        {
            "source_id": row["source_id"],
            "source_type": row["source_type"],
            "cached_at": row["cached_at"],
            "updated_at": row["updated_at"],
            "item": json.loads(row["item_json"]),
        }
        for row in rows
    ]


def find_cached_item(db, plugin_id, source_id=None):
    items = cached_items(db, source_id, enabled_only=False)
    matches = [entry for entry in items if entry["item"].get("id") == plugin_id]
    matches.sort(key=lambda entry: (entry["source_type"] != "official", entry["source_id"]))
    return matches[0] if matches else None


def state(db, plugin_id):
    row = db.execute(
        "SELECT enabled,sensitive_authorized,source_id,source_type FROM plugin_state WHERE id=?",
        (plugin_id,),
    ).fetchone()
    return {
        "enabled": bool(row["enabled"]) if row else False,
        "authorized": bool(row["sensitive_authorized"]) if row else False,
        "source_id": row["source_id"] if row else None,
        "source_type": row["source_type"] if row else None,
    }


def semver_installed_version(plugin_dir, plugin_id):
    path = Path(plugin_dir) / plugin_id / "manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return manifest.get("version")


def build_market(db, plugin_dir, source_id=None, keyword=None, sort="rating"):
    entries = cached_items(db, source_id, enabled_only=True)
    keyword = keyword.casefold() if isinstance(keyword, str) and keyword else None
    items = []
    for entry in entries:
        item = dict(entry["item"])
        if keyword:
            haystack = " ".join(str(item.get(field, "")) for field in ("id", "name", "author", "description")).casefold()
            if keyword not in haystack:
                continue
        status = state(db, item["id"])
        item["source_id"] = entry["source_id"]
        item["source_type"] = entry["source_type"]
        item["installed"] = (Path(plugin_dir) / item["id"]).is_dir() and status["source_id"] in {None, entry["source_id"]}
        item["update_available"] = False
        if item["installed"]:
            current = semver_installed_version(plugin_dir, item["id"])
            item["update_available"] = is_newer(item.get("version"), current)
        item["verified"] = bool(item.get("verified", False)) if entry["source_type"] == "official" else False
        item.setdefault("rating", None)
        item.setdefault("author_rating", None)
        item.setdefault("badges", [])
        items.append(item)

    def rating_score(item):
        rating = item.get("rating") or {}
        return float(rating.get("score", -1)) if isinstance(rating, dict) else -1

    if sort == "updated":
        items.sort(key=lambda item: str(item.get("updated_at", "")), reverse=True)
    elif sort == "name":
        items.sort(key=lambda item: str(item.get("name", item["id"])).casefold())
    else:
        items.sort(key=lambda item: (-rating_score(item), str(item.get("name", item["id"])).casefold()))
    cached_times = [entry["cached_at"] for entry in entries if entry["cached_at"]]
    return {"cached_at": max(cached_times) if cached_times else None, "items": items}


def _safe_member_path(extraction_root, member_name, plugin_id):
    if not isinstance(member_name, str) or not member_name or "\x00" in member_name:
        raise InstallError("ZIP 包含非法路径", 422)
    if "\\" in member_name or member_name.startswith("/") or re.match(r"^[A-Za-z]:", member_name):
        raise InstallError("ZIP 包含不安全路径", 422)
    raw_parts = member_name.split("/")
    if raw_parts[-1] == "":
        raw_parts = raw_parts[:-1]
    if not raw_parts or any(part in {".", "..", ""} or ":" in part for part in raw_parts):
        raise InstallError("ZIP 包含路径穿越", 422)
    parts = PurePosixPath(member_name).parts
    if parts[0] != plugin_id:
        raise InstallError("ZIP 顶层目录必须与插件 ID 一致", 422)
    target = extraction_root.joinpath(*parts)
    resolved = target.resolve()
    if resolved != extraction_root and extraction_root not in resolved.parents:
        raise InstallError("ZIP 包含路径穿越", 422)
    return target


def _extract_archive(payload, extraction_root, plugin_id, config):
    max_files = int(config.get("PLUGIN_MAX_ARCHIVE_FILES", 1000))
    max_uncompressed = int(config.get("PLUGIN_MAX_UNCOMPRESSED_BYTES", 100 * 1024 * 1024))
    max_file = int(config.get("PLUGIN_MAX_ARCHIVE_FILE_BYTES", 25 * 1024 * 1024))
    try:
        archive = zipfile.ZipFile(io.BytesIO(payload))
    except (OSError, zipfile.BadZipFile) as exc:
        raise InstallError("下载内容不是有效 ZIP 文件", 422) from exc
    with archive:
        members = archive.infolist()
        if not members or len(members) > max_files:
            raise InstallError("ZIP 文件数量超过限制", 422)
        declared_total = 0
        extracted_total = 0
        seen = set()
        extraction_root.mkdir(parents=True, exist_ok=True)
        for member in members:
            target = _safe_member_path(extraction_root, member.filename, plugin_id)
            canonical = "/".join(part.casefold() for part in PurePosixPath(member.filename).parts)
            if canonical in seen:
                raise InstallError("ZIP 包含重复路径", 422)
            seen.add(canonical)
            mode = (member.external_attr >> 16) & 0o170000
            if mode == 0o120000 or mode not in {0, 0o040000, 0o100000}:
                raise InstallError("ZIP 包含不支持的特殊文件", 422)
            if member.file_size < 0 or member.file_size > max_file:
                raise InstallError("ZIP 单文件超过大小限制", 422)
            declared_total += member.file_size
            if declared_total > max_uncompressed:
                raise InstallError("ZIP 解压内容超过大小限制", 422)
            if member.is_dir() or member.filename.endswith("/"):
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            try:
                with archive.open(member, "r") as source, target.open("wb") as destination:
                    file_total = 0
                    while True:
                        chunk = source.read(64 * 1024)
                        if not chunk:
                            break
                        file_total += len(chunk)
                        extracted_total += len(chunk)
                        if file_total > max_file or extracted_total > max_uncompressed:
                            raise InstallError("ZIP 解压内容超过大小限制", 422)
                        destination.write(chunk)
            except InstallError:
                raise
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise InstallError("ZIP 文件无法安全解压", 422) from exc
    candidate = extraction_root / plugin_id
    if not candidate.is_dir() or candidate.is_symlink():
        raise InstallError("ZIP 缺少插件顶层目录", 422)
    return candidate


def install_plugin(db, plugin_root, source_id, plugin_id, config, audit_func):
    if not valid_plugin_id(plugin_id):
        raise InstallError("plugin_id 非法", 400)
    source = _source_row(db, source_id)
    if not source:
        raise SourceError("插件源不存在", 404)
    if not source["enabled"]:
        raise SourceError("插件源已停用", 422)
    entry = find_cached_item(db, plugin_id, source_id)
    if not entry:
        raise SourceError("插件不在该插件源缓存中", 404)
    item = entry["item"]
    download_url = item.get("download_url")
    checksum = item.get("sha256")
    parsed_download = urlparse(download_url) if isinstance(download_url, str) else None
    if not parsed_download or parsed_download.scheme not in {"http", "https"} or not parsed_download.netloc:
        raise InstallError("插件缺少有效 download_url", 422)
    if not isinstance(checksum, str) or not SHA256.fullmatch(checksum):
        raise InstallError("插件缺少有效 SHA-256 校验值", 422)
    payload = fetch_bytes(
        download_url,
        int(config.get("PLUGIN_MAX_DOWNLOAD_BYTES", 50 * 1024 * 1024)),
        config.get("PLUGIN_NETWORK_TIMEOUT", 30),
    )
    actual = hashlib.sha256(payload).hexdigest()
    if actual.casefold() != checksum.casefold():
        raise InstallError("插件 ZIP SHA-256 校验失败", 422, {"expected": checksum.lower(), "actual": actual})

    root = Path(plugin_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix=".plugin-install-", dir=str(root.parent)))
    backup = None
    replaced = False
    try:
        candidate = _extract_archive(payload, temp_root, plugin_id, config)
        good, errors = audit_func(candidate)
        if not good:
            raise InstallError(
                "插件语法审核未通过,不允许加载",
                422,
                {"id": plugin_id, "audit_ok": False, "errors": errors},
            )
        try:
            manifest = json.loads((candidate / "manifest.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise InstallError("插件 manifest.json 无法读取", 422) from exc
        if manifest.get("id") != plugin_id:
            raise InstallError("插件 manifest id 与安装 ID 不一致", 422)
        if manifest.get("version") != item.get("version"):
            raise InstallError("插件版本与源索引不一致", 422)

        destination = root / plugin_id
        if destination.exists() or destination.is_symlink():
            if destination.is_symlink() or not destination.is_dir():
                raise InstallError("现有插件路径不是安全目录", 409)
            backup = root.parent / (".plugin-backup-" + uuid.uuid4().hex)
            destination.rename(backup)
        candidate.rename(destination)
        replaced = True
        db.execute(
            """INSERT INTO plugin_state(id,enabled,source_id,source_type)
               VALUES(?,1,?,?)
               ON CONFLICT(id) DO UPDATE SET enabled=1,sensitive_authorized=0,source_id=excluded.source_id,
               source_type=excluded.source_type,updated_at=CURRENT_TIMESTAMP""",
            (plugin_id, source_id, entry["source_type"]),
        )
        db.commit()
        if backup:
            try:
                shutil.rmtree(backup)
            except OSError:
                # Installation is already committed and usable. Keep a uniquely
                # named backup rather than risking removal of the new plugin.
                pass
            backup = None
        return {"id": plugin_id, "audit_ok": True, "errors": []}
    except Exception:
        db.rollback()
        destination = root / plugin_id
        if replaced and destination.exists():
            shutil.rmtree(destination, ignore_errors=True)
        if backup and backup.exists() and not destination.exists():
            backup.rename(destination)
            backup = None
        raise
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
        if backup and backup.exists():
            shutil.rmtree(backup, ignore_errors=True)


def remove_plugin(db, plugin_root, plugin_id):
    if not valid_plugin_id(plugin_id):
        raise SourceError("id 非法", 400)
    root = Path(plugin_root).resolve()
    path = root / plugin_id
    if not path.is_dir() or path.is_symlink():
        raise SourceError("插件不存在", 404)
    pending = root.parent / (".plugin-uninstall-" + uuid.uuid4().hex)
    try:
        path.rename(pending)
        db.execute("DELETE FROM plugin_state WHERE id=?", (plugin_id,))
        db.commit()
    except Exception:
        db.rollback()
        if pending.exists() and not path.exists():
            pending.rename(path)
        raise
    try:
        shutil.rmtree(pending)
    except OSError:
        # The plugin is no longer loadable; a uniquely named cleanup directory
        # is safer than restoring state after the DB transaction committed.
        pass
