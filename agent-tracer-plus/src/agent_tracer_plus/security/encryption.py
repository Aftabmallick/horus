"""AES-256-GCM field encryption for payloads."""

import json
import os
import base64
import secrets
from typing import Any, Dict, List, Optional, Union

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:
    AESGCM = None


class FieldEncryptor:
    """Encrypt specific fields in span payloads at rest.
    
    Requires `cryptography` package.
    """

    def __init__(self, key: Union[str, bytes]):
        if AESGCM is None:
            raise ImportError("cryptography package is required for encryption. Run `pip install cryptography`")

        # Ensure key is exactly 32 bytes for AES-256
        if isinstance(key, str):
            # If it's a hex string, decode it
            if len(key) == 64:
                self.key = bytes.fromhex(key)
            else:
                # Pad or truncate to 32 bytes for simplicity (in a real app, use PBKDF2/HKDF)
                self.key = key.encode('utf-8')[:32].ljust(32, b'\0')
        else:
            self.key = key[:32].ljust(32, b'\0')

        self.aesgcm = AESGCM(self.key)

    def encrypt_value(self, value: Any) -> str:
        """Serialize and encrypt any JSON-serializable value using AES-256-GCM."""
        data = json.dumps(value).encode('utf-8')
        nonce = os.urandom(12) # 96-bit nonce is standard for GCM
        ct = self.aesgcm.encrypt(nonce, data, None)
        # Store as nonce + ciphertext, base64 encoded
        encrypted = base64.b64encode(nonce + ct).decode('utf-8')
        return f"ENCRYPTED:{encrypted}"

    def decrypt_value(self, encrypted_str: str) -> Any:
        """Decrypt and deserialize a value using AES-256-GCM."""
        if not encrypted_str.startswith("ENCRYPTED:"):
            return encrypted_str

        raw_data = base64.b64decode(encrypted_str[10:])
        nonce = raw_data[:12]
        ct = raw_data[12:]
        decrypted = self.aesgcm.decrypt(nonce, ct, None)
        return json.loads(decrypted.decode('utf-8'))

    def encrypt_payload(self, payload: Dict[str, Any], fields: list[str]) -> Dict[str, Any]:
        """Encrypt specific keys in a dictionary payload."""
        if not isinstance(payload, dict):
            return payload

        result = dict(payload)
        for field in fields:
            if field in result:
                result[field] = self.encrypt_value(result[field])
        return result

    def decrypt_payload(self, payload: Dict[str, Any], fields: list[str]) -> Dict[str, Any]:
        """Decrypt specific keys in a dictionary payload."""
        if not isinstance(payload, dict):
            return payload

        result = dict(payload)
        for field in fields:
            if field in result and isinstance(result[field], str):
                result[field] = self.decrypt_value(result[field])
        return result


class KeyManager:
    """Manages AES-256 encryption keys with rotation and environment loading.

    Usage::

        # Generate a new key and store its hex in an environment variable:
        key_hex = KeyManager.generate_key()
        os.environ["TRACER_ENCRYPTION_KEY"] = key_hex

        # Load from env and create encryptor:
        km = KeyManager.from_env("TRACER_ENCRYPTION_KEY")
        encryptor = km.get_encryptor()

        # Rotate key (re-encrypts all provided payloads):
        new_hex = KeyManager.generate_key()
        updated_payloads = km.rotate_key(new_hex, payloads, encrypted_fields)
    """

    def __init__(self, key_hex: str) -> None:
        if len(key_hex) != 64:
            raise ValueError(
                f"Key must be a 64-character hex string (32 bytes / 256 bits). "
                f"Got {len(key_hex)} chars. Use KeyManager.generate_key()."
            )
        self._key_hex = key_hex
        self._encryptor = FieldEncryptor(key_hex)

    @staticmethod
    def generate_key() -> str:
        """Generate a cryptographically strong 256-bit key as a hex string."""
        return secrets.token_hex(32)

    @classmethod
    def from_env(cls, env_var: str = "TRACER_ENCRYPTION_KEY") -> "KeyManager":
        """Load a key from an environment variable.

        Raises:
            ValueError: If the env var is not set or is not a valid 256-bit hex key.
        """
        key_hex = os.getenv(env_var, "")
        if not key_hex:
            raise ValueError(
                f"Encryption key env var '{env_var}' is not set. "
                f"Generate a key with KeyManager.generate_key() and set it in the environment."
            )
        return cls(key_hex)

    def get_encryptor(self) -> FieldEncryptor:
        """Return the current FieldEncryptor instance."""
        return self._encryptor

    def rotate_key(
        self,
        new_key_hex: str,
        payloads: List[Dict[str, Any]],
        encrypted_fields: List[str],
    ) -> List[Dict[str, Any]]:
        """Re-encrypt all payloads from the current key to a new key.

        Args:
            new_key_hex: New 64-char hex key.
            payloads: List of payload dicts containing encrypted fields.
            encrypted_fields: Field names that are currently encrypted.

        Returns:
            List of payloads with fields re-encrypted under the new key.
        """
        new_km = KeyManager(new_key_hex)
        new_encryptor = new_km.get_encryptor()
        rotated = []

        for payload in payloads:
            # 1. Decrypt all fields with current key
            decrypted = self._encryptor.decrypt_payload(payload, encrypted_fields)
            # 2. Re-encrypt with new key
            re_encrypted = new_encryptor.encrypt_payload(decrypted, encrypted_fields)
            rotated.append(re_encrypted)

        # Update current key
        self._key_hex = new_key_hex
        self._encryptor = new_encryptor
        return rotated


