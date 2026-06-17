from backend.core.security import hash_password, verify_password


def test_password_hashing_and_verification_work() -> None:
    plain = "StrongPass1"

    hashed = hash_password(plain)

    assert isinstance(hashed, str)
    assert hashed.startswith("$2")
    assert verify_password(plain, hashed) is True
    assert verify_password("WrongPass1", hashed) is False
