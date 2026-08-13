import httpx
from packages.storage.base import StorageBackend


class SupabaseStorage(StorageBackend):
    def __init__(self, url: str, secret_key: str, bucket: str):
        if not (url and secret_key and bucket):
            raise ValueError("Supabase storage configuration is incomplete")
        self.base = url.rstrip("/")
        self.key = secret_key
        self.bucket = bucket

    @property
    def headers(self) -> dict[str, str]:
        return {"apikey": self.key, "Authorization": f"Bearer {self.key}"}

    def put(self, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        with httpx.Client(timeout=60) as client:
            r = client.post(
                f"{self.base}/storage/v1/object/{self.bucket}/{path}",
                headers={**self.headers, "Content-Type": content_type, "x-upsert": "false"},
                content=data,
            )
            r.raise_for_status()

    def get(self, path: str) -> bytes:
        with httpx.Client(timeout=60) as client:
            r = client.get(
                f"{self.base}/storage/v1/object/authenticated/{self.bucket}/{path}",
                headers=self.headers,
            )
            r.raise_for_status()
            return r.content

    def delete(self, path: str) -> None:
        with httpx.Client(timeout=60) as client:
            r = client.delete(
                f"{self.base}/storage/v1/object/{self.bucket}",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"prefixes": [path]},
            )
            r.raise_for_status()
