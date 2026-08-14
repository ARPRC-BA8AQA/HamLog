import importlib.util
import ast
import json
import multiprocessing
import os
import sys
import traceback
from pathlib import Path

from backend.plugins.api import PluginContext


DANGEROUS_IMPORTS = {
    "socket": "网络请求请使用 ctx.http_get/http_post",
    "requests": "网络请求请使用 ctx.http_get/http_post",
    "urllib": "网络请求请使用 ctx.http_get/http_post",
    "http": "网络请求请使用 ctx.http_get/http_post",
    "ftplib": "网络请求请使用 ctx.http_get/http_post",
    "subprocess": "插件不允许直接启动子进程",
    "ctypes": "插件不允许直接调用系统库",
    "os": "文件与系统操作请使用 PluginContext",
    "pathlib": "文件操作请使用 PluginContext",
    "shutil": "文件操作请使用 PluginContext",
    "glob": "文件操作请使用 PluginContext",
    "tempfile": "文件操作请使用 PluginContext",
}


def _check_runtime_imports(path, manifest, sensitive_authorized):
    violations = []
    for source in path.rglob("*.py"):
        if "data" in source.relative_to(path).parts or "__pycache__" in source.parts:
            continue
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name.split(".", 1)[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".", 1)[0]]
            for name in names:
                guidance = DANGEROUS_IMPORTS.get(name)
                if guidance:
                    violations.append(f"{source.name}: 禁止 import {name}，{guidance}")
            if isinstance(node, ast.Call):
                function = node.func
                if isinstance(function, ast.Name) and function.id in {"open", "eval", "exec", "compile", "__import__"}:
                    violations.append(f"{source.name}: 禁止直接调用 {function.id}，请使用 PluginContext")
    if violations:
        raise PermissionError("; ".join(sorted(set(violations))))


def _apply_resource_limits(memory_mb, cpu_seconds):
    """Apply best-effort limits available in the current child process."""
    try:
        import resource
    except ImportError:  # Windows has no stdlib resource module.
        resource = None
    if resource is not None:
        memory_bytes = max(64, int(memory_mb)) * 1024 * 1024
        for limit_name in ("RLIMIT_AS", "RLIMIT_DATA"):
            limit = getattr(resource, limit_name, None)
            if limit is not None:
                try:
                    resource.setrlimit(limit, (memory_bytes, memory_bytes))
                    break
                except (OSError, ValueError):
                    continue
        if hasattr(resource, "RLIMIT_CPU"):
            try:
                cpu = max(1, int(cpu_seconds))
                resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
            except (OSError, ValueError):
                pass
        if hasattr(resource, "RLIMIT_NOFILE"):
            try:
                soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
                descriptor_limit = min(128, hard) if hard != resource.RLIM_INFINITY else 128
                resource.setrlimit(resource.RLIMIT_NOFILE, (descriptor_limit, descriptor_limit))
            except (OSError, ValueError):
                pass
    if hasattr(os, "sched_getaffinity") and hasattr(os, "sched_setaffinity"):
        try:
            available = os.sched_getaffinity(0)
            if available:
                os.sched_setaffinity(0, {min(available)})
        except OSError:
            pass


def _worker(connection, plugin_dir, action, args, sensitive_authorized, memory_mb, cpu_seconds, db_path, app_data_dir):
    path = Path(plugin_dir)
    try:
        _apply_resource_limits(memory_mb, cpu_seconds)
        manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        _check_runtime_imports(path, manifest, sensitive_authorized)
        context = PluginContext(manifest["id"], path, manifest.get("permissions", []), manifest.get("sensitive_permissions", []), sensitive_authorized, db_path, app_data_dir)
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


def _stop_process(process):
    if not process.is_alive():
        return
    process.terminate()
    process.join(5)
    if process.is_alive() and hasattr(process, "kill"):
        process.kill()
        process.join(2)


def invoke_plugin(plugin_dir, action, args=None, sensitive_authorized=False, timeout=30, memory_mb=256, db_path=None, app_data_dir=None):
    context = multiprocessing.get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    bounded_timeout = min(max(float(timeout), 1), 60)
    process = context.Process(
        target=_worker,
        args=(child, str(plugin_dir), action, args or {}, sensitive_authorized, memory_mb, int(bounded_timeout) + 1, db_path, app_data_dir),
        daemon=True,
    )
    process.start(); child.close()
    if not parent.poll(bounded_timeout):
        _stop_process(process)
        parent.close()
        return {"ok": False, "error": "插件执行超时"}
    try: result = parent.recv()
    except EOFError: result = {"ok": False, "error": "插件子进程异常退出"}
    finally:
        parent.close(); process.join(5)
        _stop_process(process)
    return result
