from opentrend.crypto import decrypt_token, encrypt_token


def test_roundtrip() -> None:
    key = "my-secret-key-for-testing-12345"
    token = "ghp_abc123xyz"
    encrypted = encrypt_token(token, key)
    assert encrypted != token
    assert decrypt_token(encrypted, key) == token


def test_different_keys_produce_different_ciphertext() -> None:
    token = "ghp_abc123xyz"
    a = encrypt_token(token, "key-a-0000000000000000000000")
    b = encrypt_token(token, "key-b-0000000000000000000000")
    assert a != b


def test_decrypt_with_wrong_key_fails() -> None:
    import pytest

    token = "ghp_abc123xyz"
    encrypted = encrypt_token(token, "correct-key-000000000000000")
    with pytest.raises(Exception):
        decrypt_token(encrypted, "wrong-key-00000000000000000")
