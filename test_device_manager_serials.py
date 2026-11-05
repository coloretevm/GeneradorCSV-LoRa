import copy
import unittest
from urllib.error import HTTPError

from device_manager_serials import FAMILY, fetch_combined, save_combined


def default():
    return {"families": {name: {"last_serial": 0} for name in ("RTU", "GW", "I-TIC", "TIC12", FAMILY)}}


class IsolatedRegistryTests(unittest.TestCase):
    def setUp(self):
        self.settings = {"api_url": "https://api.example/contents/serial_registry.json",
                         "registry_url": "https://raw.example/main/serial_registry.json"}
        self.documents = {"legacy": default(), FAMILY: default()}
        self.documents["legacy"]["families"]["RTU"]["last_serial"] = 7997
        self.writes = []

    def read(self, settings):
        key = settings.get("registry_family", "legacy")
        if key not in self.documents:
            raise HTTPError(settings["api_url"], 404, "Not Found", {}, None)
        return copy.deepcopy(self.documents[key])

    def write(self, settings, registry, message):
        key = settings.get("registry_family", "legacy")
        self.writes.append(key)
        self.documents[key] = copy.deepcopy(registry)

    def test_shared_counter_starts_at_zero(self):
        registry = fetch_combined(self.settings, self.read, default)
        self.assertEqual(registry["families"][FAMILY]["last_serial"], 0)
        self.assertEqual(registry["families"]["RTU"]["last_serial"], 7997)

    def test_old_clients_cannot_erase_new_counter(self):
        self.documents[FAMILY]["families"][FAMILY]["last_serial"] = 17
        self.documents["legacy"]["families"].pop(FAMILY)
        registry = fetch_combined(self.settings, self.read, default)
        self.assertEqual(registry["families"][FAMILY]["last_serial"], 17)

    def test_instant_write_leaves_existing_counters_untouched(self):
        registry = fetch_combined(self.settings, self.read, default)
        registry["families"][FAMILY]["last_serial"] = 5
        saved = save_combined(self.settings, registry, "test", self.read, self.write, default)
        self.assertEqual(self.writes, [FAMILY])
        self.assertEqual(saved["families"][FAMILY]["last_serial"], 5)
        self.assertEqual(saved["families"]["RTU"]["last_serial"], 7997)

    def test_legacy_write_leaves_instant_untouched(self):
        registry = fetch_combined(self.settings, self.read, default)
        registry["families"]["RTU"]["last_serial"] += 1
        save_combined(self.settings, registry, "test", self.read, self.write, default)
        self.assertEqual(self.writes, ["legacy"])

    def test_all_and_downward_admin_changes(self):
        self.documents[FAMILY]["families"][FAMILY]["last_serial"] = 20
        registry = fetch_combined(self.settings, self.read, default)
        registry["families"][FAMILY]["last_serial"] = 2
        registry["families"]["RTU"]["last_serial"] += 1
        saved = save_combined(self.settings, registry, "test", self.read, self.write, default)
        self.assertEqual(self.writes, ["legacy", FAMILY])
        self.assertEqual(saved["families"][FAMILY]["last_serial"], 2)

    def test_missing_new_registry_initializes_zero(self):
        del self.documents[FAMILY]
        self.assertEqual(fetch_combined(self.settings, self.read, default)["families"][FAMILY]["last_serial"], 0)

    def test_permission_errors_are_not_reset_to_zero(self):
        def read(settings):
            if settings.get("registry_family"):
                raise HTTPError(settings["api_url"], 403, "Forbidden", {}, None)
            return default()
        with self.assertRaises(HTTPError):
            fetch_combined(self.settings, read, default)


if __name__ == "__main__":
    unittest.main()
