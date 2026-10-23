import queue as py_queue
import concurrent.futures
import os
import sys
import json
import time
import random
import logging
import threading
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, List, Any

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sync_playwright = None
    class PWTimeout(Exception): pass

import backend

logger = logging.getLogger("forum_suite")


class ModernBridgeApi:
    def __init__(self, window=None):
        self.window = window
        self.queue: List[Dict[str, Any]] = []
        self.is_running = False
        self.save_requested = False
        self.live_user_confirmed = threading.Event()
        self.stop_event = threading.Event()
        self.cfg = backend.load_config()
        self.active_context = None
        self.active_native_proc = None
        self.logs_history: List[Dict[str, str]] = []
        self.live_posts: List[Dict[str, Any]] = []
        self._log_lock = threading.Lock()

    def set_window(self, window):
        self.window = window

    def log_to_ui(self, message: str, color_class: str = "text-slate-300"):
        """Appends a timestamped line to log history in a thread-safe manner and updates UI."""
        logger.info(message)
        log_entry = {
            "time": time.strftime("%H:%M:%S"),
            "msg": message,
            "color": color_class
        }
        with getattr(self, "_log_lock", threading.Lock()):
            self.logs_history.append(log_entry)
            if len(self.logs_history) > 2000:
                self.logs_history = self.logs_history[-1500:]

        if self.window:
            clean_msg = message.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")
            js = f'if (typeof appendLog === "function") appendLog("{clean_msg}", "{color_class}");'
            try:
                self.window.evaluate_js(js)
            except Exception:
                pass

    def notify_ui(self, message: str, toast_type: str = "info", queue: list = None, log_color: str = None):
        """Sends a notification toast and updates queue in the UI."""
        if log_color:
            self.log_to_ui(message, log_color)
        if self.window:
            clean_msg = message.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ").replace("\r", "")
            script = f'if (typeof showToast === "function") showToast("{clean_msg}", "{toast_type}");'
            if queue is not None:
                queue_json = json.dumps(queue).replace("\\", "\\\\").replace('"', '\\"')
                script += f' if (typeof renderQueue === "function") renderQueue(JSON.parse("{queue_json}"));'
            try:
                self.window.evaluate_js(script)
            except Exception:
                pass

    # =========================================================================
    # PLAYWRIGHT CODEGEN & BLUEPRINT STUDIO
    # =========================================================================
    def launch_codegen_recorder(self, url: str = None) -> Dict[str, Any]:
        """Launches Playwright Inspector / Codegen for visual recording."""
        target = (url or self.cfg.get("board_url") or "https://www.themoviedb.org/movie/new").strip()
        if not target.startswith("http"):
            target = f"https://{target}"

        self.notify_ui(f"🎥 Launching Playwright Inspector for: {target}", "info", log_color="text-purple-400")
        try:
            import subprocess
            subprocess.Popen([sys.executable, "-m", "playwright", "codegen", target])
            return {
                "success": True,
                "message": f"Playwright Recorder window is open for {target}! Click on the page elements to record selectors."
            }
        except Exception as e:
            self.notify_ui(f"❌ Error launching recorder: {e}", "error", log_color="text-rose-400")
            return {"success": False, "message": str(e)}

    def get_blueprints(self) -> Dict[str, Any]:
        """Returns all custom saved site recipes."""
        return backend.load_recipes()

    def save_blueprint(self, blueprint_data: Dict[str, Any]) -> Dict[str, Any]:
        """Saves a new or updated site blueprint recipe."""
        name = blueprint_data.get("name", "").strip()
        if not name:
            return {"success": False, "message": "Blueprint Name is required."}

        recipes = backend.load_recipes()
        board_url = blueprint_data.get("board_url", "").strip()
        domain = blueprint_data.get("domain_pattern", "").strip()
        if not domain and board_url:
            try:
                from urllib.parse import urlparse
                domain = urlparse(board_url).netloc.replace("www.", "")
            except Exception:
                pass

        recipes[name] = {
            "name": name,
            "board_url": board_url,
            "domain_pattern": domain,
            "login_url": blueprint_data.get("login_url", "").strip(),
            "reply_selector": blueprint_data.get("reply_selector", "").strip(),
            "title_selector": blueprint_data.get("title_selector", "").strip(),
            "editor_selector": blueprint_data.get("editor_selector", "").strip(),
            "submit_selector": blueprint_data.get("submit_selector", "").strip(),
            "steps": blueprint_data.get("steps", []),
            "raw_post_code": blueprint_data.get("raw_post_code", []),
        }
        backend.save_recipes(recipes)
        self.notify_ui(f"🛠️ Saved Site Blueprint '{name}'!", "success", log_color="text-emerald-400")
        return {"success": True, "blueprints": recipes, "saved_name": name}

    def delete_blueprint(self, name: str) -> Dict[str, Any]:
        """Deletes a custom site blueprint recipe."""
        recipes = backend.load_recipes()
        if name in recipes:
            del recipes[name]
            backend.save_recipes(recipes)
            self.notify_ui(f"Deleted blueprint: '{name}'", "info", log_color="text-slate-400")
            return {"success": True, "blueprints": recipes}
        return {"success": False, "message": "Blueprint not found."}

    def parse_codegen(self, code_text: str) -> Dict[str, Any]:
        """Auto-detects selectors from raw Playwright codegen lines."""
        parsed = backend.parse_codegen_to_recipe(code_text)
        return {"success": True, "recipe": parsed}

    # =========================================================================
    # AI SETTINGS & CONNECTION TESTING
    # =========================================================================
    def test_ai_connection(self, anythingllm_url: str = None, anythingllm_api_key: str = None,
                           workspace_slug: str = None, ollama_url: str = None) -> Dict[str, Any]:
        """Pings local AnythingLLM and Ollama instances and returns connection status."""
        cfg = backend.load_config()
        a_url = (anythingllm_url or cfg.get("anythingllm_url") or "http://localhost:3001/api/v1").strip().rstrip("/")
        ws = (workspace_slug or cfg.get("workspace_slug") or "content").strip()
        k = (anythingllm_api_key or cfg.get("anythingllm_api_key") or "").strip()
        o_url = (ollama_url or cfg.get("ollama_url") or "http://localhost:11434").strip().rstrip("/")

        results = []
        headers = {"Content-Type": "application/json"}
        if k:
            headers["Authorization"] = f"Bearer {k}"

        # Test AnythingLLM
        try:
            req = urllib.request.Request(f"{a_url}/auth", headers=headers)
            with urllib.request.urlopen(req, timeout=4) as r:
                results.append("✅ AnythingLLM API: Connected")
        except Exception:
            try:
                req2 = urllib.request.Request(f"{a_url}/workspace/{ws}", headers=headers)
                with urllib.request.urlopen(req2, timeout=4) as r:
                    results.append(f"✅ AnythingLLM Workspace '{ws}': Connected")
            except Exception as e:
                results.append(f"⚠️ AnythingLLM: Offline or Unauthorized ({e})")

        # Test Ollama
        try:
            req_o = urllib.request.Request(f"{o_url}/api/tags")
            with urllib.request.urlopen(req_o, timeout=4) as r:
                d = json.loads(r.read().decode("utf-8"))
                models = [m.get("name", "") for m in d.get("models", [])]
                gemma = any("gemma" in m.lower() for m in models)
                if gemma:
                    results.append("✅ Ollama: Connected (Gemma model detected)")
                else:
                    results.append(f"✅ Ollama: Connected ({len(models)} models)")
        except Exception as e:
            results.append(f"⚠️ Ollama: Offline ({e})")

        summary = " • ".join(results)
        self.log_to_ui(f"🧪 AI Connection Test: {summary}", "text-sky-300")
        return {"success": True, "results": results, "summary": summary}

    def save_persona(self, persona: str, custom_system_prompt: str) -> Dict[str, Any]:
        """Saves persona settings and system prompt."""
        cfg = backend.load_config()
        cfg["persona"] = str(persona).strip()
        cfg["custom_system_prompt"] = str(custom_system_prompt).strip()
        backend.save_config(cfg)
        self.cfg = cfg
        self.notify_ui(f"🎭 Saved Persona: {persona}!", "success", log_color="text-emerald-400")
        return {"success": True}

    def save_api_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Saves LLM configuration."""
        cfg = backend.load_config()
        cfg.update(settings)
        backend.save_config(cfg)
        self.cfg = cfg
        self.notify_ui("💾 Local AI Settings saved successfully!", "success", log_color="text-emerald-400")
        return {"success": True}

    def get_saved_sites(self) -> List[str]:
        """Returns list of remembered working site domains."""
        history = backend.load_history()
        sites = set()
        for item in history:
            url = item.get("url", "") or item.get("thread_url", "")
            if url and url.startswith("http"):
                parsed = urllib.parse.urlparse(url)
                sites.add(f"{parsed.scheme}://{parsed.netloc}")
        default_sites = [
            "https://app.waiverelectronic.com",
            "https://www.themoviedb.org",
            "https://ohm.proboards.com",
            "https://autd.proboards.com"
        ]
        for s in default_sites:
            sites.add(s)
        return sorted(list(sites))

    def get_state(self) -> Dict[str, Any]:
        """Returns the full state to the UI."""
        cfg = backend.load_config()
        return {
            "model": cfg.get("model", "huihui_ai/gemma3n-abliterated:e2b-fp16"),
            "tokens": cfg.get("max_tokens", "4096"),
            "target_board": cfg.get("board_url", backend.DEFAULT_BOARD),
            "login_url": cfg.get("login_url", backend.DEFAULT_LOGIN_URL),
            "platform": cfg.get("platform", "Auto-Detect (Recommended)"),
            "persona": cfg.get("persona", "Friendly Forum Member"),
            "custom_system_prompt": cfg.get("custom_system_prompt", ""),
            "anythingllm_url": cfg.get("anythingllm_url", "http://localhost:3001/api/v1"),
            "anythingllm_api_key": cfg.get("anythingllm_api_key", ""),
            "groq_api_key": cfg.get("groq_api_key", ""),
            "gemini_api_key": cfg.get("gemini_api_key", ""),
            "workspace_slug": cfg.get("workspace_slug", "content"),
            "ollama_url": cfg.get("ollama_url", "http://localhost:11434"),
            "blueprints": backend.load_recipes(),
            "saved_sites": self.get_saved_sites(),
            "queue": self.queue,
            "live_posts": getattr(self, "live_posts", []),
            "queue_count": len(self.queue),
            "history_count": len(backend.load_history()),
            "gsheet_sync_url": cfg.get("gsheet_sync_url", backend.DEFAULT_GSHEET_URL),
            "gsheet_webhook_url": cfg.get("gsheet_webhook_url", ""),
            "gsheet_auto_sync": cfg.get("gsheet_auto_sync", True),
            "auto_retry_failed": cfg.get("auto_retry_failed", True),
            "max_retries": cfg.get("max_retries", 2),
            "is_running": self.is_running,
            "logs": self.logs_history[-100:]
        }

    def auto_spintax(self, text: str) -> Dict[str, Any]:
        """Converts raw text into rich spintax using intelligent synonym engine."""
        try:
            spintax_res = backend.generate_spintax_variations(text, self.cfg)
            return {"success": True, "spintax": spintax_res}
        except Exception as e:
            return {"success": False, "message": str(e), "spintax": text}

    def save_proxy_settings(self, proxy_server: str, proxy_list: str = "", rotation_enabled: bool = False) -> Dict[str, Any]:
        """Saves proxy and IP rotation configuration."""
        cfg = backend.load_config()
        cfg["proxy_server"] = str(proxy_server).strip()
        cfg["proxy_list"] = str(proxy_list).strip()
        cfg["proxy_rotation_enabled"] = bool(rotation_enabled)
        backend.save_config(cfg)
        self.cfg = cfg
        self.notify_ui("🌐 Proxy configuration saved successfully!", "success", log_color="text-emerald-400")
        return {"success": True}

    def save_gsheet_settings(self, gsheet_url: str, auto_sync: bool = True, webhook_url: str = None) -> Dict[str, Any]:
        """Saves the target Google Sheet URL, 0.2s Apps Script Webhook URL, and auto-sync toggle."""
        cfg = backend.load_config()
        cfg["gsheet_sync_url"] = (gsheet_url or backend.DEFAULT_GSHEET_URL).strip()
        cfg["gsheet_auto_sync"] = bool(auto_sync)
        if webhook_url is not None:
            cfg["gsheet_webhook_url"] = str(webhook_url).strip()
        backend.save_config(cfg)
        self.cfg = cfg
        mode_str = "⚡ 0.2s Webhook + Sheet A1+" if cfg.get("gsheet_webhook_url") else "📊 Direct Sheet A1+"
        self.notify_ui(f"{mode_str} Auto-Sync settings saved!", "success", log_color="text-emerald-400")
        return {
            "success": True,
            "gsheet_sync_url": cfg["gsheet_sync_url"],
            "gsheet_webhook_url": cfg.get("gsheet_webhook_url", ""),
            "gsheet_auto_sync": cfg["gsheet_auto_sync"]
        }

    def get_gsheet_webhook_script(self) -> Dict[str, Any]:
        """Returns the ready-to-paste 0.2s Google Apps Script code for Column A (A1+) instant syncing."""
        return {
            "success": True,
            "code": getattr(backend, "APPS_SCRIPT_WEBHOOK_CODE", ""),
            "sheet_url": self.cfg.get("gsheet_sync_url", backend.DEFAULT_GSHEET_URL)
        }

    def save_retry_settings(self, auto_retry: bool = True, max_retries: int = 2) -> Dict[str, Any]:
        """Saves Auto-Retry & Failed Queue Healer settings."""
        cfg = backend.load_config()
        cfg["auto_retry_failed"] = bool(auto_retry)
        try:
            cfg["max_retries"] = max(1, min(5, int(max_retries)))
        except Exception:
            cfg["max_retries"] = 2
        backend.save_config(cfg)
        self.cfg = cfg
        return {"success": True, "auto_retry_failed": cfg["auto_retry_failed"], "max_retries": cfg["max_retries"]}

    def sync_live_urls_to_sheet(self, urls: list = None, gsheet_url: str = None) -> Dict[str, Any]:
        """Manually or automatically pushes all verified live URLs to Column A (A1, A2, A3...) of the Google Sheet."""
        target_sheet = (gsheet_url or self.cfg.get("gsheet_sync_url") or backend.DEFAULT_GSHEET_URL).strip()
        self.cfg["gsheet_sync_url"] = target_sheet
        backend.save_config(self.cfg)

        urls_to_push = []
        if urls and isinstance(urls, list):
            urls_to_push = [str(u).strip() for u in urls if str(u).strip().startswith("http")]
        if not urls_to_push:
            urls_to_push = [lp.get("url") for lp in getattr(self, "live_posts", []) if lp.get("url")]
        if not urls_to_push:
            urls_to_push = [q.get("url") for q in self.queue if q.get("url") and backend.is_valid_live_post_url(q.get("url"))]

        if not urls_to_push:
            return {"success": False, "message": "No verified live URLs available to sync yet."}

        def _bg_sync():
            ok, msg = backend.sync_urls_to_google_sheet_column_a(
                urls_to_push,
                sheet_url=target_sheet,
                log_fn=lambda m: self.log_to_ui(m, "text-emerald-300")
            )
            self.notify_ui(msg, "success" if ok else "warn")

        threading.Thread(target=_bg_sync, daemon=True).start()
        return {"success": True, "message": f"Syncing {len(urls_to_push)} live URL(s) to Google Sheet Column A (starting at A1)..."}

    def verify_url(self, url: str) -> Dict[str, Any]:
        """Verifies any live post URL in incognito mode on demand and auto-adds to Google Sheet A1+ if verified."""
        url = (url or "").strip()
        if not url:
            return {"success": False, "verified": False, "message": "No URL provided."}
        self.log_to_ui(f"🛡️ Verifying URL in Incognito Mode: {url}", "text-sky-400")
        is_verified, verified_url = backend.verify_url_incognito(url, log_fn=lambda m: self.log_to_ui(m, "text-slate-300"))
        final_u = verified_url or url
        if is_verified and self.cfg.get("gsheet_auto_sync", True):
            threading.Thread(
                target=backend.sync_urls_to_google_sheet_column_a,
                args=([final_u], self.cfg.get("gsheet_sync_url", backend.DEFAULT_GSHEET_URL), lambda m: self.log_to_ui(m, "text-emerald-300"), None),
                daemon=True
            ).start()
        return {"success": True, "verified": is_verified, "url": final_u}

    def analyze_unknown_site(self, url: str = None) -> Dict[str, Any]:
        """
        Runs the Autonomous Unknown-Site Pre-Flight HTML Analyzer + Live DOM Scanner on any target URL,
        maps Title/Body/Submit selectors, and auto-saves a reusable Site Blueprint.
        """
        target = (url or self.cfg.get("board_url") or "").strip()
        if not target or not target.startswith("http"):
            return {"success": False, "message": "Please enter a valid http/https Target Board URL first."}

        self.notify_ui(f"🧭 Analyzing unknown site structure: {target}...", "info", log_color="text-sky-300")
        preflight = backend.preflight_html_site_analyzer(target, log_fn=lambda m: self.log_to_ui(m, "text-emerald-300"))
        effective_url = preflight.get("create_url") or target

        # Also run a fast headless live DOM scan if selectors weren't all in static HTML
        if sync_playwright is not None and (not preflight.get("editor_selector") or not preflight.get("submit_selector")):
            try:
                with sync_playwright() as p:
                    b = backend.launch_safe_browser(p, headless=True)
                    if b:
                        try:
                            sess_file = backend.get_session_path_for_url(target)
                            c_kwargs = {"storage_state": str(sess_file)} if sess_file.exists() else {}
                            ctx = b.new_context(**c_kwargs)
                            pg = ctx.new_page()
                            pg.goto(effective_url, wait_until="domcontentloaded", timeout=25000)
                            time.sleep(2.0)
                            scan = backend._scan_and_tag_composer_dom(pg)
                            if scan.get("title") and not preflight.get("title_selector"):
                                preflight["title_selector"] = scan["title"].get("reusable_selector", "")
                            if scan.get("body") and not preflight.get("editor_selector"):
                                preflight["editor_selector"] = scan["body"].get("reusable_selector", "")
                        finally:
                            try:
                                b.close()
                            except Exception:
                                pass
            except Exception as e:
                self.log_to_ui(f"Live DOM scan note: {e}", "text-slate-400")

        domain = urllib.parse.urlparse(effective_url).netloc.replace("www.", "").lower()
        bp_name = f"Auto: {domain}"
        recipes = backend.load_recipes()
        if preflight.get("title_selector") or preflight.get("editor_selector"):
            recipes[bp_name] = {
                "name": bp_name,
                "board_url": effective_url,
                "domain_pattern": domain,
                "login_url": target,
                "reply_selector": preflight.get("reply_selector", ""),
                "title_selector": preflight.get("title_selector", ""),
                "editor_selector": preflight.get("editor_selector", ""),
                "submit_selector": preflight.get("submit_selector", ""),
                "steps": [],
                "raw_post_code": []
            }
            backend.save_recipes(recipes)
            self.notify_ui(
                f"✅ Mapped '{preflight.get('cms')}' & saved Blueprint '{bp_name}'!",
                "success",
                log_color="text-emerald-400"
            )
        else:
            self.notify_ui(
                f"🧭 Detected '{preflight.get('cms')}'. Autonomous 6-Stage Agent will navigate dynamically on post!",
                "info",
                log_color="text-sky-300"
            )

        return {
            "success": True,
            "cms": preflight.get("cms", "Unknown Custom Site"),
            "create_url": effective_url,
            "preflight": preflight,
            "blueprints": recipes,
            "message": f"Analyzed {domain}: {preflight.get('cms')}"
        }

    def clear_logs(self) -> Dict[str, Any]:
        """Clears all session logs in memory so previous sessions do not persist."""
        self.logs_history.clear()
        return {"success": True, "message": "Logs reset successfully."}

    def get_logs(self, since: int = 0) -> List[Dict[str, str]]:
        """Returns logs for polling clients."""
        try:
            since = int(since)
            return self.logs_history[since:]
        except Exception:
            return self.logs_history[-50:]

    def save_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Saves configuration settings."""
        cfg = backend.load_config()
        cfg.update(settings)
        backend.save_config(cfg)
        self.cfg = cfg
        self.notify_ui("💾 Settings saved successfully!", "success", log_color="text-emerald-400")
        return {"success": True}

    # =========================================================================
    # LOGIN & BROWSER SESSION MANAGEMENT
    # =========================================================================
    def start_login_session(self, login_url: str = None) -> Dict[str, Any]:
        """
        Launches a Google-OAuth-Safe Native Browser (Zero-Automation CDP Delay Mode)
        so 'Sign in with Google' (accounts.google.com) never blocks login, and saves cookies.
        """
        if self.is_running:
            return {"success": False, "message": "A task is already running."}

        target_login = (login_url or self.cfg.get("login_url") or backend.DEFAULT_LOGIN_URL).strip()
        target_board = (self.cfg.get("board_url") or target_login).strip()
        sess_file = backend.get_session_path_for_url(target_board)
        login_sess_file = backend.get_session_path_for_url(target_login)
        profile_dir = backend.get_profile_dir_for_url(target_board)

        self.is_running = True
        self.stop_event.clear()
        self.save_requested = False

        self.notify_ui(
            f"🔑 Opening Google-Safe Browser for login: {target_login}",
            "info",
            log_color="text-sky-300"
        )

        def _export_profile_cookies_fallback(p_inst):
            """Exports cookies from persistent profile_dir after user closes native Chrome window."""
            try:
                temp_ctx = backend.launch_google_safe_persistent_context(p_inst, profile_dir, headless=True)
                if temp_ctx:
                    temp_ctx.storage_state(path=str(sess_file))
                    temp_ctx.storage_state(path=str(login_sess_file))
                    temp_ctx.storage_state(path=str(backend.SESSION_PATH))
                    temp_ctx.close()
                    return True
            except Exception:
                pass
            return False

        def _login_thread():
            if sync_playwright is None:
                self.notify_ui("❌ Playwright is not installed.", "error", log_color="text-rose-400")
                self.is_running = False
                return

            with sync_playwright() as p:
                ext_path = backend.get_or_create_autofill_extension()
                proc, cdp_port = backend.launch_native_chrome_for_google_login(
                    p,
                    profile_dir=profile_dir,
                    target_url=target_login,
                    ext_path=ext_path,
                    log_fn=lambda msg: self.log_to_ui(msg, "text-emerald-400")
                )

                # PATH A: Native OS Chrome launched WITHOUT Playwright CDP pipe attached during Google Sign-In!
                if proc is not None and cdp_port is not None:
                    self.active_context = "NATIVE_CHROME_CDP"
                    self.active_native_proc = proc
                    self._empty_tab_streak = 0
                    self.notify_ui(
                        "👉 Google-Safe Browser opened! You can now use 'Continue with Google' or normal login. Click '💾 Save' or close the browser when done.",
                        "warn",
                        log_color="text-amber-300"
                    )
                    saved = False
                    try:
                        deadline = time.time() + 600
                        while time.time() < deadline and not self.stop_event.is_set():
                            # Check if user clicked '💾 Save' in UI
                            if self.save_requested:
                                self.save_requested = False
                                try:
                                    cdp_browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
                                    ctx = cdp_browser.contexts[0] if cdp_browser.contexts else cdp_browser.new_context()
                                    ctx.storage_state(path=str(sess_file))
                                    ctx.storage_state(path=str(login_sess_file))
                                    ctx.storage_state(path=str(backend.SESSION_PATH))
                                    self.notify_ui(f"✅ Google & Site Session saved to {sess_file.name}!", "success", log_color="text-emerald-400")
                                    saved = True
                                    break
                                except Exception as e:
                                    self.log_to_ui(f"Save note: {e}", "text-slate-400")

                            # Check if user closed the native browser window (require process exit or 3 consecutive empty tab checks)
                            open_tabs = backend.get_cdp_open_tabs(cdp_port)
                            if open_tabs is not None and len(open_tabs) == 0:
                                empty_tab_streak = getattr(self, "_empty_tab_streak", 0) + 1
                                self._empty_tab_streak = empty_tab_streak
                            else:
                                self._empty_tab_streak = 0
                            if proc.poll() is not None or getattr(self, "_empty_tab_streak", 0) >= 3:
                                self.log_to_ui("Browser closed. Exporting saved profile cookies...", "text-slate-400")
                                try:
                                    proc.terminate()
                                except Exception:
                                    pass
                                time.sleep(0.6)
                                if _export_profile_cookies_fallback(p):
                                    self.notify_ui(f"✅ Session saved from profile to {sess_file.name}!", "success", log_color="text-emerald-400")
                                    saved = True
                                break

                            time.sleep(1.0)
                    finally:
                        try:
                            proc.terminate()
                        except Exception:
                            pass
                        self.active_context = None
                        self.is_running = False
                    return

                # PATH B: Fallback to Google-Safe Persistent Context if native CDP process couldn't start
                context = backend.launch_google_safe_persistent_context(
                    p,
                    profile_dir=profile_dir,
                    headless=False,
                    ext_path=ext_path,
                    log_fn=lambda msg: self.log_to_ui(msg, "text-slate-400")
                )
                if not context:
                    self.notify_ui("❌ Could not launch browser. Run 'playwright install chromium' in terminal.", "error", log_color="text-rose-400")
                    self.is_running = False
                    return

                self.active_context = context
                page = context.pages[0] if context.pages else context.new_page()

                saved = False
                try:
                    page.goto(target_login, wait_until="domcontentloaded", timeout=60000)
                    self.notify_ui("👉 Please log in (Google Sign-In enabled). Click '💾 Save' anytime or close the browser when done.", "warn", log_color="text-amber-300")

                    deadline = time.time() + 600
                    while time.time() < deadline and not self.stop_event.is_set():
                        if self.save_requested:
                            self.save_requested = False
                            time.sleep(0.5)
                            try:
                                context.storage_state(path=str(sess_file))
                                context.storage_state(path=str(login_sess_file))
                                context.storage_state(path=str(backend.SESSION_PATH))
                                self.notify_ui(f"✅ Session saved successfully to {sess_file.name}!", "success", log_color="text-emerald-400")
                                saved = True
                                break
                            except Exception as e:
                                self.log_to_ui(f"Save note: {e}", "text-slate-400")

                        active_pages = [pg for pg in context.pages if not pg.is_closed()]
                        if not active_pages:
                            self.log_to_ui("Browser closed. Capturing cookies...", "text-slate-400")
                            try:
                                context.storage_state(path=str(sess_file))
                                context.storage_state(path=str(login_sess_file))
                                context.storage_state(path=str(backend.SESSION_PATH))
                                self.notify_ui(f"✅ Session saved to {sess_file.name}!", "success", log_color="text-emerald-400")
                                saved = True
                            except Exception:
                                pass
                            break

                        for pg in active_pages:
                            pg_url = (pg.url or "").lower()
                            if any(g in pg_url for g in ("accounts.google.", "myaccount.google.", "google.com/o/oauth", "gstatic.com", "googleapis.com")):
                                continue
                            if not saved and (backend.is_forum_page_logged_in(pg) or backend.is_proboards_page_logged_in(pg)):
                                try:
                                    context.storage_state(path=str(sess_file))
                                    context.storage_state(path=str(login_sess_file))
                                    context.storage_state(path=str(backend.SESSION_PATH))
                                    self.notify_ui(f"✅ Auto-saved login cookies to {sess_file.name}! (Close browser or click '💾 Save Session' when finished)", "success", log_color="text-emerald-400")
                                    saved = True
                                except Exception:
                                    pass
                        time.sleep(1)

                except Exception as e:
                    self.log_to_ui(f"Login notice: {e}", "text-slate-400")
                finally:
                    try:
                        context.close()
                    except Exception:
                        pass
                    self.active_context = None
                    self.is_running = False

        threading.Thread(target=_login_thread, daemon=True).start()
        return {"success": True, "message": "Google-Safe Login session initiated."}

    def export_session_json(self, board_url: str = None) -> Dict[str, Any]:
        """Exports the active domain's storage_state session JSON so the user can upload it to a Cloud instance."""
        target = (board_url or self.cfg.get("board_url") or backend.DEFAULT_BOARD).strip()
        sess_file = backend.get_session_path_for_url(target)
        if not sess_file.exists():
            sess_file = backend.SESSION_PATH
        if not sess_file.exists():
            return {"success": False, "message": "No saved session cookie file found yet. Log in first!"}
        try:
            raw_json = sess_file.read_text(encoding="utf-8")
            return {
                "success": True,
                "filename": sess_file.name,
                "content": raw_json,
                "message": f"Exported session cookies ({sess_file.name})!"
            }
        except Exception as e:
            return {"success": False, "message": str(e)}

    def upload_session_json(self, json_content: str, board_url: str = None) -> Dict[str, Any]:
        """Imports a storage_state session JSON uploaded from the user's PC into the Cloud server."""
        if not json_content or not str(json_content).strip():
            return {"success": False, "message": "Uploaded session file is empty."}
        try:
            parsed = json.loads(json_content)
            if not isinstance(parsed, dict) or ("cookies" not in parsed and "origins" not in parsed):
                return {"success": False, "message": "Invalid Playwright storage_state JSON format."}
            target = (board_url or self.cfg.get("board_url") or backend.DEFAULT_BOARD).strip()
            sess_file = backend.get_session_path_for_url(target)
            sess_file.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
            backend.SESSION_PATH.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
            cookie_cnt = len(parsed.get("cookies", []))
            self.notify_ui(
                f"☁️ Uploaded {cookie_cnt} login cookies to Cloud Session ({sess_file.name})!",
                "success",
                log_color="text-emerald-400"
            )
            return {"success": True, "message": f"Uploaded {cookie_cnt} cookies to {sess_file.name}!"}
        except Exception as e:
            return {"success": False, "message": f"Failed to parse session JSON: {e}"}

    def save_session(self) -> Dict[str, Any]:
        """Captures cookies from active browser and also confirms Live Mode login if waiting."""
        if self.active_context or self.is_running:
            self.save_requested = True
            self.live_user_confirmed.set()
            return {"success": True, "message": "Saving session & confirming login..."}
        return {"success": False, "message": "No active browser session open."}

    # =========================================================================
    # QUEUE POSTING ENGINE
    # =========================================================================
    def start_posting_queue(self, board_url: str = None, login_url: str = None, arg3: Any = None,
                            arg4: Any = False, arg5: Any = 3.0, arg6: Any = 6.0, direct_links: list = None,
                            concurrency: Any = 2) -> Dict[str, Any]:
        """
        Posts the entire queue using saved session cookies across 1 to 4 concurrent browser tab workers.
        Defensively handles both 5-arg, 6-arg, and 8-arg signatures from any UI version.
        """
        if self.is_running:
            return {"success": False, "message": "Another task is currently running."}

        # Defensively detect if arg3 is headless boolean or platform string
        if isinstance(arg3, bool):
            headless = arg3
            platform = self.cfg.get("platform", "Auto-Detect (Recommended)")
            delay_min = float(arg4) if arg4 is not None else 3.0
            delay_max = float(arg5) if arg5 is not None else 6.0
        else:
            platform = str(arg3) if arg3 else self.cfg.get("platform", "Auto-Detect (Recommended)")
            headless = bool(arg4)
            delay_min = float(arg5) if arg5 is not None else 3.0
            delay_max = float(arg6) if arg6 is not None else 6.0

        try:
            num_workers = max(1, min(4, int(concurrency if concurrency is not None else self.cfg.get("concurrency", 2))))
        except Exception:
            num_workers = 2

        self.cfg["concurrency"] = num_workers
        backend.save_config(self.cfg)

        # Strictly enforce Python boolean type for Playwright
        headless_bool = True if (str(headless).lower() in ["true", "1"] or headless is True) else False

        pending_indices = [
            idx for idx, q in enumerate(self.queue)
            if "pending" in q.get("status", "").lower() or "fail" in q.get("status", "").lower()
        ]
        if not pending_indices:
            return {"success": False, "message": "No pending items in queue to post."}

        target_board = (board_url or self.cfg.get("board_url") or backend.DEFAULT_BOARD).strip()
        target_login = (login_url or self.cfg.get("login_url") or backend.DEFAULT_LOGIN_URL).strip()
        target_platform = (platform or self.cfg.get("platform") or "Auto-Detect (Recommended)").strip()

        if "themoviedb.org" in target_board.lower():
            target_platform = "TMDb (The Movie Database)"

        sess_file = backend.get_session_path_for_url(target_board)
        if not sess_file.exists():
            sess_file = backend.SESSION_PATH

        actual_workers = min(num_workers, len(pending_indices))
        self.is_running = True
        self.stop_event.clear()
        mode_label = f"{actual_workers} Concurrent Tabs" if actual_workers > 1 else "1 Tab (Sequential)"
        self.notify_ui(
            f"🚀 Starting queue runner ({len(pending_indices)} items • {mode_label}) on {target_platform}...",
            "info",
            log_color="text-indigo-400"
        )

        def _post_coordinator():
            if sync_playwright is None:
                self.notify_ui("❌ Playwright is not installed.", "error", log_color="text-rose-400")
                self.is_running = False
                return

            work_q = py_queue.Queue()
            for idx in pending_indices:
                work_q.put(idx)

            queue_lock = threading.Lock()
            stats = {"posted": 0}
            active_browsers = []

            def _tab_worker(worker_id: int):
                if worker_id > 1:
                    time.sleep((worker_id - 1) * 0.85)
                if self.stop_event.is_set():
                    return

                prefix = f"[Tab #{worker_id}] " if actual_workers > 1 else ""
                with sync_playwright() as p:
                    browser = backend.launch_safe_browser(
                        p,
                        headless=headless_bool,
                        log_fn=lambda msg, pfx=prefix: self.log_to_ui(f"{pfx}{msg}", "text-slate-400")
                    )
                    if not browser:
                        self.notify_ui(f"❌ {prefix}Could not launch browser for posting.", "error", log_color="text-rose-400")
                        return

                    with queue_lock:
                        active_browsers.append(browser)

                    context_kwargs = {"user_agent": backend.CLEAN_CHROME_UA}
                    if sess_file.exists():
                        context_kwargs["storage_state"] = str(sess_file)

                    context = browser.new_context(**context_kwargs)
                    context.add_init_script(backend.INIT_STEALTH_JS)
                    if worker_id == 1:
                        self.active_context = context
                    page = context.new_page()

                    while not self.stop_event.is_set():
                        try:
                            i = work_q.get_nowait()
                        except py_queue.Empty:
                            break

                        with queue_lock:
                            item = self.queue[i]
                            item["status"] = f"⚡ [Tab #{worker_id}] Posting..." if actual_workers > 1 else "⚡ In Progress..."
                            raw_title = item.get("title", "")
                            raw_body = item.get("body", "")

                        self.notify_ui(
                            f"{prefix}Posting #{i+1}: {raw_title[:38]}...",
                            "info",
                            queue=self.queue,
                            log_color="text-sky-300"
                        )

                        title_text = backend.process_spintax(raw_title)
                        body_text = backend.process_spintax(raw_body)

                        active_target_url = target_board
                        if direct_links and len(direct_links) > 0:
                            clean_links = [l.strip() for l in direct_links if str(l).strip().startswith("http")]
                            if clean_links:
                                active_target_url = clean_links[i % len(clean_links)]
                                self.log_to_ui(
                                    f"⚡ {prefix}Direct Link #{(i % len(clean_links)) + 1}: {active_target_url}",
                                    "text-sky-300"
                                )

                        worker_log_fn = lambda msg, wid=worker_id, idx_num=i+1: self.log_to_ui(f"[Tab #{wid} • #{idx_num}] {msg}", "text-slate-300")
                        try:
                            success, live_url = backend.dispatch_create_thread(
                                page=page,
                                platform_choice=target_platform,
                                board_url=active_target_url,
                                title_text=title_text,
                                body_text=body_text,
                                log_fn=worker_log_fn,
                                post_index=i
                            )
                            # Mandatory Incognito Verification on every tab's returned URL before accepting it!
                            if success and live_url and backend.is_valid_live_post_url(live_url, active_target_url):
                                is_incog_ok, verified_live_url = backend.verify_url_incognito(
                                    live_url,
                                    page=page,
                                    log_fn=worker_log_fn,
                                    browser=browser,
                                    expected_title=title_text
                                )
                                if is_incog_ok and verified_live_url:
                                    live_url = verified_live_url
                                else:
                                    success = False
                                    live_url = None
                            else:
                                success = False
                                live_url = None
                        except Exception as exc:
                            self.log_to_ui(f"❌ {prefix}Worker error on item #{i+1}: {exc}", "text-rose-400")
                            success, live_url = False, None

                        with queue_lock:
                            if success and live_url:
                                item["status"] = f"✅ [Tab #{worker_id}] Live" if actual_workers > 1 else "✅ Done (Live)"
                                item["url"] = live_url
                                item["tab"] = worker_id
                                stats["posted"] += 1
                                backend.record_history(live_url)
                                existing_lp = next((lp for lp in self.live_posts if lp.get("index") == i + 1), None)
                                if existing_lp:
                                    existing_lp.update({
                                        "tab": worker_id,
                                        "title": title_text,
                                        "url": live_url,
                                        "time": time.strftime("%H:%M:%S"),
                                        "verified": True
                                    })
                                else:
                                    self.live_posts.append({
                                        "index": i + 1,
                                        "tab": worker_id,
                                        "title": title_text,
                                        "url": live_url,
                                        "time": time.strftime("%H:%M:%S"),
                                        "verified": True
                                    })
                                self.notify_ui(
                                    f"✅ {prefix}Success (#{i+1}): {title_text[:34]} -> {live_url}",
                                    "success",
                                    queue=self.queue,
                                    log_color="text-emerald-400"
                                )
                                self.log_to_ui(f"🔗 {prefix}Live URL (#{i+1}): {live_url}", "text-sky-400")
                                if self.cfg.get("gsheet_auto_sync", True):
                                    threading.Thread(
                                        target=backend.sync_urls_to_google_sheet_column_a,
                                        args=([live_url], self.cfg.get("gsheet_sync_url", backend.DEFAULT_GSHEET_URL), worker_log_fn, None),
                                        daemon=True
                                    ).start()
                            else:
                                item["status"] = "❌ Failed"
                                self.notify_ui(
                                    f"❌ {prefix}Failed to post item #{i+1}",
                                    "error",
                                    queue=self.queue,
                                    log_color="text-rose-400"
                                )

                        work_q.task_done()

                        if not work_q.empty() and not self.stop_event.is_set():
                            delay = random.uniform(max(1.0, delay_min), max(delay_min + 1.0, delay_max))
                            self.log_to_ui(f"⏳ {prefix}Waiting {delay:.1f}s before next post...", "text-slate-500")
                            time.sleep(delay)

                    try:
                        browser.close()
                    except Exception:
                        pass

            with concurrent.futures.ThreadPoolExecutor(max_workers=actual_workers) as executor:
                futures = [executor.submit(_tab_worker, wid + 1) for wid in range(actual_workers)]
                concurrent.futures.wait(futures)

            # =====================================================================
            # 🔄 FEATURE #4: AUTO-RETRY & FAILED QUEUE HEALER (1-3 ROUNDS)
            # =====================================================================
            auto_heal_on = bool(self.cfg.get("auto_retry_failed", True))
            max_heal_rounds = int(self.cfg.get("max_retries", 2) or 2)
            healed_count = 0

            if auto_heal_on and not self.stop_event.is_set():
                for heal_round in range(1, max_heal_rounds + 1):
                    if self.stop_event.is_set():
                        break
                    failed_indices = [
                        idx for idx in pending_indices
                        if idx < len(self.queue) and (
                            "fail" in self.queue[idx].get("status", "").lower()
                            or "❌" in self.queue[idx].get("status", "")
                        )
                    ]
                    if not failed_indices:
                        break

                    self.notify_ui(
                        f"🩹 [Auto-Healer Round #{heal_round}/{max_heal_rounds}] Healing {len(failed_indices)} failed post(s) with fresh browser context...",
                        "warn",
                        queue=self.queue,
                        log_color="text-amber-300"
                    )
                    for f_idx in failed_indices:
                        self.queue[f_idx]["status"] = f"🩹 [Healer #{heal_round}] Queued"
                        work_q.put(f_idx)
                    self.notify_ui(f"🩹 Healer Round #{heal_round} queued {len(failed_indices)} item(s)", "info", queue=self.queue)

                    before_posted = stats["posted"]
                    heal_workers = min(actual_workers, len(failed_indices))
                    time.sleep(2.0)
                    with concurrent.futures.ThreadPoolExecutor(max_workers=heal_workers) as heal_exec:
                        h_futures = [heal_exec.submit(_tab_worker, wid + 1) for wid in range(heal_workers)]
                        concurrent.futures.wait(h_futures)
                    healed_this_round = max(0, stats["posted"] - before_posted)
                    healed_count += healed_this_round
                    self.log_to_ui(
                        f"🩹 [Auto-Healer Round #{heal_round}] Rescued {healed_this_round}/{len(failed_indices)} post(s)!",
                        "text-emerald-400" if healed_this_round > 0 else "text-amber-300"
                    )

            self.active_context = None
            self.is_running = False
            heal_suffix = f" (including {healed_count} healed on retry!)" if healed_count > 0 else ""
            self.notify_ui(
                f"🎉 Batch run finished ({mode_label})! Posted {stats['posted']} item(s){heal_suffix}.",
                "success",
                queue=self.queue,
                log_color="text-emerald-400"
            )

        threading.Thread(target=_post_coordinator, daemon=True).start()
        return {"success": True, "message": f"Queue runner started ({mode_label})!"}

    # =========================================================================
    # LIVE INTERACTIVE POST MODE (⚡ Login & Post Live)
    # =========================================================================
    def start_live_post(self, board_url: str = None, login_url: str = None, platform: str = None,
                        delay_min: float = 3.0, delay_max: float = 6.0,
                        direct_links: list = None, concurrency: Any = 2) -> Dict[str, Any]:
        """
        Interactive Mode:
        Opens browser to login URL, lets user log in, saves session cookies, and then runs the queue
        across 1 to 4 concurrent browser tab workers so all tabs' live URLs are captured and displayed.
        """
        if self.is_running:
            return {"success": False, "message": "Another task is running."}

        target_board = (board_url or self.cfg.get("board_url") or backend.DEFAULT_BOARD).strip()
        target_login = (login_url or self.cfg.get("login_url") or backend.DEFAULT_LOGIN_URL).strip()
        target_platform = (platform or self.cfg.get("platform") or "Auto-Detect (Recommended)").strip()

        try:
            num_workers = max(1, min(4, int(concurrency if concurrency is not None else self.cfg.get("concurrency", 2))))
        except Exception:
            num_workers = 2

        if "waiverelectronic.com" in target_board.lower() or "waiver" in target_platform.lower():
            target_platform = "WaiverElectronic (waiverelectronic.com)"
            if not target_login or "proboards" in target_login.lower():
                target_login = "https://app.waiverelectronic.com/login"
            if not target_board or "proboards" in target_board.lower():
                target_board = "https://app.waiverelectronic.com/profile/home"
        elif "themoviedb.org" in target_board.lower() or "tmdb" in target_platform.lower():
            target_platform = "TMDb (The Movie Database)"
            if not target_login or "proboards" in target_login.lower():
                target_login = "https://www.themoviedb.org/login"
            if not target_board or "proboards" in target_board.lower():
                target_board = "https://www.themoviedb.org/movie/new"

        profile_dir = backend.get_profile_dir_for_url(target_board)
        sess_file = backend.get_session_path_for_url(target_board)

        self.is_running = True
        self.stop_event.clear()
        self.live_user_confirmed.clear()
        self.notify_ui(f"⚡ Launching Live Interactive Session: {target_login}", "info", log_color="text-purple-400")

        def _interactive_worker():
            with sync_playwright() as p:
                ext_path = backend.get_or_create_autofill_extension()
                launch_args = list(backend.STEALTH_ARGS)
                if ext_path and ext_path.exists():
                    ext_str = str(ext_path).replace("\\", "/")
                    launch_args.extend([f"--disable-extensions-except={ext_str}", f"--load-extension={ext_str}"])

                # Launch Native Chrome WITHOUT Playwright CDP attached while user completes Google Sign-In!
                native_proc, cdp_port = backend.launch_native_chrome_for_google_login(
                    p,
                    profile_dir=profile_dir,
                    target_url=target_login,
                    ext_path=ext_path,
                    log_fn=lambda msg: self.log_to_ui(msg, "text-emerald-400")
                )
                ctx = None
                page = None
                if native_proc is not None and cdp_port is not None:
                    self.active_context = "NATIVE_CHROME_CDP"
                    self.active_native_proc = native_proc
                    self.notify_ui(
                        "👉 Google-Safe Live Browser opened! Log in (including 'Continue with Google'), then click '✅ Confirm Login' in the UI!",
                        "warn",
                        log_color="text-amber-300"
                    )
                    self.live_user_confirmed.wait(timeout=300)
                    if not self.stop_event.is_set():
                        try:
                            cdp_browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
                            ctx = cdp_browser.contexts[0] if cdp_browser.contexts else cdp_browser.new_context()
                            ctx.add_init_script(backend.INIT_STEALTH_JS)
                            self.active_context = ctx
                            active_pgs = [pg for pg in ctx.pages if not pg.is_closed()]
                            page = active_pgs[-1] if active_pgs else ctx.new_page()
                        except Exception as e:
                            self.log_to_ui(f"CDP attach notice: {e}", "text-amber-300")
                else:
                    ctx = backend.launch_google_safe_persistent_context(
                        p,
                        profile_dir=profile_dir,
                        headless=False,
                        ext_path=ext_path
                    )
                    self.active_context = ctx
                    page = ctx.pages[0] if ctx.pages else ctx.new_page()
                    try:
                        page.goto(target_login, wait_until="domcontentloaded", timeout=60000)
                    except Exception as e:
                        self.log_to_ui(f"Navigation notice: {e}", "text-slate-400")

                    self.notify_ui("👉 Please log in in the opened browser window. When ready, click 'Confirm Login' in the web UI!", "warn", log_color="text-amber-300")
                    self.live_user_confirmed.wait(timeout=300)

                if self.stop_event.is_set() or page is None or page.is_closed():
                    self.log_to_ui("Live session aborted or browser closed.", "text-amber-300")
                    try:
                        if ctx:
                            ctx.close()
                    except Exception:
                        pass
                    try:
                        if native_proc:
                            native_proc.terminate()
                    except Exception:
                        pass
                    self.active_context = None
                    self.active_native_proc = None
                    self.is_running = False
                    return

                # Save storage_state so additional parallel tab workers share the exact authenticated session!
                try:
                    ctx.storage_state(path=str(sess_file))
                    ctx.storage_state(path=str(backend.SESSION_PATH))
                except Exception:
                    pass

                pending_indices = [
                    idx for idx, q in enumerate(self.queue)
                    if "done" not in q.get("status", "").lower()
                ]
                if not pending_indices:
                    pending_indices = list(range(len(self.queue)))

                actual_workers = min(num_workers, max(1, len(pending_indices)))
                self.log_to_ui(
                    f"🚀 Confirmed! Running queue across {actual_workers} tab worker(s)...",
                    "text-emerald-400"
                )

                work_q = py_queue.Queue()
                for idx in pending_indices:
                    work_q.put(idx)

                queue_lock = threading.Lock()
                stats = {"posted": 0}

                def _run_on_page(worker_id: int, worker_page):
                    prefix = f"[Tab #{worker_id}] "
                    while not self.stop_event.is_set():
                        try:
                            i = work_q.get_nowait()
                        except py_queue.Empty:
                            break

                        with queue_lock:
                            item = self.queue[i]
                            item["status"] = f"⚡ [Tab #{worker_id}] Posting..." if actual_workers > 1 else "⚡ In Progress..."
                            raw_title = item.get("title", "")
                            raw_body = item.get("body", "")

                        self.notify_ui(
                            f"{prefix}Processing #{i+1}: {raw_title[:38]}...",
                            "info",
                            queue=self.queue,
                            log_color="text-sky-300"
                        )

                        title_text = backend.process_spintax(raw_title)
                        body_text = backend.process_spintax(raw_body)

                        active_target_url = target_board
                        if direct_links and len(direct_links) > 0:
                            clean_links = [l.strip() for l in direct_links if str(l).strip().startswith("http")]
                            if clean_links:
                                active_target_url = clean_links[i % len(clean_links)]

                        w_log = lambda msg, wid=worker_id, idx_num=i+1: self.log_to_ui(f"[Tab #{wid} • #{idx_num}] {msg}", "text-slate-300")
                        try:
                            success, live_url = backend.dispatch_create_thread(
                                page=worker_page,
                                platform_choice=target_platform,
                                board_url=active_target_url,
                                title_text=title_text,
                                body_text=body_text,
                                log_fn=w_log,
                                post_index=i
                            )
                            if success and live_url and backend.is_valid_live_post_url(live_url, active_target_url):
                                is_inc_ok, ver_u = backend.verify_url_incognito(live_url, page=worker_page, log_fn=w_log, expected_title=title_text)
                                if is_inc_ok and ver_u:
                                    live_url = ver_u
                                else:
                                    success, live_url = False, None
                            else:
                                success, live_url = False, None
                        except Exception as exc:
                            self.log_to_ui(f"❌ {prefix}Error on #{i+1}: {exc}", "text-rose-400")
                            success, live_url = False, None

                        with queue_lock:
                            if success and live_url and backend.is_valid_live_post_url(live_url, active_target_url):
                                item["status"] = f"✅ [Tab #{worker_id}] Live" if actual_workers > 1 else "✅ Done (Live)"
                                item["url"] = live_url
                                item["tab"] = worker_id
                                stats["posted"] += 1
                                backend.record_history(live_url)
                                existing_lp = next((lp for lp in self.live_posts if lp.get("index") == i + 1), None)
                                if existing_lp:
                                    existing_lp.update({
                                        "tab": worker_id,
                                        "title": title_text,
                                        "url": live_url,
                                        "time": time.strftime("%H:%M:%S"),
                                        "verified": True
                                    })
                                else:
                                    self.live_posts.append({
                                        "index": i + 1,
                                        "tab": worker_id,
                                        "title": title_text,
                                        "url": live_url,
                                        "time": time.strftime("%H:%M:%S"),
                                        "verified": True
                                    })
                                self.notify_ui(
                                    f"✅ {prefix}Success (#{i+1}): {title_text[:34]} -> {live_url}",
                                    "success",
                                    queue=self.queue,
                                    log_color="text-emerald-400"
                                )
                                self.log_to_ui(f"🔗 {prefix}Live URL (#{i+1}): {live_url}", "text-sky-400")
                                if self.cfg.get("gsheet_auto_sync", True):
                                    threading.Thread(
                                        target=backend.sync_urls_to_google_sheet_column_a,
                                        args=([live_url], self.cfg.get("gsheet_sync_url", backend.DEFAULT_GSHEET_URL), w_log, None),
                                        daemon=True
                                    ).start()
                            else:
                                item["status"] = "❌ Failed"
                                self.notify_ui(f"❌ {prefix}Failed to post item #{i+1}", "error", queue=self.queue, log_color="text-rose-400")

                        work_q.task_done()

                        if not work_q.empty() and not self.stop_event.is_set():
                            delay = random.uniform(max(1.0, delay_min), max(delay_min + 1.0, delay_max))
                            self.log_to_ui(f"⏳ {prefix}Waiting {delay:.1f}s...", "text-slate-500")
                            time.sleep(delay)

                def _secondary_worker(wid: int):
                    time.sleep((wid - 1) * 0.85)
                    if self.stop_event.is_set():
                        return
                    with sync_playwright() as p2:
                        b2 = backend.launch_safe_browser(p2, headless=False)
                        if not b2:
                            return
                        c2_kwargs = {"storage_state": str(sess_file)} if sess_file.exists() else {}
                        c2 = b2.new_context(**c2_kwargs)
                        c2.add_init_script(backend.INIT_STEALTH_JS)
                        pg2 = c2.new_page()
                        try:
                            _run_on_page(wid, pg2)
                        finally:
                            try:
                                b2.close()
                            except Exception:
                                pass

                extra_threads = []
                for wid in range(2, actual_workers + 1):
                    t = threading.Thread(target=_secondary_worker, args=(wid,), daemon=True)
                    t.start()
                    extra_threads.append(t)

                # Worker 1 runs on the already-open interactive page
                _run_on_page(1, page)

                for t in extra_threads:
                    t.join()

                # 🔄 FEATURE #4: AUTO-RETRY & FAILED QUEUE HEALER IN LIVE MODE
                auto_heal_on = bool(self.cfg.get("auto_retry_failed", True))
                max_heal_rounds = int(self.cfg.get("max_retries", 2) or 2)
                if auto_heal_on and not self.stop_event.is_set() and page and not page.is_closed():
                    for heal_round in range(1, max_heal_rounds + 1):
                        if self.stop_event.is_set():
                            break
                        failed_indices = [
                            idx for idx in pending_indices
                            if idx < len(self.queue) and (
                                "fail" in self.queue[idx].get("status", "").lower()
                                or "❌" in self.queue[idx].get("status", "")
                            )
                        ]
                        if not failed_indices:
                            break
                        self.notify_ui(
                            f"🩹 [Live Auto-Healer #{heal_round}/{max_heal_rounds}] Retrying {len(failed_indices)} failed post(s)...",
                            "warn",
                            queue=self.queue,
                            log_color="text-amber-300"
                        )
                        for f_idx in failed_indices:
                            self.queue[f_idx]["status"] = f"🩹 [Healer #{heal_round}] Retrying..."
                            work_q.put(f_idx)
                        time.sleep(2.0)
                        _run_on_page(1, page)

                try:
                    if ctx:
                        ctx.close()
                except Exception:
                    pass
                try:
                    if native_proc:
                        native_proc.terminate()
                except Exception:
                    pass
                self.active_context = None
                self.active_native_proc = None
                self.is_running = False
                self.notify_ui(
                    f"🎉 Live session complete! Posted {stats['posted']} item(s).",
                    "success",
                    queue=self.queue,
                    log_color="text-emerald-400"
                )

        threading.Thread(target=_interactive_worker, daemon=True).start()
        return {"success": True, "message": "Interactive browser launched. Log in and click Confirm!"}

    def confirm_live_login(self) -> Dict[str, Any]:
        """Called when user clicks 'Confirm Login' button in UI."""
        self.live_user_confirmed.set()
        return {"success": True, "message": "Login confirmed. Automation proceeding..."}

    def stop_all(self) -> Dict[str, Any]:
        """
        Thread-safe stop handler: signals all worker loops (self.stop_event, self.live_user_confirmed)
        and terminates any native login Chrome process without violating Playwright greenlet thread affinity.
        """
        self.stop_event.set()
        self.live_user_confirmed.set()
        if getattr(self, "active_native_proc", None) is not None:
            try:
                self.active_native_proc.terminate()
            except Exception:
                pass
            self.active_native_proc = None
        self.active_context = None
        self.is_running = False
        self.notify_ui("⏹️ Stop signal sent! Halting active tasks and closing worker tabs...", "warn", log_color="text-amber-400")
        return {"success": True, "message": "Stopped."}

    def clear_cookies(self, board_url: str = None) -> Dict[str, Any]:
        """Clears cookies and profiles for target board."""
        target = (board_url or self.cfg.get("board_url") or backend.DEFAULT_BOARD).strip()
        parsed = urllib.parse.urlparse(target)
        clean_d = parsed.netloc.lower()
        if clean_d.startswith("www."): clean_d = clean_d[4:]

        p_dir = backend.get_profile_dir_for_url(target)
        import shutil
        if p_dir.exists():
            shutil.rmtree(p_dir, ignore_errors=True)

        for p in [Path.home() / f".forum_session_{clean_d}.json", backend.SESSION_PATH]:
            if p.exists():
                try: p.unlink()
                except Exception: pass

        self.notify_ui(f"🧹 Cleared session cookies for {clean_d}.", "info", log_color="text-slate-400")
        return {"success": True}

    # =========================================================================
    # QUEUE & DRAFT MANAGEMENT
    # =========================================================================
    def approve_and_queue(self, title: str, body: str) -> Dict[str, Any]:
        """Adds a draft to the queue."""
        t = str(title).strip()
        b = str(body).strip()
        if not b:
            return {"success": False, "message": "Body content cannot be empty."}
        if not t:
            t = b.splitlines()[0][:60] if b.splitlines() else "Untitled Post"

        item = {
            "num": len(self.queue) + 1,
            "title": t,
            "body": b,
            "status": "⏳ Pending",
            "url": ""
        }
        self.queue.append(item)
        backend.append_to_saved_queue_csv(item)
        self.notify_ui(f"✅ Queued: '{t[:40]}...'", "success", queue=self.queue, log_color="text-emerald-400")
        return {"success": True, "queue": self.queue,
            "live_posts": getattr(self, "live_posts", []), "count": len(self.queue)}

    def delete_queue_item(self, index: int) -> Dict[str, Any]:
        try:
            idx = int(index)
            if 0 <= idx < len(self.queue):
                del self.queue[idx]
                for i, item in enumerate(self.queue): item["num"] = i + 1
                self.notify_ui("Deleted item from queue.", "info", queue=self.queue)
                return {"success": True, "queue": self.queue}
        except Exception as e:
            return {"success": False, "message": str(e)}
        return {"success": False, "message": "Invalid index."}

    def clear_queue(self) -> Dict[str, Any]:
        self.queue = []
        self.notify_ui("Queue cleared.", "info", queue=self.queue, log_color="text-slate-400")
        return {"success": True, "queue": []}

    def reset_failed(self) -> Dict[str, Any]:
        count = 0
        for item in self.queue:
            if "fail" in item.get("status", "").lower():
                item["status"] = "⏳ Pending"
                count += 1
        self.notify_ui(f"Reset {count} failed items to Pending.", "info", queue=self.queue)
        return {"success": True, "queue": self.queue}

    def load_google_links(self, links_text: str) -> Dict[str, Any]:
        urls = [u.strip() for u in str(links_text).splitlines() if u.strip().startswith("http")]
        if not urls:
            return {"success": False, "message": "No valid links provided."}

        new_items = []
        for u in urls:
            try:
                res_type, items = backend.fetch_single_google_url(u)
                for t, b in items:
                    new_items.append({"num": len(self.queue) + len(new_items) + 1, "title": t, "body": b, "status": "⏳ Pending", "url": ""})
            except Exception as e:
                self.log_to_ui(f"Error loading {u[:30]}: {e}", "text-rose-400")

        if new_items:
            self.queue.extend(new_items)
            self.notify_ui(f"Loaded {len(new_items)} items from Google links!", "success", queue=self.queue, log_color="text-emerald-400")
            return {"success": True, "count": len(new_items), "queue": self.queue}
        return {"success": False, "message": "Could not parse Google links. Ensure sharing is public."}

    def generate_ai_post(self, topic: str, platform: str = None, max_tokens: int = 4096) -> Dict[str, Any]:
        """Generates an AI post draft using local Gemma 3n / AnythingLLM / Ollama."""
        try:
            platform = platform or self.cfg.get("platform", "Auto-Detect (Recommended)")
            self.log_to_ui(f"Calling local AI for: '{topic[:40]}...' ({platform})", "text-sky-300")
            sys_prompt = self.cfg.get("custom_system_prompt", "")
            item = backend.generate_ai_post_item(topic, target_platform=platform, max_tokens=max_tokens, custom_system_prompt=sys_prompt)
            self.log_to_ui(f"✨ Generated draft: '{item['title'][:50]}'", "text-emerald-400")
            return {"success": True, "title": item["title"], "body": item["body"]}
        except Exception as e:
            self.log_to_ui(f"AI Generation error: {e}", "text-rose-400")
            return {"success": False, "message": str(e)}
