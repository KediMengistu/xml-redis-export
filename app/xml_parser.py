"""Read the XML config into plain Python data. Knows nothing about Redis."""

from dataclasses import dataclass, field

import defusedxml.ElementTree as SafeET
from defusedxml import DefusedXmlException


class ConfigError(Exception):
    """The XML file is missing, unreadable, malformed or not shaped as expected."""


@dataclass
class ExportData:
    subdomains: list[str]
    # (cookie name, cookie host) -> cookie value, in file order
    cookies: dict[tuple[str, str], str]
    warnings: list[str] = field(default_factory=list)


def parse_config(path) -> ExportData:
    """Parse the config file at `path`. Raises ConfigError on any problem."""
    try:
        # defusedxml refuses entity declarations and external references,
        # which blocks XXE and "billion laughs" attacks.
        root = SafeET.parse(path).getroot()
    except FileNotFoundError:
        raise ConfigError(f"file not found: {path}") from None
    except OSError as e:
        raise ConfigError(f"cannot read {path}: {e.strerror or e}") from None
    except DefusedXmlException:
        raise ConfigError(
            f"{path} declares XML entities, which are not allowed (possible XXE attack)"
        ) from None
    except SafeET.ParseError as e:
        raise ConfigError(f"{path} is not valid XML: {e}") from None

    if root.tag != "config":
        raise ConfigError(f"expected <config> as the root element, found <{root.tag}>")

    warnings: list[str] = []
    subdomains = _parse_subdomains(_section(root, "subdomains"))
    cookies = _parse_cookies(_section(root, "cookies"), warnings)
    return ExportData(subdomains=subdomains, cookies=cookies, warnings=warnings)


def _section(root, name):
    section = root.find(name)
    if section is None:
        raise ConfigError(f"missing <{name}> section")
    return section


def _text(element) -> str:
    # Trim surrounding whitespace (the file mixes tabs and spaces) but keep case.
    return (element.text or "").strip()


def _parse_subdomains(section) -> list[str]:
    subdomains = []
    for i, element in enumerate(section.findall("subdomain"), start=1):
        url = _text(element)
        if not url:
            raise ConfigError(f"subdomain #{i} is empty")
        subdomains.append(url)
    return subdomains


def _parse_cookies(section, warnings: list[str]) -> dict[tuple[str, str], str]:
    cookies: dict[tuple[str, str], str] = {}
    for i, element in enumerate(section.findall("cookie"), start=1):
        name = element.get("name", "").strip()
        host = element.get("host", "").strip()
        value = _text(element)
        if not name or not host:
            raise ConfigError(f"cookie #{i} is missing its 'name' or 'host' attribute")
        if not value:
            raise ConfigError(f"cookie #{i} ({name}/{host}) has no value")
        if (name, host) in cookies:
            warnings.append(f"duplicate cookie {name}/{host}: keeping the last value")
        cookies[(name, host)] = value
    return cookies
