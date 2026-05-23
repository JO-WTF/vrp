import json
import os
from http.server import SimpleHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

class VisHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve static frontend files from 'frontend/dist' (we will build them there)
        frontend_dir = Path(__file__).parent / "frontend" / "dist"
        super().__init__(*args, directory=str(frontend_dir), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == '/api/runs':
            self.serve_runs()
        elif parsed.path.startswith('/api/runs/') and parsed.path.endswith('/history'):
            run_name = parsed.path.split('/')[3]
            self.serve_history(run_name)
        else:
            # Fallback to frontend routing (index.html) if not found, or static files
            # For simplicity, just use base SimpleHTTPRequestHandler for static paths
            # and if file doesn't exist, we can fallback to index.html for SPA.
            file_path = Path(self.directory) / parsed.path.lstrip('/')
            if not file_path.exists() and not parsed.path.startswith('/assets/'):
                self.path = '/index.html'
            super().do_GET()

    def serve_runs(self):
        data_dir = Path(os.getcwd()) / ".vrp_vis_data"
        runs = []
        if data_dir.exists():
            for p in data_dir.glob("*.json"):
                runs.append(p.stem)
                
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        # Allow CORS for development if we run Vite dev server
        self.send_header('Access-Control-Allow-Origin', '*') 
        self.end_headers()
        self.wfile.write(json.dumps(runs).encode('utf-8'))

    def serve_history(self, run_name: str):
        data_dir = Path(os.getcwd()) / ".vrp_vis_data"
        history_file = data_dir / f"{run_name}.json"
        
        if not history_file.exists():
            self.send_error(404, "Run not found")
            return
            
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        with open(history_file, 'rb') as f:
            self.wfile.write(f.read())

def serve(port=8080):
    print(f"Starting VRP Visualizer at http://localhost:{port}")
    print(f"Reading tracking data from {Path(os.getcwd()) / '.vrp_vis_data'}")
    server_address = ('', port)
    httpd = HTTPServer(server_address, VisHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down visualizer.")
        httpd.server_close()

if __name__ == "__main__":
    serve()
