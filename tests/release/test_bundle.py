import hashlib
import importlib.util
import json
import pathlib
import tempfile
import unittest
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("bundle_verifier", ROOT / "tools/release/verify.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class BundleTests(unittest.TestCase):
    def make(self, directory, alter=None):
        root = "ArduCore-test/"
        files = {"README.txt": b"Hardware unverified\n"}
        profiles = ("full", "uart", "distance", "temperature", "buzzer", "servo")
        for profile in profiles:
            for suffix in ("hex", "elf"):
                files[f"firmware/{profile}/arducore.ino.{suffix}"] = b"fixture"
        manifest = {"version": "test", "dirty": False, "source_commit": "a" * 40,
                    "hardware_verified": False,
                    "profiles": {name: {"id": i} for i, name in enumerate(profiles)},
                    "files": {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}}
        if alter:
            alter(files, manifest)
        path = pathlib.Path(directory) / "test.zip"
        with zipfile.ZipFile(path, "w") as bundle:
            for name, data in files.items():
                bundle.writestr(root + name, data)
            bundle.writestr(root + "manifest.json", json.dumps(manifest))
        path.with_suffix(".zip.sha256").write_text(hashlib.sha256(path.read_bytes()).hexdigest() + "  test.zip\n")
        return path

    def test_complete_bundle(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(verifier.verify(self.make(directory))["version"], "test")

    def test_tampered_payload_despite_updated_outer_checksum(self):
        def tamper(files, _):
            files["README.txt"] = b"tampered"
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "Payload SHA-256"):
            verifier.verify(self.make(directory, tamper))

    def test_outer_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make(directory)
            with path.open("ab") as out:
                out.write(b"changed")
            with self.assertRaisesRegex(ValueError, "Archive SHA-256"):
                verifier.verify(path)

    def test_unsafe_and_unmanifested_members(self):
        for name in ("../outside", "extra.txt"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                path = self.make(directory, lambda files, manifest: files.update({name: b"extra"}))
                with self.assertRaises(ValueError):
                    verifier.verify(path)

    def test_dirty_bundle_requires_explicit_development_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.make(directory, lambda files, manifest: manifest.update(dirty=True))
            with self.assertRaisesRegex(ValueError, "uncommitted"):
                verifier.verify(path)
            self.assertTrue(verifier.verify(path, allow_dirty=True)["dirty"])

    def test_missing_profile_or_artifact(self):
        for remove in ("profile", "artifact"):
            def alter(files, manifest):
                if remove == "profile":
                    del manifest["profiles"]["servo"]
                else:
                    del files["firmware/servo/arducore.ino.hex"]
                    del manifest["files"]["firmware/servo/arducore.ino.hex"]
            with self.subTest(remove=remove), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    verifier.verify(self.make(directory, alter))


if __name__ == "__main__":
    unittest.main()
