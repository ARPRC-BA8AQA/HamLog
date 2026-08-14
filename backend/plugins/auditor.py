import ast
import json
import py_compile
import re
from pathlib import Path

PLUGIN_ID = re.compile(r"^[a-z][a-z0-9_-]{2,39}$")

def audit(plugin_dir):
    path = Path(plugin_dir); errors = []
    if not PLUGIN_ID.fullmatch(path.name): errors.append("插件目录名不合规")
    manifest_path = path / "manifest.json"
    if not manifest_path.exists(): return False, ["缺少 manifest.json"]
    try: manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc: return False, [f"manifest.json: {exc}"]
    required = ("id", "name", "version", "entry", "min_app_version", "api_version", "permissions")
    for field in required:
        if field not in manifest: errors.append(f"manifest 缺少字段: {field}")
    if manifest.get("id") != path.name: errors.append("manifest id 与目录名不一致")
    entry = path / str(manifest.get("entry", ""))
    if not entry.is_file(): errors.append("入口文件不存在")
    for source in path.glob("*.py"):
        try: ast.parse(source.read_text(encoding="utf-8"), filename=str(source)); py_compile.compile(str(source), doraise=True)
        except (SyntaxError, py_compile.PyCompileError) as exc: errors.append(f"{source.name}: {exc}")
    return not errors, errors
