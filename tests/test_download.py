import http.server
import threading

import pytest

from geopulse.download import download_file


@pytest.fixture
def server(tmp_path):
    (tmp_path / "hello.txt").write_text("hello geopulse")
    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(*a, directory=str(tmp_path), **k)
    httpd = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def test_download_and_skip(server, tmp_path):
    dest = tmp_path / "out" / "hello.txt"
    download_file(f"{server}/hello.txt", dest)
    assert dest.read_text() == "hello geopulse"
    mtime = dest.stat().st_mtime_ns
    download_file(f"{server}/hello.txt", dest)  # skipped
    assert dest.stat().st_mtime_ns == mtime


def test_download_failure(server, tmp_path, monkeypatch):
    monkeypatch.setattr("geopulse.download.time.sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        download_file(f"{server}/missing.txt", tmp_path / "x.txt", retries=2)
    assert not (tmp_path / "x.txt.part").exists()
