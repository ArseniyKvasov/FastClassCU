"""One-off helper: generate the RS256 key pair auth-service signs JWTs with.

Run once per deployment: python scripts/generate_keys.py
Never commit the private key — keys/ is gitignored.
"""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> None:
    keys_dir = Path(__file__).resolve().parent.parent / "keys"
    keys_dir.mkdir(exist_ok=True)

    private_path = keys_dir / "private.pem"
    public_path = keys_dir / "public.pem"

    if private_path.exists() or public_path.exists():
        print("Keys already exist, refusing to overwrite.")
        return

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    private_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    public_path.write_bytes(
        private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"Wrote {private_path} and {public_path}")


if __name__ == "__main__":
    main()
