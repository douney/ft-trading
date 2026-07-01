import base64
import getpass
import logging
import os
from typing import Optional

from modules.config.env import load_env

logger = logging.getLogger(__name__)

class BrokerConfig:
    def __init__(
        self,
        env_prefix: str,
        acc_type: str,
        password_file: str = "secrets.bin",
    ):
        load_env()

        self.env_prefix = env_prefix
        self.username = self._env("USERNAME")
        self.password = self._env("PASSWORD")
        self.api_key = self._env("API_KEY")
        self.acc_type = acc_type
        self.acc_number = self._env("ACC_NUMBER")
        self.encrypted_password = self._env("PASSWORD_ENCRYPTED")
        self.password_file = self._env("PASSWORD_FILE", password_file)

    def _env(self, name: str, default: str = "") -> str:
        return os.environ.get(f"{self.env_prefix}_{name}", default)

    def get_password(self) -> Optional[str]:
        return self.password

    def validate(self) -> None:
        missing = []
        if not self.username:
            missing.append(f"{self.env_prefix}_USERNAME")
        if not self.api_key:
            missing.append(f"{self.env_prefix}_API_KEY")
        if not self.acc_number:
            missing.append(f"{self.env_prefix}_ACC_NUMBER")

        if missing:
            raise ValueError("Missing broker config: " + ", ".join(missing))

    def decrypt_password(self, passphrase: Optional[str] = None) -> None:
        if self.password != "":
            return

        encrypted_data = self._read_encrypted_password()
        if encrypted_data is None:
            raise ValueError(
                f"Missing broker password. Set {self.env_prefix}_PASSWORD, "
                f"{self.env_prefix}_PASSWORD_ENCRYPTED, or provide {self.password_file}."
            )

        from Crypto.Cipher import AES
        from Crypto.Protocol.KDF import PBKDF2
        from Crypto.Util.Padding import unpad

        salt = encrypted_data[:16]
        iv = encrypted_data[16:32]
        encrypted_password = encrypted_data[32:]

        while True:
            current_passphrase = passphrase
            if current_passphrase is None:
                current_passphrase = getpass.getpass("Enter passphrase to decrypt password: ")

            key = PBKDF2(current_passphrase.encode(), salt, dkLen=32)
            cipher = AES.new(key, AES.MODE_CBC, iv)

            try:
                self.password = unpad(cipher.decrypt(encrypted_password), AES.block_size).decode()
                logger.info("Password decrypted successfully!")
                break
            except ValueError as e:
                if passphrase is not None:
                    raise ValueError("Invalid broker password passphrase") from e

                logger.error(f"Decryption error: {e}")

    def clear_password(self) -> None:
        self.password = ""

    def _read_encrypted_password(self) -> Optional[bytes]:
        if self.encrypted_password:
            return base64.b64decode(self.encrypted_password)

        if os.path.exists(self.password_file):
            with open(os.path.abspath(self.password_file), "rb") as f:
                return f.read()

        return None


class DemoConfig(BrokerConfig):
    def __init__(self):
        super().__init__("FT_IG_DEMO", "demo")


class LiveConfig(BrokerConfig):
    def __init__(self):
        super().__init__("FT_IG_LIVE", "live")
