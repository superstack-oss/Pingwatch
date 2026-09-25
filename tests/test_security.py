from app.security import email_allowed, hash_password, password_rules, valid_email, verify_password


def test_password_hash_roundtrip():
    stored = hash_password("Password@123")
    assert stored.startswith("pbkdf2$")
    assert verify_password("Password@123", stored)
    assert not verify_password("wrong-password", stored)


def test_password_rules():
    assert password_rules("short") is not None
    assert password_rules("abcdefgh") is not None
    assert password_rules("12345678") is not None
    assert password_rules("Password@123") is None


def test_email_validation_and_domain_restriction():
    assert valid_email("ops@company.com")
    assert not valid_email("not-an-email")
    assert email_allowed("ops@company.com", "")
    assert email_allowed("ops@company.com", "company.com, corp.local")
    assert not email_allowed("ops@gmail.com", "company.com")
