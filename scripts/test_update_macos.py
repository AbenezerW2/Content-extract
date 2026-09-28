import importlib.util
from pathlib import Path
import plistlib
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("updater", Path(__file__).with_name("update_macos.py"))
updater = importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def bundle(self, name, marker):
        app = self.root / name
        (app / "Contents/MacOS").mkdir(parents=True)
        (app / "Contents/MacOS/Content Extract").write_text(marker)
        (app / "Contents/Info.plist").write_bytes(plistlib.dumps({
            "CFBundleIdentifier": updater.APP_ID, "CFBundleExecutable": "Content Extract"}))
        return app

    def test_swap_keeps_previous_app_for_rollback(self):
        old = self.bundle("Content Extract.app", "old")
        new = self.bundle("staged.app", "new")
        backup = self.root / "backup.app"
        self.assertEqual(updater.replace_app(new, old, backup), backup)
        self.assertEqual((old / "Contents/MacOS/Content Extract").read_text(), "new")
        self.assertEqual((backup / "Contents/MacOS/Content Extract").read_text(), "old")

    def test_failed_swap_restores_original(self):
        old = self.bundle("Content Extract.app", "old")
        new = self.bundle("staged.app", "new")
        original = Path.rename
        def rename(path, target):
            if path == new:
                raise OSError("simulated installation failure")
            return original(path, target)
        with patch.object(Path, "rename", rename), self.assertRaises(OSError):
            updater.replace_app(new, old, self.root / "backup.app")
        self.assertEqual((old / "Contents/MacOS/Content Extract").read_text(), "old")

    def test_existing_backup_is_not_overwritten(self):
        old = self.bundle("Content Extract.app", "old")
        new = self.bundle("staged.app", "new")
        backup = self.bundle("backup.app", "previous")
        with self.assertRaises(FileExistsError):
            updater.replace_app(new, old, backup)
        self.assertEqual((old / "Contents/MacOS/Content Extract").read_text(), "old")

    def test_unrelated_app_is_rejected(self):
        app = self.bundle("Content Extract.app", "other")
        (app / "Contents/Info.plist").write_bytes(plistlib.dumps({"CFBundleIdentifier": "other.app"}))
        with self.assertRaises(ValueError):
            updater.app_info(app)

    def test_dirty_checkout_is_preserved(self):
        checkout = self.root / "source"
        checkout.mkdir()
        with patch.object(updater, "run", side_effect=["v2.2", updater.REPOSITORY, " M important.py"]) as run:
            with self.assertRaisesRegex(ValueError, "local changes"):
                updater.prepare_checkout(checkout, "v2.2")
            self.assertFalse(any("fetch" in call.args for call in run.call_args_list))

    def test_signature_failure_keeps_installed_app(self):
        old = self.bundle("Content Extract.app", "old")
        new = self.bundle("built.app", "new")
        import shutil
        def run(*args, **kwargs):
            if args[0] == "ditto":
                shutil.copytree(args[1], args[2])
            else:
                raise subprocess.CalledProcessError(1, args)
        with patch.object(updater, "run", side_effect=run), self.assertRaises(subprocess.CalledProcessError):
            updater.install_app(new, old)
        self.assertEqual((old / "Contents/MacOS/Content Extract").read_text(), "old")
        self.assertFalse(list(self.root.glob(".content-extract-update-*")))


if __name__ == "__main__":
    unittest.main()
