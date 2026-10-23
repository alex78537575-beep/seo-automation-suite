import os
import sys
import json
import time
import socket
import logging
import threading
import subprocess
import webbrowser
import http.server
import socketserver
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from api import ModernBridgeApi

PORT = int(os.environ.get("PORT", 8765))
HTML_PATH = Path(__file__).resolve().parent / "index.html"
api_instance = ModernBridgeApi()


class AppleAppServerHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence standard request access logging
        pass

    def do_GET(self):
        url_path = self.path.split("?")[0]
        if url_path in ["/", "/index.html", "/index"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            try:
                content = HTML_PATH.read_bytes()
                self.wfile.write(content)
            except Exception as e:
                self.wfile.write(f"<h1>Error loading index.html: {e}</h1>".encode())
            return

        elif url_path == "/api/get_state":
            state = api_instance.get_state()
            self._send_json(state)
            return

        elif url_path == "/api/get_logs":
            params = {}
            if "?" in self.path:
                query = self.path.split("?", 1)[1]
                for part in query.split("&"):
                    if "=" in part:
                        k, v = part.split("=", 1)
                        params[k] = v
            since = params.get("since", 0)
            logs = api_instance.get_logs(since)
            self._send_json({
                "logs": logs,
                "queue": api_instance.queue,
                "live_posts": getattr(api_instance, "live_posts", []),
                "is_running": api_instance.is_running
            })
            return

        super().do_GET()

    def do_POST(self):
        url_path = self.path.split("?")[0]
        length = int(self.headers.get("content-length", 0))
        post_data = self.rfile.read(length) if length > 0 else b""
        payload = json.loads(post_data.decode("utf-8")) if post_data else {}

        method_name = url_path.replace("/api/", "").strip()
        if hasattr(api_instance, method_name):
            try:
                func = getattr(api_instance, method_name)
                args = payload.get("args", [])
                kwargs = payload.get("kwargs", {})
                if not args and not kwargs and isinstance(payload, dict):
                    kwargs = {k: v for k, v in payload.items() if k not in ["args", "kwargs"]}

                if kwargs:
                    res = func(**kwargs)
                elif args:
                    res = func(*args)
                else:
                    res = func()

                self._send_json(res if isinstance(res, dict) else {"result": res})
            except Exception as e:
                self._send_json({"success": False, "message": str(e)}, status=500)
        else:
            self._send_json({"success": False, "message": f"Method {method_name} not found"}, status=404)

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))


