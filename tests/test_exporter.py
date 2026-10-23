import json

import fakeredis
import pytest

from app.exporter import build_keys, cookie_key, read_back, save
from app.xml_parser import ExportData


@pytest.fixture
def client():
    return fakeredis.FakeRedis(decode_responses=True)


def sample_data():
    return ExportData(
        subdomains=["http://secureline.tools.avast.com", "http://gf.tools.avast.com"],
        cookies={
            ("dlp-avast", "amazon"): "mmm_amz_dlp_777_ppc_m",
            ("dlp-avg", "cnet"): "mmm_cnt_dlp_779_ppc_m",
        },
    )


def test_cookie_key_format():
    assert cookie_key("dlp-avast", "amazon") == "cookie:dlp-avast:amazon"


def test_build_keys():
    keys = build_keys(sample_data())

    assert keys == {
        "subdomains": '["http://secureline.tools.avast.com", "http://gf.tools.avast.com"]',
        "cookie:dlp-avast:amazon": "mmm_amz_dlp_777_ppc_m",
        "cookie:dlp-avg:cnet": "mmm_cnt_dlp_779_ppc_m",
    }


def test_subdomains_value_is_valid_json_in_file_order():
    keys = build_keys(sample_data())

    assert json.loads(keys["subdomains"]) == sample_data().subdomains


def test_save_writes_every_key(client):
    keys = build_keys(sample_data())

    save(client, keys)

    assert client.get("cookie:dlp-avast:amazon") == "mmm_amz_dlp_777_ppc_m"
    assert json.loads(client.get("subdomains")) == sample_data().subdomains
    assert sorted(client.keys()) == sorted(keys)


def test_save_removes_cookies_no_longer_in_the_file(client):
    client.set("cookie:dlp-old:gone", "stale")

    save(client, build_keys(sample_data()))

    assert client.get("cookie:dlp-old:gone") is None


def test_save_leaves_unrelated_keys_alone(client):
    client.set("someone-elses-key", "keep me")

    save(client, build_keys(sample_data()))

    assert client.get("someone-elses-key") == "keep me"


def test_save_twice_gives_the_same_result(client):
    keys = build_keys(sample_data())

    save(client, keys)
    first = {k: client.get(k) for k in client.keys()}
    save(client, keys)
    second = {k: client.get(k) for k in client.keys()}

    assert first == second


def test_read_back_returns_stored_values(client):
    client.set("a", "1")

    assert read_back(client, ["a", "missing"]) == {"a": "1", "missing": None}
