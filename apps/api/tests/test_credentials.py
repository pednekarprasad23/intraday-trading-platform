import os

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.historical.credentials import (
    CredentialError,
    delete_dhan_token,
    initialize_key,
    load_dhan_token,
    store_dhan_token,
)
from app.models import AuditLog, Base, ProviderCredential


def test_encrypted_rotation_and_deletion(tmp_path):
    key = tmp_path / "private" / "key"
    initialize_key(key)
    with pytest.raises(CredentialError, match="already exists"):
        initialize_key(key)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        store_dhan_token(db, key, "first-private-token")
        row = db.get(ProviderCredential, "DHAN")
        assert "first-private-token" not in row.ciphertext
        assert load_dhan_token(db, key) == "first-private-token"
        store_dhan_token(db, key, "replacement-private-token")
        assert load_dhan_token(db, key) == "replacement-private-token"
        assert db.query(ProviderCredential).count() == 1
        assert db.query(AuditLog).count() == 2
        delete_dhan_token(db)
        with pytest.raises(CredentialError, match="No stored"):
            load_dhan_token(db, key)
        assert db.query(AuditLog).count() == 3
    if os.name == "posix":
        assert key.stat().st_mode & 0o077 == 0


def test_wrong_key_and_bad_input_fail_closed(tmp_path):
    key = tmp_path / "key"
    initialize_key(key)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        with pytest.raises(CredentialError, match="Invalid Dhan token"):
            store_dhan_token(db, key, "token\nother")
        store_dhan_token(db, key, "secret-token")
        wrong_key = tmp_path / "wrong"
        wrong_key.write_bytes(Fernet.generate_key())
        if os.name == "posix":
            wrong_key.chmod(0o600)
        with pytest.raises(CredentialError, match="cannot be decrypted") as error:
            load_dhan_token(db, wrong_key)
        assert "secret-token" not in str(error.value)
