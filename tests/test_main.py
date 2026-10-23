import io
from pathlib import Path

import fakeredis

from app.main import run

SAMPLE_CONFIG = str(Path(__file__).resolve().parent.parent / "config.xml")


def run_app(args, client):
    out, err = io.StringIO(), io.StringIO()
    code = run(args, make_client=lambda: client, out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_without_verbose_prints_only_a_summary():
    client = fakeredis.FakeRedis(decode_responses=True)

    code, out, err = run_app([SAMPLE_CONFIG], client)

    assert code == 0
    assert out.splitlines() == ["Saved 47 keys to Redis: 'subdomains' (38 URLs) and 46 cookie keys."]
    assert err == ""
    assert len(client.keys()) == 47


def test_verbose_prints_every_saved_key_with_its_value():
    client = fakeredis.FakeRedis(decode_responses=True)

    code, out, _ = run_app(["-v", SAMPLE_CONFIG], client)

    lines = out.splitlines()
    assert code == 0
    assert len(lines) == 1 + 47
    assert "cookie:dlp-avast:amazon = mmm_amz_dlp_777_ppc_m" in lines
    assert lines[-1].startswith('subdomains = ["http://secureline.tools.avast.com", ')
    assert lines[1:] == sorted(lines[1:])


def test_bad_file_fails_without_touching_redis(tmp_path):
    client = fakeredis.FakeRedis(decode_responses=True)
    client.set("cookie:dlp-avast:amazon", "previous export")

    code, out, err = run_app([str(tmp_path / "missing.xml")], client)

    assert code == 1
    assert out == ""
    assert "Error: file not found" in err
    assert client.get("cookie:dlp-avast:amazon") == "previous export"


def test_redis_unavailable_fails_with_clear_message():
    server = fakeredis.FakeServer()
    server.connected = False
    client = fakeredis.FakeRedis(server=server, decode_responses=True)

    code, _, err = run_app([SAMPLE_CONFIG], client)

    assert code == 1
    assert "Error: could not write to Redis" in err
