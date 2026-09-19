from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import time
from threading import RLock
from tempfile import NamedTemporaryFile


class CacheError(RuntimeError):
    """Raised when a cache artifact cannot be safely stored or loaded."""


@dataclass(frozen=True, slots=True)
class CacheEntry:
    key: str
    path: Path
    size_bytes: int
    last_used: float


class ArtifactCache:
    """Content-addressed, size-bounded local artifact cache with LRU eviction."""

    def __init__(self, root: Path, *, max_bytes: int = 512 * 1024 * 1024) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be > 0")
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._metadata_path = self._root / "metadata.json"
        self._max_bytes = max_bytes
        self._lock = RLock()
        self._metadata: dict[str, dict[str, float | int]] = self._load_metadata()

    def get(self, key: str) -> bytes | None:
        self._validate_key(key)
        with self._lock:
            entry = self._metadata.get(key)
            if entry is None:
                return None
            path = self._path_for(key)
            try:
                data = path.read_bytes()
            except FileNotFoundError:
                self._metadata.pop(key, None)
                self._save_metadata_locked()
                return None
            expected_size = int(entry["size_bytes"])
            if len(data) != expected_size or _sha256(data) != key:
                raise CacheError("cache entry integrity check failed")
            self._touch_locked(key)
            return data

    def put(self, data: bytes) -> CacheEntry:
        key = _sha256(data)
        with self._lock:
            target = self._path_for(key)
            if not target.exists():
                with NamedTemporaryFile(
                    mode="wb",
                    dir=self._root,
                    prefix=".cache-",
                    delete=False,
                ) as tmp:
                    temp_path = Path(tmp.name)
                    tmp.write(data)
                    tmp.flush()

                try:
                    temp_path.replace(target)
                finally:
                    temp_path.unlink(missing_ok=True)

            self._metadata[key] = {
                "size_bytes": len(data),
                "last_used": time.time(),
            }
            self._evict_locked(exclude={key})
            self._save_metadata_locked()
            entry = self._metadata.get(key)
            if entry is None:
                raise CacheError("cache entry was evicted immediately")
            return CacheEntry(
                key=key,
                path=target,
                size_bytes=int(entry["size_bytes"]),
                last_used=float(entry["last_used"]),
            )

    def remove(self, key: str) -> bool:
        self._validate_key(key)
        with self._lock:
            existed = key in self._metadata or self._path_for(key).exists()
            self._metadata.pop(key, None)
            self._path_for(key).unlink(missing_ok=True)
            self._save_metadata_locked()
            return existed

    def total_bytes(self) -> int:
        with self._lock:
            return sum(int(item["size_bytes"]) for item in self._metadata.values())

    def keys(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(sorted(self._metadata))

    def evict(self) -> tuple[str, ...]:
        with self._lock:
            removed = self._evict_locked()
            self._save_metadata_locked()
            return tuple(removed)

    def _evict_locked(self, *, exclude: set[str] | None = None) -> list[str]:
        excluded = exclude or set()
        removed: list[str] = []
        while self.total_bytes() > self._max_bytes:
            candidates = [
                (key, float(item["last_used"]))
                for key, item in self._metadata.items()
                if key not in excluded
            ]
            if not candidates:
                break
            key, _ = min(candidates, key=lambda item: (item[1], item[0]))
            self._metadata.pop(key, None)
            self._path_for(key).unlink(missing_ok=True)
            removed.append(key)
        return removed

    def _touch_locked(self, key: str) -> None:
        self._metadata[key]["last_used"] = time.time()
        self._save_metadata_locked()

    def _path_for(self, key: str) -> Path:
        return self._root / key

    def _load_metadata(self) -> dict[str, dict[str, float | int]]:
        if not self._metadata_path.exists():
            return {}
        try:
            payload = json.loads(self._metadata_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError
            return {
                str(key): {
                    "size_bytes": int(value["size_bytes"]),
                    "last_used": float(value["last_used"]),
                }
                for key, value in payload.items()
                if isinstance(value, dict)
            }
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            raise CacheError("cache metadata is invalid") from exc

    def _save_metadata_locked(self) -> None:
        payload = json.dumps(self._metadata, sort_keys=True, separators=(",", ":"))
        temp = self._metadata_path.with_suffix(".tmp")
        temp.write_text(payload, encoding="utf-8")
        temp.replace(self._metadata_path)

    @staticmethod
    def _validate_key(key: str) -> None:
        if len(key) != 64 or any(ch not in "0123456789abcdef" for ch in key):
            raise CacheError("cache key must be a lowercase SHA-256 digest")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