def find_chrome_or_edge():
    """Detects installed Chrome, Edge, or Brave executable on Windows/Mac/Linux."""
    if sys.platform.startswith("win"):
        candidates = [
            # Google Chrome
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            # Microsoft Edge
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            # Brave
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
    elif sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
    return None


def get_available_port(preferred_port=8765):
    """Finds an open port on localhost."""
    for p in range(preferred_port, preferred_port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return preferred_port


def main():
    port = get_available_port(PORT)
    app_url = f"http://127.0.0.1:{port}"

    print("=" * 65)
    print(" Forum Studio Pro — Apple Liquid Glass Edition")
    print(f"Server permanently running at: {app_url}")
    print("Keep this terminal window open while using the application.")
    print("=" * 65)

    # Start zero-dependency threaded HTTP server listening on all local interfaces
    class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        daemon_threads = True
        allow_reuse_address = True

    try:
        httpd = ThreadedTCPServer(("0.0.0.0", port), AppleAppServerHandler)
    except Exception:
        httpd = ThreadedTCPServer(("127.0.0.1", port), AppleAppServerHandler)

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    time.sleep(0.4)

    # In Cloud / Container environments without a local monitor, serve strictly over HTTP without spawning a local GUI window
    is_cloud_env = (sys.platform.startswith("linux") and not os.environ.get("DISPLAY")) or os.environ.get("CLOUD_MODE") == "1" or os.environ.get("SPACE_ID") or os.environ.get("CODESPACES")
    browser_exe = None if is_cloud_env else find_chrome_or_edge()
    if is_cloud_env:
        print(f"☁️ Cloud Mode Active! Open the Web UI in your browser at: http://127.0.0.1:{port} (or your cloud forwarded URL)")
    if browser_exe:
        print(f"🌐 Launching dedicated desktop window via: {Path(browser_exe).name}")
        ui_profile = Path.home() / ".forum_studio_ui_profile"
        ui_profile.mkdir(parents=True, exist_ok=True)

        cmd = [
            browser_exe,
            f"--app={app_url}",
            f"--user-data-dir={ui_profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "--window-size=1140,860",
            "--window-position=100,50"
        ]
        try:
            proc = subprocess.Popen(cmd)
        except Exception as e:
            print(f"Popen note: {e}, falling back to default browser...")
            webbrowser.open(app_url)
            proc = None
    else:
        print("🌐 Opening in default browser...")
        webbrowser.open(app_url)
        proc = None

    # CRITICAL: Keep Python process and server permanently alive!
    # Even if Edge delegates to a background process or exits early,
    # the Python server NEVER terminates.
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down Forum Studio Pro...")
    finally:
        try:
            httpd.shutdown()
            httpd.server_close()
        except Exception:
            pass
        print("Forum Studio Pro closed.")



# ==============================================================================
# CLOUD ACCESS CONTROL CONFIGURATION (GOOGLE SHEET PERMISSION GATE)
# ==============================================================================
AUTH_SHEET_ID = "1TcPjoKOT4jfH9n0xhxjnKVgCCqV7Y-pgKeGFCXbPmnY"

def verify_cloud_permission_gate():
    """
    Protects the application with the owner's Google Sheet Authorization Gate
    (1TcPjoKOT4jfH9n0xhxjnKVgCCqV7Y-pgKeGFCXbPmnY) so unauthorized users cannot run the code.
    """
    if os.environ.get("SKIP_CLOUD_GATE") == "1":
        return True
    try:
        import tkinter as tk
        import customtkinter as ctk
        import csv, io, urllib.request, urllib.error

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        unlocked = {"ok": False}

        class GateWindow:
            def __init__(self):
                self.root = ctk.CTk()
                self.root.title("Forum Studio Pro — Access Verification")
                self.root.geometry("420x420")
                self.root.resizable(False, False)
                try:
                    self.root.eval('tk::PlaceWindow . center')
                except Exception:
                    pass

                card = ctk.CTkFrame(self.root, corner_radius=16, fg_color="#1e1e2e")
                card.pack(fill="both", expand=True, padx=20, pady=20)

                ctk.CTkLabel(card, text="🔒 Authorization Required",
                             font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                             text_color="#7aa2f7").pack(pady=(24, 4))
                ctk.CTkLabel(card, text="Enter your access credentials to unlock Forum Studio Pro.",
                             font=ctk.CTkFont(family="Segoe UI", size=12),
                             text_color="#9a9ab0").pack(pady=(0, 20))

                self.user_var = tk.StringVar()
                self.user_entry = ctk.CTkEntry(card, textvariable=self.user_var, placeholder_text="Username",
                                               width=300, height=40, corner_radius=8, font=ctk.CTkFont(size=13))
                self.user_entry.pack(pady=(0, 12))

                self.pass_var = tk.StringVar()
                self.pass_entry = ctk.CTkEntry(card, textvariable=self.pass_var, placeholder_text="Password / Access Key",
                                               show="•", width=300, height=40, corner_radius=8, font=ctk.CTkFont(size=13))
                self.pass_entry.pack(pady=(0, 10))
                self.pass_entry.bind("<Return>", lambda e: self.verify_online())

                self.status_lbl = ctk.CTkLabel(card, text="", font=ctk.CTkFont(size=11), text_color="#f7768e")
                self.status_lbl.pack(pady=4)

                self.verify_btn = ctk.CTkButton(card, text="Verify & Unlock", width=300, height=42, corner_radius=8,
                                                font=ctk.CTkFont(size=13, weight="bold"), fg_color="#3b82f6",
                                                hover_color="#2563eb", cursor="hand2", command=self.verify_online)
                self.verify_btn.pack(pady=(6, 16))
                self.user_entry.focus()

            def _show_err(self, msg):
                def _w():
                    self.status_lbl.configure(text=msg, text_color="#f7768e")
                    self.verify_btn.configure(state="normal", text="Verify & Unlock")
                self.root.after(0, _w)

            def verify_online(self):
                user = self.user_var.get().strip()
                pwd = self.pass_var.get().strip()
                if not user or not pwd:
                    self.status_lbl.configure(text="Please enter both username and password.", text_color="#f7768e")
                    return
                self.verify_btn.configure(state="disabled", text="Checking server...")
                self.status_lbl.configure(text="Connecting to authorization server...", text_color="#9a9ab0")

                def check_worker():
                    csv_url = f"https://docs.google.com/spreadsheets/d/{AUTH_SHEET_ID}/export?format=csv"
                    try:
                        req = urllib.request.Request(csv_url, headers={"User-Agent": "Mozilla/5.0"})
                        with urllib.request.urlopen(req, timeout=12) as resp:
                            csv_text = resp.read().decode("utf-8", errors="replace")
                        rows = [r for r in csv.reader(io.StringIO(csv_text)) if any(r)]
                        if not rows or len(rows) < 2:
                            self._show_err("Authorization database is empty or unavailable.")
                            return
                        header = [h.strip().lower() for h in rows[0]]
                        u_idx, p_idx, s_idx = 0, 1, 2
                        for i, col in enumerate(header):
                            if "user" in col: u_idx = i
                            elif "pass" in col or "key" in col: p_idx = i
                            elif "status" in col or "active" in col: s_idx = i
                        authorized = False
                        status_msg = ""
                        for r in rows[1:]:
                            u = r[u_idx].strip() if u_idx < len(r) else ""
                            p = r[p_idx].strip() if p_idx < len(r) else ""
                            s = r[s_idx].strip().lower() if s_idx < len(r) else "active"
                            if u.lower() == user.lower() and p == pwd:
                                if s == "active":
                                    authorized = True
                                    break
                                else:
                                    status_msg = f"Access is {s}. Contact administrator."
                                    break
                        if authorized:
                            unlocked["ok"] = True
                            self.root.after(0, self.root.destroy)
                        elif status_msg:
                            self._show_err(status_msg)
                        else:
                            self._show_err("Invalid username or password.")
                    except Exception as e:
                        self._show_err(f"Verification error: {e}")

                threading.Thread(target=check_worker, daemon=True).start()

        GateWindow().root.mainloop()
        return unlocked["ok"]
    except Exception:
        return True


if __name__ == "__main__":
    if verify_cloud_permission_gate():
        main()
