import hashlib
import io
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from core.runtime.stager import (
    CapabilityStager,
    StageError,
    StagingPolicy,
    UrlLibArchiveTransport,
)
from registry import ArtifactSpec, CapabilityManifest, GitHubSourceResolver


def make_archive(*entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for entry in entries:
            name, kind, payload = entry
            if kind == "dir":
                info = tarfile.TarInfo(name)
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
            elif kind == "file":
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
            elif kind == "symlink":
                info = tarfile.TarInfo(name)
                info.type = tarfile.SYMTYPE
                info.linkname = payload.decode()
                archive.addfile(info)
            elif kind == "hardlink":
                info = tarfile.TarInfo(name)
                info.type = tarfile.LNKTYPE
                info.linkname = payload.decode()
                archive.addfile(info)
            else:
                raise AssertionError(kind)
    return stream.getvalue()


class FakeTransport:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def download(self, url, destination, *, max_bytes, timeout_seconds):
        self.calls.append((url, destination, max_bytes, timeout_seconds))
        if len(self.payload) > max_bytes:
            raise StageError("fake payload exceeds configured limit")
        destination.write_bytes(self.payload)
        return len(self.payload)


class CapabilityStagerTests(unittest.TestCase):
    def setUp(self):
        self.resolver = GitHubSourceResolver()
        self.commit = "a" * 40
        self.base_manifest = CapabilityManifest(
            capability_id="browser.form_fill",
            version="1.0.0",
            description="Fill form fields.",
            artifact=ArtifactSpec(
                repository_url="https://github.com/example/form-fill",
                pinned_commit=self.commit,
                subdirectory="src",
            ),
        )

    def test_stages_verified_source_and_removes_archive(self):
        payload = make_archive(
            ("form-fill-aaa/", "dir", b""),
            ("form-fill-aaa/src/", "dir", b""),
            ("form-fill-aaa/src/main.py", "file", b"print('ok')"),
            ("form-fill-aaa/README.md", "file", b"ok"),
        )
        manifest = CapabilityManifest(
            capability_id=self.base_manifest.capability_id,
            version=self.base_manifest.version,
            description=self.base_manifest.description,
            artifact=ArtifactSpec(
                repository_url=self.base_manifest.artifact.repository_url,
                pinned_commit=self.commit,
                sha256=hashlib.sha256(payload).hexdigest(),
                subdirectory="src",
            ),
        )
        transport = FakeTransport(payload)
        stager = CapabilityStager(
            self.resolver,
            transport,
            StagingPolicy(
                max_download_bytes=1024 * 1024,
                max_extracted_bytes=1024 * 1024,
            ),
        )

        with TemporaryDirectory() as temp:
            workdir = Path(temp)
            plan = self.resolver.resolve(manifest)
            staged = stager.stage(manifest, plan, workdir)

            self.assertEqual(staged.capability_id, manifest.capability_id)
            self.assertEqual(staged.pinned_commit, self.commit)
            self.assertEqual(staged.target_path.name, "src")
            self.assertEqual(
                (staged.target_path / "main.py").read_text(),
                "print('ok')",
            )
            self.assertEqual(staged.downloaded_bytes, len(payload))
            self.assertEqual(staged.sha256, hashlib.sha256(payload).hexdigest())
            self.assertTrue(staged.repository_root.exists())
            self.assertFalse(
                any(path.name == ".source-archive.tar.gz" for path in workdir.iterdir())
            )

        self.assertEqual(len(transport.calls), 1)

    def test_rejects_checksum_mismatch_and_cleans_source(self):
        payload = make_archive(("form-fill-aaa/", "dir", b""))
        manifest = CapabilityManifest(
            capability_id=self.base_manifest.capability_id,
            version=self.base_manifest.version,
            description=self.base_manifest.description,
            artifact=ArtifactSpec(
                repository_url=self.base_manifest.artifact.repository_url,
                pinned_commit=self.commit,
                sha256="b" * 64,
                subdirectory="",
            ),
        )
        stager = CapabilityStager(self.resolver, FakeTransport(payload))

        with TemporaryDirectory() as temp:
            workdir = Path(temp)
            plan = self.resolver.resolve(manifest)
            with self.assertRaisesRegex(StageError, "checksum"):
                stager.stage(manifest, plan, workdir)
            self.assertFalse((workdir / "source").exists())
            self.assertFalse((workdir / ".source-archive.tar.gz").exists())

    def test_rejects_tampered_source_plan(self):
        payload = make_archive(("form-fill-aaa/", "dir", b""))
        stager = CapabilityStager(self.resolver, FakeTransport(payload))

        with TemporaryDirectory() as temp:
            workdir = Path(temp)
            plan = self.resolver.resolve(self.base_manifest)
            tampered = type(plan)(
                capability_id=plan.capability_id,
                repository_url=plan.repository_url,
                pinned_commit=plan.pinned_commit,
                archive_url=(
                    "https://github.com/attacker/evil/archive/"
                    + self.commit
                    + ".tar.gz"
                ),
                clone_url=plan.clone_url,
                subdirectory=plan.subdirectory,
                partial_clone_command=plan.partial_clone_command,
                sparse_checkout_command=plan.sparse_checkout_command,
            )
            with self.assertRaisesRegex(StageError, "source plan"):
                stager.stage(self.base_manifest, tampered, workdir)

    def test_rejects_symlink_and_path_traversal_archives(self):
        payloads = [
            make_archive(
                ("form-fill-aaa/", "dir", b""),
                ("form-fill-aaa/link", "symlink", b"/tmp/pwn"),
            ),
            make_archive(("../escape.txt", "file", b"bad")),
        ]

        for payload in payloads:
            with self.subTest():
                stager = CapabilityStager(
                    self.resolver,
                    FakeTransport(payload),
                )
                with TemporaryDirectory() as temp:
                    plan = self.resolver.resolve(self.base_manifest)
                    with self.assertRaises(StageError):
                        stager.stage(self.base_manifest, plan, Path(temp))
                    self.assertFalse(Path(temp, "source").exists())

    def test_rejects_extracted_size_limit(self):
        payload = make_archive(
            ("form-fill-aaa/", "dir", b""),
            ("form-fill-aaa/big.bin", "file", b"x" * 2048),
        )
        stager = CapabilityStager(
            self.resolver,
            FakeTransport(payload),
            StagingPolicy(
                max_download_bytes=1024 * 1024,
                max_extracted_bytes=1024,
            ),
        )
        with TemporaryDirectory() as temp:
            manifest = CapabilityManifest(
                capability_id=self.base_manifest.capability_id,
                version=self.base_manifest.version,
                description=self.base_manifest.description,
                artifact=ArtifactSpec(
                    repository_url=self.base_manifest.artifact.repository_url,
                    pinned_commit=self.commit,
                ),
            )
            plan = self.resolver.resolve(manifest)
            with self.assertRaisesRegex(StageError, "extracted-size"):
                stager.stage(manifest, plan, Path(temp))
            self.assertFalse(Path(temp, "source").exists())

    def test_rejects_download_urls_outside_github_https(self):
        with self.assertRaises(StageError):
            UrlLibArchiveTransport().download(
                "http://github.com/example/form-fill/archive/"
                + self.commit
                + ".tar.gz",
                Path("/tmp/super-ai-test-download"),
                max_bytes=1024,
                timeout_seconds=1,
            )

        with self.assertRaises(StageError):
            UrlLibArchiveTransport().download(
                "https://evil.example/archive/"
                + self.commit
                + ".tar.gz",
                Path("/tmp/super-ai-test-download"),
                max_bytes=1024,
                timeout_seconds=1,
            )

    def test_policy_rejects_invalid_limits(self):
        with self.assertRaises(ValueError):
            StagingPolicy(max_download_bytes=0).validate()
        with self.assertRaises(ValueError):
            StagingPolicy(max_extracted_bytes=0).validate()
        with self.assertRaises(ValueError):
            StagingPolicy(max_members=0).validate()


if __name__ == "__main__":
    unittest.main()
