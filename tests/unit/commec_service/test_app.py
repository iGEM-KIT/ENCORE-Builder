"""Tests of commec-service/app.py (the HTTP wrapper around the COMMEC command line).

COMMEC itself is never run: subprocess.run is replaced, so the tests cover the wrapper (status search, error paths, the
health logic and the HTTP routes) without Conda, BLAST or the databases.
"""

import http.client
import importlib.util
import json
import subprocess
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

APP_PATH = Path(__file__).resolve().parents[3] / "commec-service" / "app.py"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    """The module loaded fresh with a temporary database directory."""
    monkeypatch.setenv("COMMEC_DB_DIR", str(tmp_path / "databases"))
    monkeypatch.delenv("COMMEC_SKIP_TAXONOMY", raising=False)
    spec = importlib.util.spec_from_file_location("commec_app_under_test", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_commec(output=None, calls=None, write=True):
    """A subprocess.run replacement that writes the `<prefix>.output.json` COMMEC would produce."""
    def run(cmd, **kwargs):
        if calls is not None:
            calls.append(cmd)
        if write:
            prefix = cmd[cmd.index("-o") + 1]
            Path(f"{prefix}.output.json").write_text(json.dumps(output))
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    return run


STATUS = {"screen_status": "Pass", "biorisk": "Pass", "protein_taxonomy": "Skip", "nucleotide_taxonomy": "Skip",
          "low_concern": "Pass", "rationale": "No matches found."}
SEQ = "ATGGCTAAAGGTGAAGAACTGTTCACCGGTGTTGTTCCAATCTTGGTTGAATTGGATGGTGATGTT"


# _find_status

def test_find_status_finds_the_status_object_wherever_commec_puts_it(app):
    find = app._find_status
    assert find({"queries": [{"x": 1}, {"status": STATUS}]}) == STATUS
    assert find({"screen_status": "Flag", "biorisk": "Flag"}) == {"screen_status": "Flag", "biorisk": "Flag"}
    assert find([{"a": {"b": [{"status": STATUS}]}}]) == STATUS
    assert find({"queries": [{"status": {"no": "screen_status"}}]}) is None
    assert find("text") is None and find(None) is None


# _screen_one

def test_screen_one_returns_the_status_of_a_successful_run(app, monkeypatch):
    calls = []
    monkeypatch.setattr(app.subprocess, "run", fake_commec({"queries": [{"status": STATUS}]}, calls))
    result = app._screen_one("x", SEQ)
    assert result == {"available": True, "status": STATUS}
    cmd = calls[0]
    assert cmd[:2] == ["commec", "screen"] and "-d" in cmd and "-F" in cmd
    assert "--skip-tx" in cmd and "--skip-nt" in cmd                                 # taxonomy is skipped by default


def test_screen_one_runs_the_taxonomy_steps_when_asked_to(app, monkeypatch):
    monkeypatch.setattr(app, "SKIP_TAXONOMY", False)
    calls = []
    monkeypatch.setattr(app.subprocess, "run", fake_commec({"status": STATUS}, calls))
    app._screen_one("x", SEQ)
    assert "--skip-tx" not in calls[0] and "--skip-nt" not in calls[0]


def test_screen_one_keeps_only_acgt_and_rejects_empty_and_too_long_input(app, monkeypatch):
    calls = []
    monkeypatch.setattr(app.subprocess, "run", fake_commec({"status": STATUS}, calls))
    assert app._screen_one("x", ">xyz 123 mn")["available"] is False                # no A, C, G or T left
    assert calls == []                                                               # commec is not even started
    monkeypatch.setattr(app, "MAX_SEQ_LEN", 10)
    too_long = app._screen_one("x", "A" * 11)
    assert too_long["available"] is False and "longer than 10" in too_long["reason"]


def test_screen_one_never_puts_the_label_into_the_command(app, monkeypatch):
    calls = []
    monkeypatch.setattr(app.subprocess, "run", fake_commec({"status": STATUS}, calls))
    app._screen_one("; rm -rf / #", SEQ)
    assert all("rm -rf" not in part for part in calls[0])


@pytest.mark.parametrize("error, text", [
    (FileNotFoundError(), "executable was not found"),
    (subprocess.TimeoutExpired("commec", 1), "did not finish"),
])
def test_screen_one_reports_a_missing_or_hanging_commec(app, monkeypatch, error, text):
    def run(cmd, **kwargs):
        raise error
    monkeypatch.setattr(app.subprocess, "run", run)
    result = app._screen_one("x", SEQ)
    assert result["available"] is False and text in result["reason"]


def test_screen_one_reports_missing_output_unparsable_output_and_missing_status(app, monkeypatch):
    monkeypatch.setattr(app.subprocess, "run", fake_commec(write=False))
    assert "produced no" in app._screen_one("x", SEQ)["reason"]

    def broken_json(cmd, **kwargs):
        Path(f"{cmd[cmd.index('-o') + 1]}.output.json").write_text("{not json")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
    monkeypatch.setattr(app.subprocess, "run", broken_json)
    assert "Could not parse" in app._screen_one("x", SEQ)["reason"]

    monkeypatch.setattr(app.subprocess, "run", fake_commec({"something": "else"}))
    assert "recognizable status" in app._screen_one("x", SEQ)["reason"]


# HTTP routes

@pytest.fixture()
def server(app, monkeypatch):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def request(port, method, path, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Content-Type": "application/json"} if body is not None else {}
    conn.request(method, path, body=body, headers=headers)
    response = conn.getresponse()
    data = json.loads(response.read() or b"{}")
    conn.close()
    return response.status, data


def test_health_is_not_ok_without_databases_while_downloading_and_ok_when_ready(app, server, tmp_path):
    db = Path(app.DB_DIR)
    status, body = request(server, "GET", "/health")
    assert status == 200 and body["ok"] is False and "missing or empty" in body["detail"]

    db.mkdir(parents=True)
    (db / "biorisk").mkdir()
    (db / ".setup-running").touch()
    body = request(server, "GET", "/health")[1]
    assert body["ok"] is False and "downloaded" in body["detail"] and "1.2 GB" in body["detail"]   # the size text matches the README

    (db / ".setup-running").unlink()
    assert request(server, "GET", "/health")[1]["ok"] is True


def test_unknown_routes_answer_404(server):
    assert request(server, "GET", "/nope")[0] == 404
    assert request(server, "POST", "/nope", "{}")[0] == 404


def test_screen_validates_the_request_body(server):
    assert request(server, "POST", "/screen", "{not json")[0] == 400
    assert request(server, "POST", "/screen", json.dumps({"sequences": "text"}))[0] == 400
    assert request(server, "POST", "/screen", json.dumps({}))[0] == 400


def test_screen_returns_one_result_per_sequence_in_the_same_order(app, server, monkeypatch):
    monkeypatch.setattr(app.subprocess, "run", fake_commec({"status": STATUS}))
    body = {"sequences": [{"label": "a", "sequence": SEQ}, {"label": "b", "sequence": "NNNN"}, "not an object"]}
    status, data = request(server, "POST", "/screen", json.dumps(body))
    assert status == 200 and len(data["results"]) == 3
    assert data["results"][0]["available"] is True
    assert data["results"][1]["available"] is False and data["results"][2]["available"] is False
