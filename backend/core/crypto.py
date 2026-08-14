import base64
import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class Crypto:
    """AES-256-GCM storage encryption backed by a local 32-byte key."""

    def __init__(self, key_path):
        self.key_path = Path(key_path)
        self.key_path.parent.mkdir(parents=True, exist_ok=True)
        self.key = self._load_or_create()

    def _load_or_create(self):
        configured = os.environ.get("HAMLOG_AES_KEY")
        configured_b64 = os.environ.get("HAMLOG_AES_KEY_B64")
        if configured_b64:
            try:
                key = base64.b64decode(configured_b64.encode("ascii"), altchars=b"-_", validate=True)
            except (ValueError, UnicodeEncodeError) as exc:
                raise ValueError("HAMLOG_AES_KEY_B64 is not valid base64") from exc
            if len(key) != 32:
                raise ValueError("HAMLOG_AES_KEY_B64 must decode to 32 bytes")
            return key
        if configured:
            try:
                key = bytes.fromhex(configured) if len(configured) == 64 else configured.encode("utf-8")
            except ValueError as exc:
                raise ValueError("HAMLOG_AES_KEY must be 32 bytes or 64 hex characters") from exc
            if len(key) != 32:
                raise ValueError("HAMLOG_AES_KEY must be 32 bytes or 64 hex characters")
            return key
        raise ValueError("HAMLOG_AES_KEY or HAMLOG_AES_KEY_B64 must be configured")

    def encrypt(self, plaintext):
        if not isinstance(plaintext, str):
            raise TypeError("plaintext must be a string")
        nonce = os.urandom(12)
        ciphertext = AESGCM(self.key).encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    def decrypt(self, token):
        try:
            raw = base64.urlsafe_b64decode(token.encode("ascii"))
            plaintext = AESGCM(self.key).decrypt(raw[:12], raw[12:], None)
            return plaintext.decode("utf-8")
        except (ValueError, TypeError, UnicodeDecodeError, InvalidTag) as exc:
            raise ValueError("invalid encrypted value") from exc


def get_crypto(app):
    crypto = app.extensions.get("hamlog_crypto")
    if crypto is None:
        crypto = Crypto(Path(app.config["DATA_DIR"]) / "secret.key")
        app.extensions["hamlog_crypto"] = crypto
    return crypto
