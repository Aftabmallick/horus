# Module: `agent_tracer_plus.security.encryption`

AES-256-GCM field encryption for payloads.

## Class `FieldEncryptor`
Encrypt specific fields in span payloads at rest.

Requires `cryptography` package.

### `def __init__(self, key)`
### `def encrypt_value(self, value)`
Serialize and encrypt any JSON-serializable value using AES-256-GCM.

### `def decrypt_value(self, encrypted_str)`
Decrypt and deserialize a value using AES-256-GCM.

### `def encrypt_payload(self, payload, fields)`
Encrypt specific keys in a dictionary payload.

### `def decrypt_payload(self, payload, fields)`
Decrypt specific keys in a dictionary payload.

## Class `KeyManager`
Manages AES-256 encryption keys with rotation and environment loading.

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

### `def __init__(self, key_hex)`
### `def generate_key()`
Generate a cryptographically strong 256-bit key as a hex string.

### `def from_env(cls, env_var)`
Load a key from an environment variable.

Raises:
    ValueError: If the env var is not set or is not a valid 256-bit hex key.

### `def get_encryptor(self)`
Return the current FieldEncryptor instance.

### `def rotate_key(self, new_key_hex, payloads, encrypted_fields)`
Re-encrypt all payloads from the current key to a new key.

Args:
    new_key_hex: New 64-char hex key.
    payloads: List of payload dicts containing encrypted fields.
    encrypted_fields: Field names that are currently encrypted.

Returns:
    List of payloads with fields re-encrypted under the new key.

## Class `KMSKeyProvider`
Abstract interface for fetching keys from cloud KMS providers.

Subclass this to implement AWS KMS, GCP Cloud KMS, or Azure Key Vault.

Example::

    class AWSKMSProvider(KMSKeyProvider):
        def fetch_key(self, key_id: str) -&gt; str:
            import boto3
            client = boto3.client("kms")
            response = client.generate_data_key(KeyId=key_id, KeySpec="AES_256")
            return response["Plaintext"].hex()

### `def fetch_key(self, key_id)`
Fetch a 256-bit key (hex) from the KMS provider.

Args:
    key_id: Provider-specific key identifier (e.g., ARN, resource name).

Returns:
    64-character hex string representing the 256-bit key.

Raises:
    NotImplementedError: Must be overridden by subclasses.

### `def to_key_manager(self, key_id)`
Convenience: fetch key and wrap in a KeyManager.

## Class `EnvelopeEncryptor`
True Envelope Encryption using a KMS provider to encrypt Data Encryption Keys (DEKs).

### `def __init__(self, kms_provider, kek_id)`
### `def encrypt_payload(self, payload, fields)`
Generate a random DEK, encrypt the payload with it, and encrypt the DEK with the KEK.

### `def decrypt_payload(self, payload, fields)`
Decrypt the DEK using the KEK, then decrypt the payload using the DEK.

