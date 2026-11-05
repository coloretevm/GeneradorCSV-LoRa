"""Keep the new Istantaneo counter safe from older Device Manager clients."""

from urllib.error import HTTPError


FAMILY = "Istantaneo"
REGISTRY_FILE = "serial_registry_istantaneo.json"


def instant_settings(settings):
    result = dict(settings)
    for key in ("api_url", "registry_url"):
        result[key] = settings[key].rsplit("/", 1)[0] + "/" + REGISTRY_FILE
    result["registry_file"] = REGISTRY_FILE
    result["registry_family"] = FAMILY
    return result


def read_instant(settings, read_single, default_registry):
    try:
        return read_single(instant_settings(settings))
    except HTTPError as error:
        if error.code != 404:
            raise
        return default_registry()


def fetch_combined(settings, read_single, default_registry):
    registry = read_single(settings)
    instant = read_instant(settings, read_single, default_registry)
    registry["families"][FAMILY] = instant["families"][FAMILY]
    return registry


def save_combined(settings, registry, message, read_single, write_single, default_registry):
    current = fetch_combined(settings, read_single, default_registry)
    legacy = {key: value for key, value in registry["families"].items() if key != FAMILY}
    current_legacy = {key: value for key, value in current["families"].items() if key != FAMILY}
    if legacy != current_legacy:
        write_single(settings, registry, message)
    if registry["families"][FAMILY] != current["families"][FAMILY]:
        write_single(instant_settings(settings), registry, message)
    return fetch_combined(settings, read_single, default_registry)
