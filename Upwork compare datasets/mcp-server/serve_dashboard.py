import os
import httpx
import threading
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.environ.get("FINANCIAL_DATASETS_API_KEY", "")
API_BASE = "https://api.financialdatasets.ai"
PORT = 8080
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path.split("?")[0] in ("/", "/dashboard.html"):
            self._serve_html()
        elif self.path.startswith("/api/"):
            self._proxy()
        else:
            self.send_response(404)
            self.end_headers()

    def _serve_html(self):
        path = os.path.join(SCRIPT_DIR, "dashboard.html")
        try:
            with open(path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def _proxy(self):
        api_path = self.path[4:]  # strip /api prefix → /prices/...
        url = f"{API_BASE}{api_path}"
        headers = {"X-API-KEY": API_KEY} if API_KEY else {}
        try:
            with httpx.Client() as client:
                resp = client.get(url, headers=headers, timeout=30.0)
            self.send_response(resp.status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(resp.content)
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(f'{{"error": "{e}"}}'.encode())


if __name__ == "__main__":
    server = HTTPServer(("localhost", PORT), Handler)
    print(f"AAPL Dashboard: http://localhost:{PORT}")
    print("Press Ctrl+C to stop")
    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped")
