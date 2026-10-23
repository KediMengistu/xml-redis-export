"""Turn parsed data into Redis keys and save them with an injected Redis client."""

import json

from app.xml_parser import ExportData

SUBDOMAINS_KEY = "subdomains"
COOKIE_PATTERN = "cookie:*"


def cookie_key(name: str, host: str) -> str:
    return f"cookie:{name}:{host}"


def build_keys(data: ExportData) -> dict[str, str]:
    """Map every Redis key to the string value it should hold."""
    keys = {SUBDOMAINS_KEY: json.dumps(data.subdomains)}
    for (name, host), value in data.cookies.items():
        keys[cookie_key(name, host)] = value
    return keys


def save(client, keys: dict[str, str]) -> None:
    """Replace all previously exported keys with `keys`.

    Old cookie keys are removed so that a cookie deleted from the XML also
    disappears from Redis; running the export twice gives the same result.
    The delete and the writes run in one MULTI/EXEC transaction, so readers
    never see a half-written export. (The SCAN for old keys happens just
    before the transaction; that is fine for a single-writer batch job.)
    """
    stale = list(client.scan_iter(match=COOKIE_PATTERN))
    pipe = client.pipeline(transaction=True)
    pipe.delete(SUBDOMAINS_KEY, *stale)
    pipe.mset(keys)
    pipe.execute()


def read_back(client, key_names: list[str]) -> dict[str, str | None]:
    """Fetch the current values of `key_names` from Redis."""
    return dict(zip(key_names, client.mget(key_names)))
