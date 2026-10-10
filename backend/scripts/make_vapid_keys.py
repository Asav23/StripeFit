"""Create the VAPID key pair for browser notifications and write it to backend/.env.

Run once from backend/:  python scripts/make_vapid_keys.py   (then restart the API)
It refuses to overwrite existing keys, because every browser subscribed with the old key would stop
getting notifications. Pass --force to replace them anyway (browsers then need to turn notifications
off and on again).
"""

import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

sys.path.insert(0, str(Path(__file__).resolve().parent))
from env_file import ENV_PATH, read_env_value, write_env_value  # noqa: E402


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def main() -> None:
    if not ENV_PATH.exists():
        sys.exit("backend/.env is missing. Copy .env.example to .env first.")
    if read_env_value("VAPID_PRIVATE_KEY") and "--force" not in sys.argv:
        sys.exit("VAPID keys already exist in backend/.env. Use --force to replace them.")
    key = ec.generate_private_key(ec.SECP256R1())
    public = key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    private = key.private_numbers().private_value.to_bytes(32, "big")
    write_env_value("VAPID_PUBLIC_KEY", b64url(public))
    write_env_value("VAPID_PRIVATE_KEY", b64url(private))
    print("Wrote VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY to backend/.env. Restart the API to use them.")


if __name__ == "__main__":
    main()
