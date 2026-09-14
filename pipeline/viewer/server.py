"""
Local 3D Map Viewer & POV Walker HTTP Server.
Serves the modern 3D POV Walker application, static assets, and REST API for dynamic catalog.
"""
import http.server
import json
import mimetypes
import os
import posixpath
import socketserver
import urllib.parse
from typing import Optional


mimetypes.add_type("model/gltf-binary", ".glb")
mimetypes.add_type("model/gltf+json", ".gltf")
mimetypes.add_type("application/json", ".json")
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")


class MapViewerRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom request handler for local 3D viewer and asset delivery."""

    def __init__(self, *args, base_dir: Optional[str] = None, output_dir: Optional[str] = None, **kwargs):
        self.project_root = base_dir or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.public_dir = os.path.join(self.project_root, "public")
        self.output_base = output_dir or os.path.join(self.project_root, "output")
        super().__init__(*args, directory=self.project_root, **kwargs)

    def translate_path(self, path):
        """Map URL paths to filesystem paths accurately."""
        parsed = urllib.parse.urlparse(path)
        clean_path = posixpath.normpath(urllib.parse.unquote(parsed.path))

        # Root and index maps to public/index.html
        if clean_path in ["/", "/index.html", "/viewer", "/viewer/"]:
            return os.path.join(self.public_dir, "index.html")

        # Static assets in public directory (css, js, vendor)
        for prefix in ["/css/", "/js/", "/vendor/"]:
            if clean_path.startswith(prefix):
                rel = clean_path[len(prefix):]
                subdir = prefix.strip("/")
                return os.path.join(self.public_dir, subdir, *rel.split("/"))

        # Output assets
        if clean_path.startswith("/output/"):
            rel = clean_path[len("/output/"):]
            return os.path.join(self.output_base, *rel.split("/"))

        # Default fallback to project root
        return super().translate_path(path)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Health endpoint
        if path in ["/api/health", "/health"]:
            self._send_json({"status": "ok", "service": "Outdoor 3D Map Explorer Server", "code": 200})
            return

        # Map catalog API endpoint
        if path == "/api/maps":
            self._handle_api_maps()
            return

        # Verification endpoint for automated tests
        if path == "/api/verify_assets":
            query = urllib.parse.parse_qs(parsed.query)
            map_id = query.get("map", [""])[0]
            self._handle_verify_assets(map_id)
            return

        # Fallthrough to standard file serving with proper headers
        return super().do_GET()

    def end_headers(self):
        # Enable CORS for local testing and web components
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_api_maps(self):
        catalog_path = os.path.join(self.output_base, "catalog.json")
        if os.path.exists(catalog_path):
            with open(catalog_path, "r", encoding="utf-8") as fp:
                catalog = json.load(fp)
            self._send_json(catalog)
            return

        # Fallback dynamic scan
        maps = []
        if os.path.exists(self.output_base):
            for m_id in sorted(os.listdir(self.output_base)):
                m_dir = os.path.join(self.output_base, m_id)
                if os.path.isdir(m_dir):
                    manifest_file = os.path.join(m_dir, "manifest.json")
                    if os.path.exists(manifest_file):
                        try:
                            with open(manifest_file, "r", encoding="utf-8") as fp:
                                maps.append(json.load(fp))
                        except Exception:
                            pass
        self._send_json({"map_count": len(maps), "maps": maps})

    def _handle_verify_assets(self, map_id: str):
        if not map_id:
            self._send_json({"error": "Missing map query parameter"}, status=400)
            return

        m_dir = os.path.join(self.output_base, map_id)
        if not os.path.exists(m_dir):
            self._send_json({"error": f"Map directory not found: {map_id}"}, status=404)
            return

        assets = {
            "render_glb": os.path.join(m_dir, "optimized", "render.glb"),
            "collision_glb": os.path.join(m_dir, "collision", "collision.glb"),
            "walkable_glb": os.path.join(m_dir, "navigation", "walkable.glb"),
            "scene_json": os.path.join(m_dir, "scene.json"),
            "manifest_json": os.path.join(m_dir, "manifest.json"),
            "process_json": os.path.join(m_dir, "reports", "process.json")
        }

        results = {}
        all_valid = True
        for name, p in assets.items():
            exists = os.path.exists(p)
            size = os.path.getsize(p) if exists else 0
            is_ok = exists and size > 0
            if not is_ok:
                all_valid = False
            results[name] = {
                "path": os.path.relpath(p, self.project_root).replace("\\", "/"),
                "exists": exists,
                "size_bytes": size,
                "valid": is_ok
            }

        self._send_json({"map_id": map_id, "all_valid": all_valid, "assets": results})


def start_server(host: str = "127.0.0.1", port: int = 8080, base_dir: Optional[str] = None) -> socketserver.TCPServer:
    """Starts the 3D map viewer HTTP server."""
    handler = lambda *args, **kwargs: MapViewerRequestHandler(*args, base_dir=base_dir, **kwargs)
    server = socketserver.TCPServer((host, port), handler)
    print(f"Starting 3D Map Explorer Server at http://{host}:{port}/")
    return server


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="3D Outdoor Map Explorer Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    httpd = start_server(args.host, args.port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down viewer server.")
        httpd.server_close()
