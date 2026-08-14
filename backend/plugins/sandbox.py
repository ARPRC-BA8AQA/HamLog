import importlib.util
import json
import multiprocessing
import sys
import traceback
from pathlib import Path

from backend.plugins.api import PluginContext


def _worker(connection, plugin_dir, action, args, sensitive_authorized):
    path = Path(plugin_dir)
    try:
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        context = PluginContext(manifest["id"], path, manifest.get("permissions", []), manifest.get("sensitive_permissions", []), sensitive_authorized)
        entry = path / manifest["entry"]
        module_name = "hamlog_plugin_" + manifest["id"].replace("-", "_")
        spec = importlib.util.spec_from_file_location(module_name, entry)
        if not spec or not spec.loader: raise RuntimeError("无法加载插件入口")
        module = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(path))
        try: spec.loader.exec_module(module)
        finally:
            if sys.path and sys.path[0] == str(path): sys.path.pop(0)
        plugin_class = getattr(module, "Plugin", None)
        if plugin_class is None: raise RuntimeError("入口文件未定义 Plugin 类")
        plugin = plugin_class(context)
        if hasattr(plugin, "on_load"): plugin.on_load()
        if action == "__actions__": result = plugin.get_actions() if hasattr(plugin, "get_actions") else []
        elif not hasattr(plugin, "invoke"): raise RuntimeError("插件未实现 invoke")
        else: result = plugin.invoke(action, args)
        if hasattr(plugin, "on_unload"): plugin.on_unload()
        json.dumps(result, ensure_ascii=False)
        connection.send({"ok": True, "result": result, "ui": context.ui})
    except Exception as exc:
        connection.send({"ok": False, "error": str(exc), "traceback": traceback.format_exc(limit=8)})
    finally:
        connection.close()


def invoke_plugin(plugin_dir, action, args=None, sensitive_authorized=False, timeout=30):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(child, str(plugin_dir), action, args or {}, sensitive_authorized), daemon=True)
    process.start(); child.close()
    if not parent.poll(min(max(float(timeout), 1), 60)):
        process.terminate(); process.join(5)
        return {"ok": False, "error": "插件执行超时"}
    try: result = parent.recv()
    except EOFError: result = {"ok": False, "error": "插件子进程异常退出"}
    finally:
        parent.close(); process.join(5)
        if process.is_alive(): process.terminate()
    return result
