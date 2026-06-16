from __future__ import annotations

import json
import os
import socket
from base64 import urlsafe_b64encode
from getpass import getpass
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from subs_down_n_sync.exceptions import MissingCredentialsError

_CONFIG_DIR = Path.home() / ".config" / "subs-down-n-sync"
_CREDS_FILE = _CONFIG_DIR / "credentials.enc"
_SALT = b"subs-down-n-sync"
_ITERATIONS = 480_000


def _get_machine_secret() -> bytes:
    machine_id = Path("/etc/machine-id")
    if machine_id.exists():
        return machine_id.read_text().strip().encode()
    return (socket.gethostname() + os.getlogin()).encode()


def _derive_key(secret: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=_ITERATIONS,
    )
    return urlsafe_b64encode(kdf.derive(secret))


def _get_fernet() -> Fernet:
    return Fernet(_derive_key(_get_machine_secret()))


def save_credentials(user: str, pwd: str) -> None:
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"user": user, "pwd": pwd}).encode()
    _CREDS_FILE.write_bytes(_get_fernet().encrypt(payload))
    _CREDS_FILE.chmod(0o600)


def _load_from_file() -> tuple[str, str] | None:
    if not _CREDS_FILE.exists():
        return None
    try:
        payload = _get_fernet().decrypt(_CREDS_FILE.read_bytes())
        data = json.loads(payload)
        return data["user"], data["pwd"]
    except (InvalidToken, KeyError, json.JSONDecodeError):
        return None


def _prompt_and_save() -> tuple[str, str]:
    print("\nCredenciais do OpenSubtitles não encontradas.")
    print("Serão salvas em ~/.config/subs-down-n-sync/credentials.enc (criptografado).")
    user = input("Usuário OpenSubtitles: ").strip()
    pwd = getpass("Senha OpenSubtitles: ").strip()
    if not user or not pwd:
        raise MissingCredentialsError("Usuário e senha são obrigatórios.")
    save_credentials(user, pwd)
    print("✓ Credenciais salvas.")
    return user, pwd


def load_credentials() -> tuple[str, str]:
    user = os.environ.get("OPENSUBTITLES_USERNAME")
    pwd = os.environ.get("OPENSUBTITLES_PASSWORD")
    if user and pwd:
        return user, pwd

    result = _load_from_file()
    if result is not None:
        return result

    return _prompt_and_save()
