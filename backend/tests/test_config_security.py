import pytest
from cryptography.fernet import Fernet

from app.core.config import Settings, check_initial_admin_password, check_security

GOOD_SECRET = "a" * 64


def make(**kw) -> Settings:
    base = dict(SECRET_KEY=GOOD_SECRET, ENCRYPTION_KEY=Fernet.generate_key().decode(), FIRST_SUPERUSER_PASSWORD="S3gura-y-larga")
    return Settings(_env_file=None, **{**base, **kw})


def test_valid_secrets_pass():
    check_security(make())


@pytest.mark.parametrize("secret", ["", "changeme", "secret", "dev-secret-key-change-in-production",
                                    "your-secret-key-here-generate-with-openssl-rand-hex-32", "  Your-Secret  "])
def test_insecure_or_sample_secret_key_is_rejected(secret):
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        check_security(make(SECRET_KEY=secret))


def test_missing_encryption_key_is_rejected():
    with pytest.raises(RuntimeError, match="not set"):
        check_security(make(ENCRYPTION_KEY=""))


def test_sample_encryption_key_is_rejected():
    with pytest.raises(RuntimeError, match="sample value"):
        check_security(make(ENCRYPTION_KEY="your-fernet-key-here"))


@pytest.mark.parametrize("key", ["no-es-base64!", "YWJj", "a" * 44])
def test_invalid_fernet_key_is_rejected_at_startup_not_at_first_use(key):
    with pytest.raises(RuntimeError, match="valid Fernet"):
        check_security(make(ENCRYPTION_KEY=key))


@pytest.mark.parametrize("password", ["", "changeme", "your-password-here"])
def test_default_admin_password_is_rejected_when_creating_the_admin(password, monkeypatch):
    monkeypatch.delenv("GUAYNET_SKIP_SECURITY_CHECK", raising=False)
    with pytest.raises(RuntimeError, match="FIRST_SUPERUSER_PASSWORD"):
        check_initial_admin_password(make(FIRST_SUPERUSER_PASSWORD=password))


def test_real_admin_password_passes(monkeypatch):
    monkeypatch.delenv("GUAYNET_SKIP_SECURITY_CHECK", raising=False)
    check_initial_admin_password(make())


def test_skip_flag_is_honoured_for_local_development(monkeypatch):
    monkeypatch.setenv("GUAYNET_SKIP_SECURITY_CHECK", "1")
    check_initial_admin_password(make(FIRST_SUPERUSER_PASSWORD="changeme"))
