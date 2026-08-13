from pathlib import Path
from packages.storage.base import StorageBackend


class LocalStorage(StorageBackend):
    def __init__(self, root: str = "uploads"):
        self.root = Path(root)

    def _safe(self, path: str) -> Path:
        candidate = (self.root / path).resolve()
        root = self.root.resolve()
        if root != candidate and root not in candidate.parents:
            raise ValueError("Invalid storage path")
        return candidate

    def put(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        p = self._safe(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def get(self, path: str) -> bytes:
        return self._safe(path).read_bytes()

    def delete(self, path: str) -> None:
        p = self._safe(path)
        if p.exists():
            p.unlink()
