from pathlib import Path

import pytest

from app.xml_parser import ConfigError, parse_config

SAMPLE_CONFIG = Path(__file__).resolve().parent.parent / "config.xml"


def write_xml(tmp_path, text):
    path = tmp_path / "config.xml"
    path.write_text(text, encoding="utf-8")
    return path


def test_sample_config_is_parsed_completely():
    data = parse_config(SAMPLE_CONFIG)

    assert len(data.subdomains) == 38
    assert data.subdomains[:2] == ["http://secureline.tools.avast.com", "http://gf.tools.avast.com"]
    assert len(data.cookies) == 46
    assert data.cookies[("dlp-avast", "amazon")] == "mmm_amz_dlp_777_ppc_m"
    assert data.warnings == []


def test_sample_config_quirks_are_kept_as_data():
    data = parse_config(SAMPLE_CONFIG)

    assert data.cookies[("dlp-avg", "filehippo")] == "Mmm_fhp_dlp_779_ppc_m"
    assert ("dlp-avast", "donwloaden") in data.cookies
    assert ("dlp-avg", "homepate") in data.cookies
    assert data.subdomains[-1] == "https://bits.avcdn.net"  # tab-indented line


def test_whitespace_is_trimmed_and_comments_ignored(tmp_path):
    path = write_xml(tmp_path, """<config>
        <subdomains>
            <!-- a comment -->
            <subdomain>
            \t http://a.example.com  \t
            </subdomain>
        </subdomains>
        <cookies>
            <cookie name=" n " host="h">  Value_X  </cookie>
        </cookies>
    </config>""")

    data = parse_config(path)

    assert data.subdomains == ["http://a.example.com"]
    assert data.cookies == {("n", "h"): "Value_X"}


def test_empty_sections_are_allowed(tmp_path):
    path = write_xml(tmp_path, "<config><subdomains/><cookies/></config>")

    data = parse_config(path)

    assert data.subdomains == []
    assert data.cookies == {}


def test_duplicate_cookie_keeps_last_value_and_warns(tmp_path):
    path = write_xml(tmp_path, """<config><subdomains/><cookies>
        <cookie name="n" host="h">first</cookie>
        <cookie name="n" host="h">second</cookie>
    </cookies></config>""")

    data = parse_config(path)

    assert data.cookies == {("n", "h"): "second"}
    assert data.warnings == ["duplicate cookie n/h: keeping the last value"]


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="file not found"):
        parse_config(tmp_path / "nope.xml")


def test_directory_instead_of_file(tmp_path):
    with pytest.raises(ConfigError, match="cannot read"):
        parse_config(tmp_path)


def test_malformed_xml(tmp_path):
    path = write_xml(tmp_path, "<config><subdomains></config>")

    with pytest.raises(ConfigError, match="not valid XML"):
        parse_config(path)


def test_wrong_root_element(tmp_path):
    path = write_xml(tmp_path, "<settings><subdomains/><cookies/></settings>")

    with pytest.raises(ConfigError, match="root element"):
        parse_config(path)


@pytest.mark.parametrize("missing", ["subdomains", "cookies"])
def test_missing_section(tmp_path, missing):
    sections = {"subdomains": "<subdomains/>", "cookies": "<cookies/>"}
    del sections[missing]
    path = write_xml(tmp_path, f"<config>{''.join(sections.values())}</config>")

    with pytest.raises(ConfigError, match=f"missing <{missing}>"):
        parse_config(path)


@pytest.mark.parametrize("attributes", ['host="h"', 'name="n"', 'name="" host="h"'])
def test_cookie_without_name_or_host(tmp_path, attributes):
    path = write_xml(tmp_path, f"<config><subdomains/><cookies><cookie {attributes}>v</cookie></cookies></config>")

    with pytest.raises(ConfigError, match="missing its 'name' or 'host'"):
        parse_config(path)


def test_cookie_without_value(tmp_path):
    path = write_xml(tmp_path, '<config><subdomains/><cookies><cookie name="n" host="h">  </cookie></cookies></config>')

    with pytest.raises(ConfigError, match="has no value"):
        parse_config(path)


def test_empty_subdomain(tmp_path):
    path = write_xml(tmp_path, "<config><subdomains><subdomain> </subdomain></subdomains><cookies/></config>")

    with pytest.raises(ConfigError, match="subdomain #1 is empty"):
        parse_config(path)


@pytest.mark.parametrize("entity", [
    '<!ENTITY xxe SYSTEM "file:///etc/passwd">',  # XXE: read a local file
    '<!ENTITY lol "lol">',                         # building block of "billion laughs"
])
def test_entity_declarations_are_rejected(tmp_path, entity):
    path = write_xml(tmp_path, f"""<?xml version="1.0"?>
<!DOCTYPE config [ {entity} ]>
<config><subdomains><subdomain>&{entity.split()[1]};</subdomain></subdomains><cookies/></config>""")

    with pytest.raises(ConfigError, match="XXE"):
        parse_config(path)
