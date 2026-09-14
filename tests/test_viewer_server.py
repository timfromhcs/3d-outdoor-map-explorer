"""
Tests for local 3D viewer server and endpoints.
"""
import json
import threading
import time
import urllib.request
import pytest
from pipeline.viewer.server import start_server


@pytest.fixture(scope="module")
def viewer_server():
    server = start_server("127.0.0.1", 8899)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)
    yield "http://127.0.0.1:8899"
    server.shutdown()
    server.server_close()


def test_server_health_endpoint(viewer_server):
    url = f"{viewer_server}/api/health"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert data["status"] == "ok"


def test_server_maps_catalog_endpoint(viewer_server):
    url = f"{viewer_server}/api/maps"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert "maps" in data
    assert data.get("total_maps", data.get("map_count", 0)) >= 1


def test_server_verify_assets_endpoint(viewer_server):
    url = f"{viewer_server}/api/verify_assets?map=map3"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert data["map_id"] == "map3"
    assert data["all_valid"] is True
    assert data["assets"]["render_glb"]["exists"] is True


def test_server_viewer_html_serving(viewer_server):
    url = f"{viewer_server}/"
    req = urllib.request.urlopen(url)
    assert req.status == 200
    content = req.read().decode("utf-8")
    assert "3D Outdoor Map Explorer" in content
