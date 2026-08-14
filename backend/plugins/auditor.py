import ast
import json
import re
from pathlib import Path
from backend.plugins.permissions import validate_permissions

PLUGIN_ID = re.compile(r"^[a-z][a-z0-9_-]{2,39}$")
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$")

def audit(plugin_dir):
    path = Path(plugin_dir).resolve(); errors = []
    if not PLUGIN_ID.fullmatch(path.name): errors.append("插件目录名不合规")
    manifest_path = path / "manifest.json"
    if not manifest_path.exists(): return False, ["缺少 manifest.json"]
    try: manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc: return False, [f"manifest.json: {exc}"]
    if not isinstance(manifest, dict): return False, ["manifest.json 必须是对象"]
    required = ("id", "name", "version", "author", "entry", "min_app_version", "api_version", "permissions")
    for field in required:
        if field not in manifest: errors.append(f"manifest 缺少字段: {field}")
    if manifest.get("id") != path.name: errors.append("manifest id 与目录名不一致")
    if not SEMVER.fullmatch(str(manifest.get("version", ""))): errors.append("manifest version 不是有效语义化版本")
    if manifest.get("api_version") != "1": errors.append("插件 API 版本不兼容")
    errors.extend(validate_permissions(manifest))
    try:
        entry = (path / str(manifest.get("entry", ""))).resolve()
        if path not in entry.parents or not entry.is_file(): errors.append("入口文件不存在或超出插件目录")
    except (OSError, RuntimeError):
        errors.append("入口文件路径非法")
    for source in path.glob("*.py"):
        try:
            text = source.read_text(encoding="utf-8")
            ast.parse(text, filename=str(source))
            compile(text, str(source), "exec")
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            errors.append(f"{source.name}: {exc}")
    return not errors, errors
