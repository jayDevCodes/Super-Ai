from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import time
from typing import Protocol
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from registry.manifest import CapabilityManifest
from registry.resolver import GitHubSourceResolver, SourcePlan


class StageError(RuntimeError):
    """Raised when a capability source cannot be staged safely."""


@dataclass(frozen=True, slots=True)
class StagingPolicy:
    """Network and storage limits for one capability source staging operation."""

    max_download_bytes: int = 64 * 1024 * 1024
    max_extracted_bytes: int = 256 * 1024 * 1024
    max_members: int = 20_000
    download_timeout_seconds: float = 60.0

    def validate(self) -> None:
        if self.max_download_bytes <= 0:
            raise ValueError("max_download_bytes must be > 0")
        if self.max_extracted_bytes <= 0:
            raise ValueError("max_extracted_bytes must be > 0")
        if self.max_members <= 0:
            raise ValueError("max_members must be > 0")
        if self.download_timeout_seconds <= 0:
            raise ValueError("download_timeout_seconds must be > 0")


@dataclass(frozen=True, slots=True)
class StagedArtifact:
    """Verified source tree produced by the stager."""

    capability_id: str
    pinned_commit: str
    repository_root: Path
    target_path: Path
    downloaded_bytes: int
    extracted_bytes: int
    sha256: str


class ArchiveTransport(Protocol):
    """Minimal transport boundary used by the secure stager."""

    def download(
        self,
        url: str,
        destination: Path,
        *,
        max_bytes: int,
        timeout_seconds: float,
    ) -> int:
        ...


_ALLOWED_DOWNLOAD_HOSTS = frozenset({"github.com", "codeload.github.com"})


