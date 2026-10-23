import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
import threading
import json
import time
import re
import csv
import io
import socket
import urllib.request
import urllib.parse
import xmlrpc.client
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ==============================================================================
# CLOUD ACCESS CONTROL CONFIGURATION (GOOGLE SHEET)
# ==============================================================================
AUTH_SHEET_ID = "1TcPjoKOT4jfH9n0xhxjnKVgCCqV7Y-pgKeGFCXbPmnY"

# ---------------------------------------------------------------- Paths & Config

CONFIG_PATH = Path.home() / ".unified_suite_config.json"
HISTORY_PATH = Path.home() / ".unified_suite_history.json"
UNIFIED_PROFILE = Path.home() / ".unified_suite_chrome_profile"

BROWSER_SITES = ["Diigo", "Hatena", "Pastelink"]

TARGET_URLS = {
    "Diigo": "https://www.diigo.com/",
    "Hatena": "https://b.hatena.ne.jp/",
    "Pastelink": "https://pastelink.net/submit",
}

LOGIN_URLS = {
    "Diigo": "https://www.diigo.com/sign-in",
    "Hatena": "https://accounts.hatena.ne.jp/login",
    "Pastelink": "https://pastelink.net/",
}

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
]
IGNORE_ARGS = ["--enable-automation"]

