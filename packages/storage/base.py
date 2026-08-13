from abc import ABC, abstractmethod


class StorageBackend(ABC):
    @abstractmethod
    def put(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None: ...

    @abstractmethod
    def get(self, path: str) -> bytes: ...

    @abstractmethod
    def delete(self, path: str) -> None: ...
