from cryptography.fernet import Fernet

from agent_tracer_plus.security.encryption import FieldEncryptor
from agent_tracer_plus.security.redaction import PIIRedactor


def test_pii_redactor():
    redactor = PIIRedactor()

    text = "Contact me at user@example.com or call 555-123-4567."
    redacted = redactor.redact_text(text)

    assert "user@example.com" not in redacted
    assert "[REDACTED:EMAIL]" in redacted
    assert "555-123-4567" not in redacted
    assert "[REDACTED:PHONE]" in redacted

    # Test payload recursive
    payload = {
        "user_info": {
            "email": "test@test.com",
            "name": "John Doe",
            "ssn": "123-45-6789"
        },
        "tags": ["safe_tag", "card: 1234-5678-9012-3456"]
    }

    scrubbed = redactor.redact_payload(payload)
    assert scrubbed["user_info"]["email"] == "[REDACTED:EMAIL]"
    assert scrubbed["user_info"]["ssn"] == "[REDACTED:SSN]"
    assert scrubbed["user_info"]["name"] == "John Doe"
    assert scrubbed["tags"][0] == "safe_tag"
    assert "1234-5678-9012-3456" not in scrubbed["tags"][1]

def test_field_encryptor():
    key = Fernet.generate_key()
    encryptor = FieldEncryptor(key)

    payload = {
        "public_data": "safe",
        "secret_prompt": "You are a helpful assistant.",
        "api_response": {"status": "ok", "token": "abc-123"}
    }

    encrypted = encryptor.encrypt_payload(payload, fields=["secret_prompt", "api_response"])

    assert encrypted["public_data"] == "safe"
    assert encrypted["secret_prompt"].startswith("ENCRYPTED:")
    assert "helpful assistant" not in encrypted["secret_prompt"]
    assert encrypted["api_response"].startswith("ENCRYPTED:")

    decrypted = encryptor.decrypt_payload(encrypted, fields=["secret_prompt", "api_response"])
    assert decrypted["secret_prompt"] == "You are a helpful assistant."
    assert decrypted["api_response"]["token"] == "abc-123"
