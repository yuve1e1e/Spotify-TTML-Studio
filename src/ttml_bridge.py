import os, sys, time, json, subprocess
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)
SCRIPT = os.path.join(SRC_DIR, "yt2ttml.py")
CONFIG_PATH = os.path.join(ROOT_DIR, "config.json")

def get_ttml_dir():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "ttml_output_dir" in cfg:
                return cfg["ttml_output_dir"]
        except Exception:
            pass
    return os.path.join(ROOT_DIR, "output", "ttml")

class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")
        cmd = [sys.executable, SCRIPT, "--title", data.get("title", ""), "--duration", str(data.get("duration", 0))]
        if data.get("hard"):
            cmd.append("--hard")

        start_ts = time.time() - 1.0
        res = subprocess.run(cmd, creationflags=subprocess.CREATE_NEW_CONSOLE)

        if res.returncode != 0:
            self.send_response(500)
            self._cors()
            self.end_headers()
            return

        out_dir = get_ttml_dir()
        ttml_text, ttml_name = "", ""
        if os.path.isdir(out_dir):
            candidates = [
                os.path.join(out_dir, f) for f in os.listdir(out_dir)
                if f.lower().endswith(".ttml") and os.path.getmtime(os.path.join(out_dir, f)) >= start_ts
            ]
            if candidates:
                latest = max(candidates, key=os.path.getmtime)
                ttml_name = os.path.basename(latest)
                with open(latest, "r", encoding="utf-8") as f:
                    ttml_text = f.read()

        payload = json.dumps({"ttml": ttml_text, "filename": ttml_name}).encode("utf-8")
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass

ThreadingHTTPServer(("127.0.0.1", 8765), Handler).serve_forever()
