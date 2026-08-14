NORMAL_PERMISSIONS = {
    "log.read", "log.write", "settings.read", "settings.write", "qsl.read",
    "ui.menu", "ui.style", "ui.theme", "ui.panel", "ui.widget",
}
SENSITIVE_PERMISSIONS = {
    "network", "file.write", "file.read", "system", "db.raw",
    "aes.decrypt", "subprocess",
}


def validate_permissions(manifest):
    normal = set(manifest.get("permissions", []))
    sensitive = set(manifest.get("sensitive_permissions", []))
    unknown = (normal - NORMAL_PERMISSIONS) | (sensitive - SENSITIVE_PERMISSIONS)
    if unknown:
        return ["未知权限: " + ", ".join(sorted(unknown))]
    return []