INIT_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});
"""

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# ---------------------------------------------------------------- Helpers & History

def load_config():
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_config(cfg):
    try:
        CONFIG_PATH.write_text(json.dumps(cfg), encoding="utf-8")
    except Exception:
        pass

def load_history():
    try:
        h = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        h = {}
    for s in BROWSER_SITES + ["API_BLAST"]:
        h.setdefault(s, [])
    return h

def save_history(h):
    try:
        HISTORY_PATH.write_text(json.dumps(h), encoding="utf-8")
    except Exception:
        pass

def record_done(site, url):
    h = load_history()
    h.setdefault(site, [])
    if url not in h[site]:
        h[site].append(url)
        save_history(h)

def is_done(site, url):
    return url in load_history().get(site, [])

def clean_title(first_url):
    clean = re.sub(r"^https?://(www\.)?", "", first_url)
    clean = re.sub(r"[/?#].*$", "", clean)
    clean = clean.replace(".", " ").capitalize()
    return f"Resources - {clean}"[:55]

def launch_context_sync(p, profile_dir, headless=False):
    launch_kwargs = {
        "user_data_dir": str(profile_dir),
        "headless": headless,
        "viewport": {"width": 1280, "height": 960},
        "args": STEALTH_ARGS,
        "ignore_default_args": IGNORE_ARGS,
    }
    try:
        ctx = p.chromium.launch_persistent_context(channel="chrome", **launch_kwargs)
    except Exception:
        ctx = p.chromium.launch_persistent_context(**launch_kwargs)
    ctx.add_init_script(INIT_STEALTH_JS)
    return ctx

# ---------------------------------------------------------------- Multi-Search Crawler Pings

def ping_search_engines(title, page_url, log):
    old_timeout = socket.getdefaulttimeout()
    endpoints = [
        ("Ping-O-Matic", "http://rpc.pingomatic.com"),
        ("Weblogs.com", "http://rpc.weblogs.com/RPC2"),
        ("Blo.gs", "http://ping.blo.gs/")
    ]
    try:
        socket.setdefaulttimeout(6)
        for name, ep in endpoints:
            try:
                sp = xmlrpc.client.ServerProxy(ep)
                sp.weblogUpdates.ping(title, page_url)
                log(f"   📡 [{name}] Pinged crawler for: {page_url}")
            except Exception:
                pass
    finally:
        socket.setdefaulttimeout(old_timeout)

# ---------------------------------------------------------------- 10 Verified Active API Engines

def publish_centos(urls, title, log):
    try:
        content = f"# {title or 'Resource Directory'}\n\n" + "\n".join(urls)
        data = urllib.parse.urlencode({"text": content, "title": title or "Resource Directory"}).encode("utf-8")
        req = urllib.request.Request("https://paste.centos.org/api/create", data=data, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = resp.read().decode("utf-8").strip()
            if res.startswith("http"):
                log(f"✅ CentOS Official (DA 91) Published: {res}")
                return res
    except Exception as e:
        log(f"❌ CentOS notice: {e}")
    return None

def get_graph_org_token():
    cfg = load_config()
    if "graph_token" in cfg:
        return cfg["graph_token"]
    try:
        url = "https://api.graph.org/createAccount?short_name=ResourceBot&author_name=Curator"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
            token = data.get("result", {}).get("access_token")
            if token:
                cfg["graph_token"] = token
                save_config(cfg)
                return token
    except Exception:
        pass
    return None

def publish_graph_org(urls, title, log):
    try:
        token = get_graph_org_token()
        if not token:
            return None
        content_nodes = [{"tag": "p", "children": ["Curated reference index:"]}]
        for u in urls:
            content_nodes.append({"tag": "p", "children": [{"tag": "a", "attrs": {"href": u, "target": "_blank"}, "children": [u]}]})
        post_data = urllib.parse.urlencode({"access_token": token, "title": title or "Resource Directory", "content": json.dumps(content_nodes), "return_content": "false"}).encode("utf-8")
        req = urllib.request.Request("https://api.graph.org/createPage", data=post_data, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode())
            if res.get("ok"):
                url = res.get("result", {}).get("url")
                log(f"✅ Graph.org (DA 88) Published: {url}")
                return url
    except Exception as e:
        log(f"❌ Graph.org notice: {e}")
    return None

def publish_dpaste_org(urls, title, log):
    try:
        content = f"# {title or 'Resource Links'}\n\n" + "\n".join([f"- {u}" for u in urls])
        post_data = urllib.parse.urlencode({"content": content, "title": title or "Resource Links", "syntax": "markdown", "expiry_days": "365"}).encode("utf-8")
        req = urllib.request.Request("https://dpaste.org/api/", data=post_data, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            url = resp.read().decode("utf-8").strip().replace('"', '')
            if url.startswith("http"):
                log(f"✅ dpaste.org (DA 78) Published: {url}")
                return url
    except Exception as e:
        log(f"❌ dpaste.org notice: {e}")
    return None

def publish_rentry(urls, title, log):
    try:
        md_lines = [f"# {title or 'Resource Directory'}\n", "Useful links and reference materials:\n"]
        for u in urls:
            md_lines.append(f"- [{u}]({u})")
        post_data = urllib.parse.urlencode({"url": "", "edit_code": "", "text": "\n".join(md_lines)}).encode("utf-8")
        req = urllib.request.Request("https://rentry.co/api/new", data=post_data, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://rentry.co"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            if data.get("status") == "200":
                url = data.get("url")
                log(f"✅ Rentry.co (DA 75) Published: {url}")
                return url
    except Exception as e:
        log(f"❌ Rentry notice: {e}")
    return None

def publish_dpaste_com(urls, title, log):
    try:
        content = f"# {title or 'Resource Directory'}\n\n" + "\n".join([f"- {u}" for u in urls])
        data = urllib.parse.urlencode({"content": content, "title": title or "Resource Links", "syntax": "markdown", "expiry_days": "365"}).encode("utf-8")
        req = urllib.request.Request("https://dpaste.com/api/v2/", data=data, headers={"User-Agent": "curl/7.88.1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = resp.read().decode("utf-8").strip()
            if res.startswith("http"):
                log(f"✅ dpaste.com (DA 75) Published: {res}")
                return res
    except Exception as e:
        log(f"❌ dpaste.com notice: {e}")
    return None

def publish_paste_rs(urls, title, log):
    try:
        content = f"=== {title or 'Resource Directory'} ===\n\n" + "\n".join(urls) + "\n"
        req = urllib.request.Request("https://paste.rs", data=content.encode("utf-8"), headers={"User-Agent": "curl/7.88.1"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            url = resp.read().decode("utf-8").strip()
            if url.startswith("http"):
                log(f"✅ Paste.rs Published: {url}")
                return url
    except Exception as e:
        log(f"❌ Paste.rs notice: {e}")
    return None

def publish_termbin(urls, title, log):
    try:
        content = f"=== {title or 'Resource Links'} ===\n" + "\n".join(urls) + "\n"
        with socket.create_connection(("termbin.com", 9999), timeout=6) as s:
            s.sendall(content.encode("utf-8"))
            resp = s.recv(1024).decode("utf-8").strip()
            if resp.startswith("http"):
                log(f"✅ Termbin.com Published: {resp}")
                return resp
    except Exception as e:
        log(f"❌ Termbin notice: {e}")
    return None

def publish_ix_io(urls, title, log):
    try:
        content = f"=== {title or 'Resource Directory'} ===\n\n" + "\n".join(urls)
        data = urllib.parse.urlencode({"f:1": content}).encode("utf-8")
        req = urllib.request.Request("http://ix.io", data=data, headers={"User-Agent": "curl/7.88.1"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            res = resp.read().decode("utf-8").strip()
            if res.startswith("http"):
                log(f"✅ ix.io Published: {res}")
                return res
    except Exception as e:
        log(f"❌ ix.io notice: {e}")
    return None

def publish_cnet(urls, title, log):
    try:
        content = f"# {title or 'Resource Directory'}\n\n" + "\n".join(urls) + "\n"
        req = urllib.request.Request("https://paste.c-net.org/", data=content.encode("utf-8"), headers={"User-Agent": "curl/7.88.1"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            url = resp.read().decode("utf-8").strip()
            if url.startswith("http"):
                log(f"✅ paste.c-net.org Published: {url}")
                return url
    except Exception as e:
        log(f"❌ paste.c-net.org notice: {e}")
    return None

def publish_nullpaste(urls, title, log):
    try:
        content = (f"# {title or 'Resource Directory'}\n\n" + "\n".join(urls)).encode("utf-8")
        req = urllib.request.Request("https://nullpaste.org/api/v1/pastes", data=content, headers={"Content-Type": "text/plain", "User-Agent": "curl/7.88.1"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            url = data.get("url")
            if url:
                log(f"✅ NullPaste Published: {url}")
                return url
    except Exception as e:
        log(f"❌ NullPaste notice: {e}")
    return None

def run_api_blast(urls, log):
    title = clean_title(urls[0])
    log(f"🚀 Blasting {len(urls)} link(s) across 10 verified high-authority platforms...")
    start_time = time.time()
    created_pages = []

    targets = [
        lambda: publish_centos(urls, title, log),
        lambda: publish_graph_org(urls, title, log),
        lambda: publish_dpaste_org(urls, title, log),
        lambda: publish_rentry(urls, title, log),
        lambda: publish_dpaste_com(urls, title, log),
        lambda: publish_paste_rs(urls, title, log),
        lambda: publish_termbin(urls, title, log),
        lambda: publish_ix_io(urls, title, log),
        lambda: publish_cnet(urls, title, log),
        lambda: publish_nullpaste(urls, title, log),
    ]

    for fn in targets:
        try:
            res = fn()
            if res:
                created_pages.append(res)
        except Exception:
            pass

    if created_pages:
        log("🔔 Sending XML-RPC pings to search engine aggregators (Google/Bing/Yahoo feeds)...")
        for p in created_pages:
            ping_search_engines(title, p, log)

    elapsed = round(time.time() - start_time, 2)
    log(f"🎉 API Blast Finished: {len(created_pages)} platforms published & pinged in {elapsed}s!")
    for u in urls:
        record_done("API_BLAST", u)

# ---------------------------------------------------------------- Browser Workers

def dismiss_passkey_prompt(page, log=None):
    try:
        for text in ["Not now", "Later", "あとで", "今はしない"]:
            loc = page.get_by_text(re.compile(re.escape(text), re.I))
            if loc.count() > 0:
                loc.first.click()
                time.sleep(1)
                return
        if "passkey" in page.url or page.locator('text=passkey').count() > 0:
            page.go_back()
            time.sleep(1)
    except Exception:
        pass

def hatena_add_bookmark(page, url, log):
    dismiss_passkey_prompt(page, log)
    page.goto("https://b.hatena.ne.jp/", wait_until="domcontentloaded", timeout=60000)
    time.sleep(1.5)
    mypage = page.locator('a[data-gtm-label="gh-mypage"]')
    if mypage.count() == 0:
        log("  Hatena: my page link not found (not logged in?)")
        return False
    mypage.first.click()
    time.sleep(2)
    add = page.locator("a.btn-white")
    if add.count() == 0:
        log("  Hatena: add-bookmark button not found")
        return False
    add.first.click()
    time.sleep(2)
    urlfield = page.locator('input[name="url"], input[type="url"]').first
    urlfield.fill(url)
    urlfield.press("Enter")
    time.sleep(2.5)
    comment = page.locator('textarea[name="comment"], textarea').first
    if comment.count() > 0:
        comment.fill(url)
    submit = page.locator("input.bookmarkadd-submit-btn")
    if submit.count() == 0:
        log("  Hatena: submit button not found")
        return False
    submit.first.click()
    time.sleep(2.5)
    return True

def diigo_add_bookmark(page, url, log):
    page.goto(TARGET_URLS["Diigo"], wait_until="domcontentloaded", timeout=60000)
    time.sleep(2)
    add_btn = page.locator("div.addItemButton, button.addItemButton, a.addItemButton")
    if add_btn.count() == 0 or not add_btn.first.is_visible():
        log("  Diigo: '+' add button not visible.")
        return False
    add_btn.first.click()
    time.sleep(1)
    link_option = page.locator("div.add-type-item.link, a.add-type-item.link, div.add-type-item")
    if link_option.count() == 0:
        return False
    link_option.first.click()

    try:
        page.wait_for_selector("div.AddBookmark, .modal-dialog", timeout=12000, state="visible")
    except PWTimeout:
        log(f"  Diigo dialog did not open for {url}")
        return False

    modal = page.locator("div.AddBookmark, .modal-dialog").first
    time.sleep(0.5)
    url_input = modal.locator('input[type="text"], input').first
    url_input.fill(url)
    time.sleep(0.5)

    next_btn = modal.locator('button:has-text("Next"), div.btn:has-text("Next"), button.btn-primary, button').first
    next_btn.click()

    try:
        page.wait_for_selector("div.AddBookmark textarea, div.AddBookmark input[placeholder*='Title' i], .AddBookmark textarea", timeout=15000, state="visible")
        time.sleep(1)
    except PWTimeout:
        log("  Diigo: Metadata loading timed out.")
        return False

    clicked = False
    for label in ["Add", "Save", "Bookmark", "Add Bookmark"]:
        btn = modal.locator(f'button:has-text("{label}"), a:has-text("{label}"), div[role="button"]:has-text("{label}")')
        if btn.count() > 0:
            for idx in range(btn.count()):
                candidate = btn.nth(idx)
                txt = (candidate.inner_text() or "").strip().lower()
                if "next" not in txt and candidate.is_visible():
                    candidate.scroll_into_view_if_needed()
                    candidate.click()
                    clicked = True
                    break
        if clicked:
            break

    if not clicked:
        primary_btn = modal.locator("button.btn-primary, .modal-footer button, button[type='submit']")
        if primary_btn.count() > 0:
            for idx in range(primary_btn.count()):
                candidate = primary_btn.nth(idx)
                txt = (candidate.inner_text() or "").strip().lower()
                if "cancel" not in txt and "next" not in txt and candidate.is_visible():
                    candidate.scroll_into_view_if_needed()
                    candidate.click()
                    clicked = True
                    break

    try:
        modal.wait_for(state="hidden", timeout=12000)
        time.sleep(1.5)
        return True
    except PWTimeout:
        return False

def pastelink_bulk(page, urls, log):
    log(f"  Pastelink: Submitting {len(urls)} links...")
    page.goto(TARGET_URLS["Pastelink"], wait_until="domcontentloaded", timeout=60000)
    time.sleep(2)

    title_input = page.locator('input[placeholder*="title" i], input[type="text"]').first
    if title_input.count() > 0:
        title_input.fill(clean_title(urls[0]))

    body = page.locator("textarea").first
    body.fill("\n".join(urls))
    time.sleep(1)

    def click_publish():
        for sel in ['button:has-text("Publish")', '#submitbtn', 'input[value*="Publish" i]', 'button[type="submit"]', 'input[type="submit"]']:
            loc = page.locator(sel)
            if loc.count() > 0 and loc.first.is_visible():
                loc.first.scroll_into_view_if_needed()
                loc.first.click()
                return True
        return False

    time.sleep(2)
    click_publish()
    time.sleep(2)

    for _ in range(15):
        if "/submit" not in page.url and re.search(r"pastelink\.net/[A-Za-z0-9]+$", page.url):
            log(f"  Pastelink published: {page.url}")
            return True
        success = page.locator('text="Success!"')
        if success.count() > 0 and success.first.is_visible():
            log("  Pastelink: Turnstile verified (Success!). Clicking Publish...")
            click_publish()
            time.sleep(2.5)
            if "/submit" not in page.url and re.search(r"pastelink\.net/[A-Za-z0-9]+$", page.url):
                log(f"  Pastelink published: {page.url}")
                return True
        time.sleep(1)

    try:
        page.wait_for_url(lambda u: "/submit" not in u and re.search(r"pastelink\.net/[A-Za-z0-9]+$", u), timeout=10000)
        log(f"  Pastelink published: {page.url}")
        return True
    except PWTimeout:
        log("  Pastelink: Submission stayed on /submit.")
        return False

# ---------------------------------------------------------------- Google Sheet Watcher

class GoogleSheetWatcher:
    def __init__(self, sheet_url, callback=None, log_callback=None, poll_interval=8):
        self.raw_input = sheet_url.strip()
        self.callback = callback
        self.log = log_callback or print
        self.poll_interval = poll_interval
        self.running = False
        self._thread = None
        self.seen_urls = set()
        self.sheet_id = self._extract_sheet_id(self.raw_input)
        self.gid = self._extract_gid(self.raw_input)

    def _extract_sheet_id(self, text):
        m = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", text)
        return m.group(1) if m else text

    def _extract_gid(self, text):
        m = re.search(r"[?&#]gid=(\d+)", text)
        return m.group(1) if m else None

    def _fetch_values(self):
        gid_param = f"&gid={self.gid}" if self.gid else ""
        export_url = f"https://docs.google.com/spreadsheets/d/{self.sheet_id}/export?format=csv{gid_param}"
        req = urllib.request.Request(export_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=12) as response:
            content = response.read().decode("utf-8-sig")
            reader = csv.reader(io.StringIO(content))
            return list(reader)

    def parse_topmost_day(self, all_values):
        if not all_values:
            return []
        date_pattern = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
        found = False
        extracted = []
        for row in all_values:
            if not row:
                continue
            col_a = str(row[0]).strip().lstrip("\ufeff")
            if date_pattern.search(col_a):
                if not found:
                    found = True
                    continue
                else:
                    break
            if found and len(row) > 2:
                for cell in row[2:]:
                    v = str(cell).strip()
                    if v.startswith("http://") or v.startswith("https://"):
                        extracted.append(v)
        return extracted

    def loop(self):
        self.log("Sheet Watcher: Connected & polling every 8s...")
        while self.running:
            try:
                values = self._fetch_values()
                urls = self.parse_topmost_day(values)
                new_urls = [u for u in urls if u not in self.seen_urls]
                if new_urls:
                    self.log(f"Sheet Watcher: Detected {len(new_urls)} NEW links!")
                    for u in new_urls:
                        self.seen_urls.add(u)
                    if self.callback:
                        self.callback(new_urls)
            except Exception:
                pass
            time.sleep(self.poll_interval)

    def start(self):
        self.running = True
        self._thread = threading.Thread(target=self.loop, daemon=True)
        self._thread.start()

    def stop(self):
        self.running = False

# ---------------------------------------------------------------- Modern UI Master Application (CustomTkinter)

class App:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("Unified SEO Backlink & Indexing Suite")
        self.root.geometry("1020x860")
        self.root.minsize(860, 720)

        # Header Title Banner
        h_frame = ctk.CTkFrame(self.root, corner_radius=12, fg_color="#1f2335")
        h_frame.pack(fill="x", padx=16, pady=(12, 6))
        ctk.CTkLabel(h_frame, text="⚡ Unified SEO Backlink & Indexing Suite",
                     font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                     text_color="#7aa2f7").pack(anchor="w", padx=16, pady=(10, 2))
        ctk.CTkLabel(h_frame, text="Dual Engine: 10 Verified APIs (2s Blast) + Single Chrome Automation (Diigo, Hatena, Pastelink)",
                     font=ctk.CTkFont(family="Segoe UI", size=12),
                     text_color="#9aa5ce").pack(anchor="w", padx=16, pady=(0, 10))

        # Top Bar: Sheet Watcher Card
        s_bar = ctk.CTkFrame(self.root, corner_radius=12, fg_color="#1e1e2e")
        s_bar.pack(fill="x", padx=16, pady=(0, 8))

        s_inner = ctk.CTkFrame(s_bar, fg_color="transparent")
        s_inner.pack(fill="x", padx=14, pady=10)

        ctk.CTkLabel(s_inner, text="Google Sheet URL:", width=130, anchor="w",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.sheet_url_var = tk.StringVar()
        self.sheet_entry = ctk.CTkEntry(s_inner, textvariable=self.sheet_url_var, height=34, corner_radius=6)
        self.sheet_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        self.watch_btn = ctk.CTkButton(s_inner, text="▶ Start Watcher (8s)", width=160, height=34, corner_radius=6,
                                       font=ctk.CTkFont(size=12, weight="bold"), fg_color="#10b981",
                                       hover_color="#059669", cursor="hand2", command=self.toggle_watcher)
        self.watch_btn.pack(side="left", padx=(0, 6))

        self.reset_btn = ctk.CTkButton(s_inner, text="Reset History", width=110, height=34, corner_radius=6,
                                       font=ctk.CTkFont(size=12), fg_color="#24283b", hover_color="#2f354f",
                                       cursor="hand2", command=self.reset_history)
        self.reset_btn.pack(side="left")

        # Master Action Buttons Bar
        a_bar = ctk.CTkFrame(self.root, fg_color="transparent")
        a_bar.pack(fill="x", padx=16, pady=(0, 8))

        # Row 1: Fast API Blast & Full Combo
        r1 = ctk.CTkFrame(a_bar, fg_color="transparent")
        r1.pack(fill="x", pady=(0, 6))
        self.api_blast_btn = ctk.CTkButton(
            r1, text="⚡ Run Instant API Blast (10 Sites in 2s - Zero Browser)",
            height=40, corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#3b82f6", hover_color="#2563eb", cursor="hand2", command=self.trigger_api_blast
        )
        self.api_blast_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.combo_btn = ctk.CTkButton(
            r1, text="🚀 FULL COMBO (Blast 10 APIs + Run Browser Bookmarks)",
            height=40, corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#8b5cf6", hover_color="#7c3aed", cursor="hand2", command=self.trigger_full_combo
        )
        self.combo_btn.pack(side="left", fill="x", expand=True)

        # Row 2: Browser Actions
        r2 = ctk.CTkFrame(a_bar, fg_color="transparent")
        r2.pack(fill="x")
        self.browser_run_btn = ctk.CTkButton(
            r2, text="🌐 Run Browser Bookmarks (Diigo + Hatena + Pastelink)",
            height=38, corner_radius=8, font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#10b981", hover_color="#059669", cursor="hand2", command=self.trigger_browser_run
        )
        self.browser_run_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.login_btn = ctk.CTkButton(
            r2, text="🔑 Open Chrome to Login (3 Tabs in ONE Window)",
            height=38, corner_radius=8, font=ctk.CTkFont(size=12),
            fg_color="#24283b", hover_color="#2f354f", cursor="hand2", command=self.open_login_browser
        )
        self.login_btn.pack(side="left", padx=0)

        # Tabs Container (CustomTkinter CTkTabview)
        self.tabview = ctk.CTkTabview(self.root, corner_radius=12, fg_color="#1e1e2e")
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(0, 12))

        # Tab 1: Instant API Engine
        self.tab_api = self.tabview.add("⚡ Instant API Engine (10 Sites)")
        self.build_api_tab(self.tab_api)

        # Tabs 2, 3, 4: Browser Sites
        self.browser_tabs = {}
        for site in BROWSER_SITES:
            tab_frame = self.tabview.add(f"{site} (Browser)")
            self.browser_tabs[site] = self.build_browser_tab(tab_frame, site)

        self.watcher = None
        self.load_settings()

    def build_api_tab(self, parent):
        ctk.CTkLabel(parent, text="Instant Multi-Site API Engine (Runs 100% in Background)",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="#7aa2f7").pack(anchor="w", padx=4, pady=(6, 2))
        ctk.CTkLabel(parent, text="Publishes to CentOS (DA 91), Graph.org (DA 88), dpaste.org (DA 78), Rentry (DA 75), dpaste.com (DA 75), Paste.rs, Termbin, ix.io, c-net, NullPaste + Search Engine Crawler Pings",
                     font=ctk.CTkFont(size=11), text_color="#9aa5ce").pack(anchor="w", padx=4, pady=(0, 8))

        ctk.CTkLabel(parent, text="Target URLs (queued from Google Sheet or paste here):",
                     font=ctk.CTkFont(size=12)).pack(anchor="w", padx=4, pady=(0, 2))
        self.api_urls_box = ctk.CTkTextbox(parent, height=90, corner_radius=8, font=ctk.CTkFont(family="Consolas", size=11))
        self.api_urls_box.pack(fill="x", padx=4, pady=(0, 8))

        ctk.CTkLabel(parent, text="Live Output & Crawl Status:",
                     font=ctk.CTkFont(size=12, weight="bold"), text_color="#9aa5ce").pack(anchor="w", padx=4, pady=(0, 2))
        self.api_log_box = ctk.CTkTextbox(parent, height=220, corner_radius=8, font=ctk.CTkFont(family="Consolas", size=11),
                                          activate_scrollbars=True)
        self.api_log_box.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.api_log_box.configure(state="disabled")

        raw_txt = self.api_log_box._textbox
        raw_txt.tag_configure("ok", foreground="#10b981")
        raw_txt.tag_configure("err", foreground="#f87171")
        raw_txt.tag_configure("warn", foreground="#fbbf24")
        raw_txt.tag_configure("head", foreground="#60a5fa")

    def build_browser_tab(self, parent, site):
        ctk.CTkLabel(parent, text=f"{site} Automation Dashboard",
                     font=ctk.CTkFont(size=13, weight="bold"), text_color="#7aa2f7").pack(anchor="w", padx=4, pady=(6, 2))
        mode = "Submits links individually (1 by 1)." if site in ["Diigo", "Hatena"] else "Submits all links in BULK (1 post)."
        ctk.CTkLabel(parent, text=f"Mode: {mode}", font=ctk.CTkFont(size=11), text_color="#9aa5ce").pack(anchor="w", padx=4, pady=(0, 8))

        ctk.CTkLabel(parent, text="Target URLs:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=4, pady=(0, 2))
        u_box = ctk.CTkTextbox(parent, height=80, corner_radius=8, font=ctk.CTkFont(family="Consolas", size=11))
        u_box.pack(fill="x", padx=4, pady=(0, 8))

        c_bar = ctk.CTkFrame(parent, fg_color="transparent")
        c_bar.pack(fill="x", padx=4, pady=(0, 8))

        btn = ctk.CTkButton(c_bar, text=f"Run {site} Only", width=140, height=32, corner_radius=6,
                            font=ctk.CTkFont(size=12, weight="bold"), fg_color="#3b82f6", hover_color="#2563eb",
                            cursor="hand2", command=lambda s=site: self.run_single_browser_site(s))
        btn.pack(side="left")

        pbar = ctk.CTkProgressBar(c_bar, height=12, corner_radius=6)
        pbar.pack(side="left", fill="x", expand=True, padx=(12, 10))
        pbar.set(0)

        lbl = ctk.CTkLabel(c_bar, text="idle", font=ctk.CTkFont(size=12), text_color="#9aa5ce")
        lbl.pack(side="left")

        log = ctk.CTkTextbox(parent, height=200, corner_radius=8, font=ctk.CTkFont(family="Consolas", size=11),
                            activate_scrollbars=True)
        log.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        log.configure(state="disabled")

        return {"urls": u_box, "btn": btn, "pbar": pbar, "lbl": lbl, "log": log}

    def api_log(self, msg):
        def _w():
            self.api_log_box.configure(state="normal")
            tag = "info"
            if "✅" in msg or "🎉" in msg:
                tag = "ok"
            elif "❌" in msg:
                tag = "err"
            elif "🚀" in msg or "🔔" in msg or "📡" in msg:
                tag = "head"

            self.api_log_box._textbox.insert("end", msg + "\n", tag)
            self.api_log_box._textbox.see("end")
            self.api_log_box.configure(state="disabled")
        self.root.after(0, _w)

    def browser_log(self, site, msg):
        def _w():
            box = self.browser_tabs[site]["log"]
            box.configure(state="normal")
            box._textbox.insert("end", msg + "\n")
            box._textbox.see("end")
            box.configure(state="disabled")
        self.root.after(0, _w)

    def get_all_active_urls(self):
        urls = [u.strip() for u in self.api_urls_box.get("1.0", "end").splitlines() if u.strip()]
        if not urls:
            for t in self.browser_tabs.values():
                urls = [u.strip() for u in t["urls"].get("1.0", "end").splitlines() if u.strip()]
                if urls:
                    break
        return list(dict.fromkeys(urls))

    def reset_history(self):
        if messagebox.askyesno("Reset", "Clear finished history so links can be re-run?"):
            save_history({})
            if self.watcher:
                self.watcher.seen_urls.clear()
            self.api_log("History cleared.")
            messagebox.showinfo("Reset", "History cleared.")

    def toggle_watcher(self):
        if self.watcher and self.watcher.running:
            self.watcher.stop()
            self.watcher = None
            self.watch_btn.configure(text="▶ Start Watcher (8s)", fg_color="#10b981", hover_color="#059669")
        else:
            url = self.sheet_url_var.get().strip()
            if not url:
                messagebox.showwarning("Missing", "Enter Google Sheet URL first.")
                return
            self.watcher = GoogleSheetWatcher(url, callback=self.on_new_sheet_urls, log_callback=self.api_log)
            self.watcher.start()
            self.watch_btn.configure(text="⏹ Stop Watcher", fg_color="#ef4444", hover_color="#dc2626")
            self.save_settings()

    def on_new_sheet_urls(self, urls):
        def _u():
            existing = [x.strip() for x in self.api_urls_box.get("1.0", "end").splitlines() if x.strip()]
            combined = list(dict.fromkeys(existing + urls))
            self.api_urls_box.delete("1.0", "end")
            self.api_urls_box.insert("1.0", "\n".join(combined))

            for site, tab in self.browser_tabs.items():
                tab["urls"].delete("1.0", "end")
                tab["urls"].insert("1.0", "\n".join(combined))
        self.root.after(0, _u)

    def open_login_browser(self):
        def work():
            with sync_playwright() as p:
                ctx = launch_context_sync(p, UNIFIED_PROFILE, headless=False)
                for i, (name, target) in enumerate(LOGIN_URLS.items()):
                    page = ctx.pages[0] if (i == 0 and ctx.pages) else ctx.new_page()
                    page.goto(target, wait_until="domcontentloaded")
                try:
                    ctx.pages[0].wait_for_event("close", timeout=0)
                except Exception:
                    pass
        threading.Thread(target=work, daemon=True).start()

    def trigger_api_blast(self):
        urls = self.get_all_active_urls()
        if not urls:
            messagebox.showwarning("Empty", "No URLs to publish.")
            return

        self.api_blast_btn.configure(state="disabled", text="Blasting 10 APIs...")
        def work():
            try:
                run_api_blast(urls, self.api_log)
            finally:
                self.root.after(0, lambda: self.api_blast_btn.configure(
                    state="normal", text="⚡ Run Instant API Blast (10 Sites in 2s - Zero Browser)"
                ))
        threading.Thread(target=work, daemon=True).start()

    def trigger_browser_run(self):
        urls = self.get_all_active_urls()
        if not urls:
            messagebox.showwarning("Empty", "No URLs to process.")
            return

        self.browser_run_btn.configure(state="disabled", text="Running Browser Bookmarks...")
        def work():
            with sync_playwright() as p:
                ctx = launch_context_sync(p, UNIFIED_PROFILE, headless=False)
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                try:
                    for site in BROWSER_SITES:
                        self.execute_browser_site(page, site, urls)
                finally:
                    ctx.close()
                    self.root.after(0, lambda: self.browser_run_btn.configure(
                        state="normal", text="🌐 Run Browser Bookmarks (Diigo + Hatena + Pastelink)"
                    ))
        threading.Thread(target=work, daemon=True).start()

    def trigger_full_combo(self):
        urls = self.get_all_active_urls()
        if not urls:
            messagebox.showwarning("Empty", "No URLs to process.")
            return

        def work():
            run_api_blast(urls, self.api_log)
            time.sleep(1)

            with sync_playwright() as p:
                ctx = launch_context_sync(p, UNIFIED_PROFILE, headless=False)
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                try:
                    for site in BROWSER_SITES:
                        self.execute_browser_site(page, site, urls)
                finally:
                    ctx.close()
        threading.Thread(target=work, daemon=True).start()

    def run_single_browser_site(self, site):
        urls = [u.strip() for u in self.browser_tabs[site]["urls"].get("1.0", "end").splitlines() if u.strip()]
        if not urls:
            messagebox.showwarning("Empty", f"No URLs to process in {site} tab.")
            return

        def work():
            with sync_playwright() as p:
                ctx = launch_context_sync(p, UNIFIED_PROFILE, headless=False)
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                try:
                    self.execute_browser_site(page, site, urls)
                finally:
                    ctx.close()
        threading.Thread(target=work, daemon=True).start()

    def execute_browser_site(self, page, site, urls):
        todo = [u for u in urls if not is_done(site, u)]
        tab = self.browser_tabs[site]
        self.browser_log(site, f"--- Starting {site} ({len(todo)} pending of {len(urls)}) ---")
        tab["pbar"].set(0)

        if not todo:
            self.browser_log(site, "All links already completed.")
            return

        total_cnt = len(todo)
        if site == "Diigo":
            for idx, u in enumerate(todo):
                self.browser_log(site, f"[{idx+1}/{total_cnt}] Submitting: {u}")
                if diigo_add_bookmark(page, u, lambda m: self.browser_log(site, m)):
                    record_done(site, u)
                    self.browser_log(site, "  ✅ Diigo: ok")
                tab["pbar"].set((idx + 1) / total_cnt)
                tab["lbl"].configure(text=f"{idx+1}/{total_cnt}")

        elif site == "Hatena":
            for idx, u in enumerate(todo):
                self.browser_log(site, f"[{idx+1}/{total_cnt}] Submitting: {u}")
                if hatena_add_bookmark(page, u, lambda m: self.browser_log(site, m)):
                    record_done(site, u)
                    self.browser_log(site, "  ✅ Hatena: ok")
                tab["pbar"].set((idx + 1) / total_cnt)
                tab["lbl"].configure(text=f"{idx+1}/{total_cnt}")

        elif site == "Pastelink":
            if pastelink_bulk(page, todo, lambda m: self.browser_log(site, m)):
                for u in todo:
                    record_done(site, u)
            tab["pbar"].set(1.0)

        self.browser_log(site, f"🎉 {site} Finished.")

    def load_settings(self):
        cfg = load_config()
        self.sheet_url_var.set(cfg.get("sheet_url", ""))

    def save_settings(self):
        cfg = {"sheet_url": self.sheet_url_var.get().strip()}
        save_config(cfg)

    def run(self):
        self.root.mainloop()


# ==============================================================================
# MODERN CLOUD LOGIN GATE WINDOW (CustomTkinter)
# ==============================================================================
class CloudLoginWindow:
    def __init__(self, on_success):
        self.on_success = on_success
        self.root = ctk.CTk()
        self.root.title("Unified Suite - Access Verification")
        self.root.geometry("420x420")
        self.root.resizable(False, False)

        try:
            self.root.eval('tk::PlaceWindow . center')
        except Exception:
            pass

        card = ctk.CTkFrame(self.root, corner_radius=16, fg_color="#1e1e2e")
        card.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(card, text="🔒 Authorization Required", font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
                     text_color="#7aa2f7").pack(pady=(24, 4))
        ctk.CTkLabel(card, text="Enter your access credentials to unlock the suite.",
                     font=ctk.CTkFont(family="Segoe UI", size=12), text_color="#9a9ab0").pack(pady=(0, 20))

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

                reader = csv.reader(io.StringIO(csv_text))
                rows = [r for r in reader if any(r)]

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
                    self.root.after(0, self._on_success_login)
                elif status_msg:
                    self._show_err(status_msg)
                else:
                    self._show_err("Invalid username or password.")

            except urllib.error.URLError:
                self._show_err("Network error: Cannot reach authentication server.")
            except Exception as e:
                self._show_err(f"Verification error: {e}")

        threading.Thread(target=check_worker, daemon=True).start()

    def _show_err(self, msg):
        def _w():
            self.status_lbl.configure(text=msg, text_color="#f7768e")
            self.verify_btn.configure(state="normal", text="Verify & Unlock")
        self.root.after(0, _w)

    def _on_success_login(self):
        self.root.destroy()
        self.on_success()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    def launch():
        App().run()

    CloudLoginWindow(on_success=launch).run()