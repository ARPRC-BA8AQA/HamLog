import base64
import os
import logging
from pathlib import Path

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
                key = base64.urlsafe_b64decode(configured_b64.encode("ascii"))
            except (ValueError, UnicodeEncodeError) as exc:
                raise ValueError("HAMLOG_AES_KEY_B64 is not valid base64") from exc
            if len(key) != 32:
                raise ValueError("HAMLOG_AES_KEY_B64 must decode to 32 bytes")
            return key
        if configured:
            key = bytes.fromhex(configured) if len(configured) == 64 else configured.encode("utf-8")
            if len(key) != 32:
                raise ValueError("HAMLOG_AES_KEY must be 32 bytes or 64 hex characters")
            return key
        if self.key_path.exists():
            key = self.key_path.read_bytes()
            if len(key) != 32:
                raise ValueError("AES key must be exactly 32 bytes")
            return key
        logging.getLogger("hamlog").warning("HAMLOG_AES_KEY is not set; generating a local development key at %s", self.key_path)
        key = AESGCM.generate_key(bit_length=256)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        fd = os.open(self.key_path, flags, 0o600)
        try:
            os.write(fd, key)
        finally:
            os.close(fd)
        try:
            os.chmod(self.key_path, 0o600)
        except OSError:
            pass
        return key

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
        except (ValueError, TypeError, UnicodeDecodeError) as exc:
            raise ValueError("invalid encrypted value") from exc


def get_crypto(app):
    crypto = app.extensions.get("hamlog_crypto")
    if crypto is None:
        crypto = Crypto(Path(app.config["DATA_DIR"]) / "secret.key")
        app.extensions["hamlog_crypto"] = crypto
    return crypto
