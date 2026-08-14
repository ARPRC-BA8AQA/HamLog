# Windows build

HamLog 2.0.0 is packaged as a PyInstaller one-directory application and then
wrapped in a per-user Inno Setup installer.

## Requirements

- 64-bit Windows 10 or 11
- Python 3.9 or newer with the `py` launcher
- Inno Setup 6 (`ISCC.exe`) for the installer step

## Build

Run from the repository root in PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\installer\build.ps1 -Clean
```

Use `-SkipInstaller` to build only `installer\dist\HamLog\HamLog.exe`. Use
`-Python C:\path\to\python.exe` when the `py` launcher is unavailable. The full
installer is written to `installer\dist\HamLog-2.0.0-Setup.exe`.

The spec recursively includes `front`, `docs`, and any repository-level
`assets` or `official_plugins` directory, plus `LICENSE`. Runtime configuration,
databases, installed plugins, logs, caches, and environment files are excluded.

## Runtime storage

Installed builds keep writable state outside the application directory:

```text
%LOCALAPPDATA%\HamLog\config.yaml
%LOCALAPPDATA%\HamLog\data\
%LOCALAPPDATA%\HamLog\logs\
%LOCALAPPDATA%\HamLog\plugins\
```

Set `HAMLOG_HOME` before starting HamLog to use another state directory. The
installer and uninstaller leave this state intact so upgrades do not remove
user data. Do not place secrets in the build tree; AES keys remain supplied via
`HAMLOG_AES_KEY` or `HAMLOG_AES_KEY_B64`.
