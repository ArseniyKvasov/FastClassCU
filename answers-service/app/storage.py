import hashlib
from pathlib import Path

from app.config import settings


class LocalStorage:
    """Content-addressable blob store - same mechanism as Content Service's
    LocalStorage, deliberately not shared code: answer files (voice
    recordings) have a different owner/lifecycle than lesson materials, even
    though the storage trick is identical."""

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, sha256: str) -> Path:
        return self.root / sha256[:2] / sha256

    def save(self, data: bytes) -> tuple[str, str, int]:
        sha256 = hashlib.sha256(data).hexdigest()
        path = self._path(sha256)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        storage_key = f"{sha256[:2]}/{sha256}"
        return sha256, storage_key, len(data)

    def read(self, storage_key: str) -> bytes:
        return (self.root / storage_key).read_bytes()

    def delete(self, storage_key: str) -> None:
        path = self.root / storage_key
        if path.exists():
            path.unlink()

    def exists(self, storage_key: str) -> bool:
        return (self.root / storage_key).exists()


storage = LocalStorage()
