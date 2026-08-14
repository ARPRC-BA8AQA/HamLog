"""Encrypted QRZ credential persistence."""

from backend.core.crypto import get_crypto


USERNAME_KEY = "qrz_username_encrypted"
PASSWORD_KEY = "qrz_password_encrypted"


class QRZCredentialStore:
    def __init__(self, app, db):
        self.app = app
        self.db = db

    def set(self, username, password):
        username = str(username).strip() if isinstance(username, str) else ""
        if not username or len(username) > 128:
            raise ValueError("username 不能为空且不能超过 128 字符")
        if not isinstance(password, str) or not password or len(password) > 1024:
            raise ValueError("password 不能为空且不能超过 1024 字符")
        crypto = get_crypto(self.app)
        encrypted = {
            USERNAME_KEY: crypto.encrypt(username),
            PASSWORD_KEY: crypto.encrypt(password),
        }
        for key, value in encrypted.items():
            self.db.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )
        self.db.commit()

    def get(self):
        rows = self.db.execute(
            "SELECT key,value FROM settings WHERE key IN (?,?)",
            (USERNAME_KEY, PASSWORD_KEY),
        ).fetchall()
        values = {row["key"]: row["value"] for row in rows}
        if USERNAME_KEY not in values or PASSWORD_KEY not in values:
            return None
        crypto = get_crypto(self.app)
        return crypto.decrypt(values[USERNAME_KEY]), crypto.decrypt(values[PASSWORD_KEY])

    def clear(self):
        cursor = self.db.execute(
            "DELETE FROM settings WHERE key IN (?,?)",
            (USERNAME_KEY, PASSWORD_KEY),
        )
        self.db.commit()
        return cursor.rowcount
