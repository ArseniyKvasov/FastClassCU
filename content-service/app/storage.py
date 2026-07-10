import hashlib
from pathlib import Path

from app.config import settings


class LocalStorage:
    """Content-addressable blob store. The key IS the content hash, so writing
    the same bytes twice is idempotent and never duplicates on disk - this is
    the file-level counterpart to task-content dedup. Swappable for S3/GCS
    later behind the same three methods; nothing else in the service touches
    the filesystem directly (unlike the old clone code's raw shutil.copy2)."""

    def __init__(self, root: str | None = None) -> None:
        self.root = Path(root or settings.storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, sha256: str) -> Path:
        # Shard by first 2 hex chars to avoid one giant flat directory.
        return self.root / sha256[:2] / sha256

    def save(self, data: bytes) -> tuple[str, str, int]:
        """Returns (sha256, storage_key, size_bytes)."""
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
