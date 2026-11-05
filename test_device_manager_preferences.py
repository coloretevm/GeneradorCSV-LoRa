import json
from pathlib import Path
import tempfile
import unittest

from device_manager_ui import load_guided_preferences, THEME_DEFAULT_POLICY


class StartupThemeTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="DeviceManager_theme_")
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "guided_ui_settings.json"

    def save(self, value):
        self.path.write_text(json.dumps(value), encoding="utf-8")
        return load_guided_preferences(self.path)

    def test_fresh_install_starts_dark_in_italian(self):
        preferences = load_guided_preferences(self.path)
        self.assertEqual(preferences["theme"], "dark")
        self.assertEqual(preferences["language"], "it")

    def test_v128_light_default_migrates_to_dark(self):
        preferences = self.save({"theme": "light", "language": "es"})
        self.assertEqual(preferences["theme"], "dark")
        self.assertEqual(preferences["language"], "es")

    def test_v128_dark_setting_stays_dark(self):
        self.assertEqual(self.save({"theme": "dark", "language": "it"})["theme"], "dark")

    def test_new_explicit_light_choice_is_remembered(self):
        preferences = self.save({"theme": "light", "language": "en", "theme_default_policy": THEME_DEFAULT_POLICY})
        self.assertEqual(preferences["theme"], "light")
        self.assertEqual(preferences["language"], "en")

    def test_new_explicit_dark_choice_is_remembered(self):
        self.assertEqual(self.save({"theme": "dark", "theme_default_policy": THEME_DEFAULT_POLICY})["theme"], "dark")

    def test_bad_settings_use_safe_defaults(self):
        for saved in ([], None, "light", {"theme": "invalid", "language": "unknown", "theme_default_policy": THEME_DEFAULT_POLICY}):
            with self.subTest(saved=saved):
                self.assertEqual(self.save(saved)["theme"], "dark")
                self.assertEqual(load_guided_preferences(self.path)["language"], "it")
        self.path.write_text("{invalid", encoding="utf-8")
        self.assertEqual(load_guided_preferences(self.path)["theme"], "dark")

    def test_migration_does_not_modify_the_settings_file(self):
        old = '{"theme":"light","language":"it"}'
        self.path.write_text(old, encoding="utf-8")
        load_guided_preferences(self.path)
        self.assertEqual(self.path.read_text(encoding="utf-8"), old)


if __name__ == "__main__":
    unittest.main()