def _validate_download_url(url: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.hostname.lower() not in _ALLOWED_DOWNLOAD_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise StageError(
            "download URL must be HTTPS GitHub without credentials/query/fragment"
        )
    if parsed.port not in (None, 443):
        raise StageError("download URL must use the HTTPS default port")


class _SafeRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_download_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrlLibArchiveTransport:
    """HTTPS-only GitHub archive downloader with bounded redirects and size."""

    _USER_AGENT = "Super-Ai-capability-stager/1"

    def download(
        self,
        url: str,
        destination: Path,
        *,
        max_bytes: int,
        timeout_seconds: float,
    ) -> int:
        _validate_download_url(url)
        destination = Path(destination)
        if destination.exists() or destination.is_symlink():
            raise StageError(f"download destination already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)

        opener = build_opener(_SafeRedirectHandler())
        request = Request(
            url,
            headers={
                "Accept": "application/gzip, application/octet-stream",
                "User-Agent": self._USER_AGENT,
            },
        )
        started = time.monotonic()

        try:
            with opener.open(request, timeout=timeout_seconds) as response:
                _validate_download_url(response.geturl())
                content_length = response.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        if int(content_length) > max_bytes:
                            raise StageError(
                                f"archive exceeds download limit: {content_length} > {max_bytes} bytes"
                            )
                    except ValueError as exc:
                        raise StageError("invalid Content-Length header") from exc

                downloaded = 0
                with destination.open("wb") as output:
                    while True:
                        if time.monotonic() - started > timeout_seconds:
                            raise StageError("archive download exceeded timeout")
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        downloaded += len(chunk)
                        if downloaded > max_bytes:
                            raise StageError(
                                f"archive exceeds download limit: {downloaded} > {max_bytes} bytes"
                            )
                        output.write(chunk)
                return downloaded
        except StageError:
            destination.unlink(missing_ok=True)
            raise
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise StageError("archive download failed") from exc


class CapabilityStager:
    """Fetch, verify, and safely extract one immutable capability source.

    This component never imports, executes, or installs the staged source.
    Execution and OS-level sandboxing belong to later runtime boundaries.
    """

    def __init__(
        self,
        resolver: GitHubSourceResolver,
        transport: ArchiveTransport,
        policy: StagingPolicy | None = None,
    ) -> None:
        self._resolver = resolver
        self._transport = transport
        self._policy = policy or StagingPolicy()
        self._policy.validate()

    def stage(
        self,
        manifest: CapabilityManifest,
        plan: SourcePlan,
        workdir: Path,
    ) -> StagedArtifact:
        manifest.validate()
        expected = self._resolver.resolve(manifest)
        if plan != expected:
            raise StageError("source plan does not match the validated manifest")

        workdir = Path(workdir)
        if not workdir.exists() or not workdir.is_dir() or workdir.is_symlink():
            raise StageError("workdir must be an existing, non-symlink directory")

        staging_root = workdir / "source"
        archive_path: Path | None = None

        try:
            staging_root.mkdir()
            archive_path = workdir / ".source-archive.tar.gz"
            if archive_path.exists() or archive_path.is_symlink():
                raise StageError("temporary archive path already exists")

            downloaded_bytes = self._transport.download(
                plan.archive_url,
                archive_path,
                max_bytes=self._policy.max_download_bytes,
                timeout_seconds=self._policy.download_timeout_seconds,
            )
            actual_size = archive_path.stat().st_size
            if downloaded_bytes != actual_size:
                raise StageError("transport byte count does not match archive size")

            digest = _sha256_file(archive_path)
            expected_sha256 = manifest.artifact.sha256
            if expected_sha256 is not None and digest.lower() != expected_sha256.lower():
                raise StageError("archive sha256 checksum mismatch")

            repository_root, extracted_bytes = _safe_extract(
                archive_path,
                staging_root,
                max_extracted_bytes=self._policy.max_extracted_bytes,
                max_members=self._policy.max_members,
            )

            target_path = repository_root / manifest.artifact.subdirectory
            if (
                not target_path.exists()
                or not target_path.is_dir()
                or target_path.is_symlink()
            ):
                raise StageError(
                    "declared capability subdirectory is not a directory"
                )

            root_resolved = repository_root.resolve()
            target_resolved = target_path.resolve()
            if (
                target_resolved != root_resolved
                and root_resolved not in target_resolved.parents
            ):
                raise StageError(
                    "declared capability subdirectory escapes the repository root"
                )

            return StagedArtifact(
                capability_id=manifest.capability_id,
                pinned_commit=manifest.artifact.pinned_commit,
                repository_root=repository_root,
                target_path=target_path,
                downloaded_bytes=downloaded_bytes,
                extracted_bytes=extracted_bytes,
                sha256=digest,
            )
        except StageError:
            shutil.rmtree(staging_root, ignore_errors=True)
            raise
        except Exception as exc:
            shutil.rmtree(staging_root, ignore_errors=True)
            raise StageError("capability source staging failed") from exc
        finally:
            if archive_path is not None:
                archive_path.unlink(missing_ok=True)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_archive_member_path(name: str) -> PurePosixPath:
    if "\x00" in name:
        raise StageError("archive member contains a NUL byte")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise StageError(f"unsafe archive member path: {name!r}")
    return path


def _safe_extract(
    archive_path: Path,
    destination: Path,
    *,
    max_extracted_bytes: int,
    max_members: int,
) -> tuple[Path, int]:
    try:
        archive = tarfile.open(archive_path, mode="r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise StageError("invalid gzip tar archive") from exc

    extracted_bytes = 0
    root_names: set[str] = set()

    with archive:
        members = archive.getmembers()
        if len(members) > max_members:
            raise StageError("archive contains too many members")

        for member in members:
            safe_path = _safe_archive_member_path(member.name)
            root_names.add(safe_path.parts[0])

            if member.islnk() or member.issym():
                raise StageError(
                    "symbolic and hard links are not allowed in capability archives"
                )
            if member.ischr() or member.isblk() or member.isfifo():
                raise StageError(
                    "special filesystem entries are not allowed in capability archives"
                )

            if member.size < 0:
                raise StageError("archive member has a negative size")

            if member.isreg() and member.size > (
                max_extracted_bytes - extracted_bytes
            ):
                raise StageError("archive exceeds extracted-size limit")

            target = destination.joinpath(*safe_path.parts)
            if not _is_within(destination, target):
                raise StageError(
                    f"archive member escapes staging directory: {member.name!r}"
                )

            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue

            if not member.isreg():
                raise StageError(
                    f"unsupported archive member type: {member.name!r}"
                )

            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() or target.is_symlink():
                raise StageError(
                    f"archive contains duplicate output path: {member.name!r}"
                )

            source = archive.extractfile(member)
            if source is None:
                raise StageError(f"cannot read archive member: {member.name!r}")

            written_for_member = 0
            with source, target.open("wb") as output:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    written_for_member += len(chunk)
                    extracted_bytes += len(chunk)
                    if (
                        written_for_member > member.size
                        or extracted_bytes > max_extracted_bytes
                    ):
                        raise StageError("archive extracted-size limit exceeded")
                    output.write(chunk)

            if written_for_member != member.size:
                raise StageError(
                    f"archive member size mismatch: {member.name!r}"
                )

    if len(root_names) != 1:
        raise StageError(
            "capability archive must contain exactly one top-level directory"
        )

    repository_root = destination / next(iter(root_names))
    if not repository_root.is_dir() or repository_root.is_symlink():
        raise StageError("archive top-level entry must be a directory")

    return repository_root, extracted_bytes


def _is_within(root: Path, child: Path) -> bool:
    root_resolved = root.resolve()
    child_resolved = child.resolve()
    return child_resolved == root_resolved or root_resolved in child_resolved.parents
