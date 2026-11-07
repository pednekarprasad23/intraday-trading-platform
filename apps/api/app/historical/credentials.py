"""Operator-only encrypted Dhan data token storage; no HTTP credential surface."""

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.models import AuditLog, ProviderCredential, utcnow


class CredentialError(ValueError):
    """Safe error with no token or cryptographic material."""


def initialize_key(path: Path) -> None:
    """Explicit one-time local initialization; never overwrite a key in use."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise CredentialError(
            "Credential key already exists; initialization refused"
        ) from exc
    try:
        with os.fdopen(fd, "wb") as output:
            output.write(Fernet.generate_key())
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _cipher(path: Path) -> Fernet:
    try:
        if path.is_symlink() or not path.is_file():
            raise CredentialError("Credential key file is missing or invalid")
        if os.name == "posix" and path.stat().st_mode & 0o077:
            raise CredentialError("Credential key file permissions are too broad")
        return Fernet(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise CredentialError("Credential key is unavailable or invalid") from exc


def store_dhan_token(db: Session, path: Path, token: str) -> None:
    if (
        not token
        or token != token.strip()
        or "\n" in token
        or "\r" in token
        or len(token) > 4096
    ):
        raise CredentialError("Invalid Dhan token input")
    ciphertext = _cipher(path).encrypt(token.encode("utf-8")).decode("ascii")
    row = db.get(ProviderCredential, "DHAN")
    if row is None:
        db.add(
            ProviderCredential(
                provider="DHAN", ciphertext=ciphertext, rotated_at=utcnow()
            )
        )
    else:
        row.ciphertext = ciphertext
        row.rotated_at = utcnow()
    db.add(AuditLog(event_type="dhan_credential_rotated"))
    db.commit()


def load_dhan_token(db: Session, path: Path) -> str:
    row = db.get(ProviderCredential, "DHAN")
    if row is None:
        raise CredentialError("No stored Dhan token; save one using the operator CLI")
    if row.key_version != 1:
        raise CredentialError("Unsupported credential key version")
    try:
        return _cipher(path).decrypt(row.ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError) as exc:
        raise CredentialError(
            "Dhan credential cannot be decrypted; check key and rotation"
        ) from exc


def delete_dhan_token(db: Session) -> None:
    row = db.get(ProviderCredential, "DHAN")
    if row is not None:
        db.delete(row)
        db.add(AuditLog(event_type="dhan_credential_deleted"))
        db.commit()