class KMSKeyProvider:
    """Abstract interface for fetching keys from cloud KMS providers.

    Subclass this to implement AWS KMS, GCP Cloud KMS, or Azure Key Vault.

    Example::

        class AWSKMSProvider(KMSKeyProvider):
            def fetch_key(self, key_id: str) -> str:
                import boto3
                client = boto3.client("kms")
                response = client.generate_data_key(KeyId=key_id, KeySpec="AES_256")
                return response["Plaintext"].hex()
    """

    def fetch_key(self, key_id: str) -> str:
        """Fetch a 256-bit key (hex) from the KMS provider.

        Args:
            key_id: Provider-specific key identifier (e.g., ARN, resource name).

        Returns:
            64-character hex string representing the 256-bit key.

        Raises:
            NotImplementedError: Must be overridden by subclasses.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement fetch_key(key_id). "
            "See KMSKeyProvider docstring for examples."
        )

    def to_key_manager(self, key_id: str) -> KeyManager:
        """Convenience: fetch key and wrap in a KeyManager."""
        return KeyManager(self.fetch_key(key_id))


class EnvelopeEncryptor:
    """True Envelope Encryption using a KMS provider to encrypt Data Encryption Keys (DEKs)."""
    
    def __init__(self, kms_provider: KMSKeyProvider, kek_id: str):
        self.kms = kms_provider
        self.kek_id = kek_id
        # In a real cloud setup, kms_provider would both generate a DEK and return (plaintext_dek, encrypted_dek)
        # Here we simulate the KMS generate_data_key behavior using AESGCM for the KEK.
        kek_hex = self.kms.fetch_key(self.kek_id)
        if len(kek_hex) != 64:
            kek_hex = kek_hex.encode('utf-8')[:32].ljust(32, b'\0').hex()
        self.kek = bytes.fromhex(kek_hex)
        self.kek_aesgcm = AESGCM(self.kek)

    def encrypt_payload(self, payload: Dict[str, Any], fields: list[str]) -> Dict[str, Any]:
        """Generate a random DEK, encrypt the payload with it, and encrypt the DEK with the KEK."""
        if not isinstance(payload, dict):
            return payload

        # 1. Generate unique DEK for this payload
        dek = os.urandom(32)
        dek_hex = dek.hex()
        
        # 2. Encrypt payload fields using the DEK
        dek_encryptor = FieldEncryptor(dek_hex)
        result = dek_encryptor.encrypt_payload(payload, fields)
        
        # 3. Encrypt the DEK using the KEK
        nonce = os.urandom(12)
        encrypted_dek = self.kek_aesgcm.encrypt(nonce, dek, None)
        encoded_encrypted_dek = base64.b64encode(nonce + encrypted_dek).decode('utf-8')
        
        # 4. Attach the encrypted DEK to the payload envelope
        result["__encrypted_dek"] = encoded_encrypted_dek
        return result

    def decrypt_payload(self, payload: Dict[str, Any], fields: list[str]) -> Dict[str, Any]:
        """Decrypt the DEK using the KEK, then decrypt the payload using the DEK."""
        if not isinstance(payload, dict) or "__encrypted_dek" not in payload:
            return payload

        # 1. Decrypt the DEK using the KEK
        raw_dek_data = base64.b64decode(payload["__encrypted_dek"])
        nonce = raw_dek_data[:12]
        ct = raw_dek_data[12:]
        try:
            dek = self.kek_aesgcm.decrypt(nonce, ct, None)
        except Exception as e:
            raise ValueError(f"Failed to unwrap DEK: {e}")
            
        # 2. Decrypt payload fields using the DEK
        dek_hex = dek.hex()
        dek_encryptor = FieldEncryptor(dek_hex)
        result = dek_encryptor.decrypt_payload(payload, fields)
        
        # 3. Remove the envelope metadata
        result.pop("__encrypted_dek", None)
        return result

