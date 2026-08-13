import pytest
from packages.storage.local import LocalStorage


def test_local_storage_round_trip(tmp_path):
    s=LocalStorage(str(tmp_path))
    s.put("w/d/file.txt",b"hello","text/plain")
    assert s.get("w/d/file.txt")==b"hello"
    s.delete("w/d/file.txt")
    assert not (tmp_path/"w/d/file.txt").exists()


def test_local_storage_blocks_traversal(tmp_path):
    s=LocalStorage(str(tmp_path))
    with pytest.raises(ValueError):
        s.put("../escape.txt",b"x")
