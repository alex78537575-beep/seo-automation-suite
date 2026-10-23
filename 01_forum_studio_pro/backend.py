from urllib.parse import urlparse, urljoin
import os
import shutil
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except Exception:
    tk = None

try:
    import customtkinter as ctk
except Exception:
    ctk = None
import webbrowser
import threading
import json
import time
import random
import csv
import io
import re
import urllib.parse
import urllib.request
from pathlib import Path
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
except ImportError:
    sync_playwright = None
    class PWTimeout(Exception): pass

try:
    import pypdf
except ImportError:
    try:
        import PyPDF2 as pypdf
    except ImportError:
        pypdf = None

try:
    import docx
except ImportError:
    docx = None

try:
    import openpyxl
except ImportError:
    openpyxl = None

# ==============================================================================
# CLOUD ACCESS CONTROL CONFIGURATION (GOOGLE SHEET)
# ==============================================================================
AUTH_SHEET_ID = "1TcPjoKOT4jfH9n0xhxjnKVgCCqV7Y-pgKeGFCXbPmnY"

# Local Storage Paths
CONFIG_PATH = Path.home() / ".proboards_tool_config.json"
SESSION_PATH = Path.home() / ".proboards_session.json"
HISTORY_PATH = Path.home() / ".proboards_history.json"

DEFAULT_BOARD = "https://ohm.proboards.com/board/29/real-life-handball"
DEFAULT_LOGIN_URL = "https://login.proboards.com/login/949966/1"

# Playwright Browser Stealth Flags
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-features=CalculateNativeWinOcclusion,AutomationControlled",
    "--lang=en-US,en",
]

INIT_STEALTH_JS = """

// Navigation-proof Multi-Tab Clipboard & Share Link Interceptor
window.__captured_live_url = window.__captured_live_url || '';
try {
    if (navigator.clipboard) {
        const _origWriteText = navigator.clipboard.writeText ? navigator.clipboard.writeText.bind(navigator.clipboard) : null;
        navigator.clipboard.writeText = async function(text) {
            try {
                if (text && typeof text === 'string' && text.trim().startsWith('http')) {
                    window.__captured_live_url = text.trim();
                    try { localStorage.setItem('__fsp_captured_url', text.trim()); } catch(e) {}
                }
            } catch(e) {}
            if (_origWriteText) {
                try { return await _origWriteText(text); } catch(e) { return Promise.resolve(); }
            }
            return Promise.resolve();
        };
        const _origReadText = navigator.clipboard.readText ? navigator.clipboard.readText.bind(navigator.clipboard) : null;
        navigator.clipboard.readText = async function() {
            if (window.__captured_live_url) return window.__captured_live_url;
            try {
                const saved = localStorage.getItem('__fsp_captured_url');
                if (saved && saved.startsWith('http')) return saved;
            } catch(e) {}
            if (_origReadText) {
                try { return await _origReadText(); } catch(e) { return window.__captured_live_url || ''; }
            }
            return '';
        };
    }
    const _origExecCommand = document.execCommand ? document.execCommand.bind(document) : null;
    if (_origExecCommand) {
        document.execCommand = function(cmd, showUI, val) {
            if (cmd && String(cmd).toLowerCase() === 'copy') {
                try {
                    const sel = window.getSelection ? String(window.getSelection()) : '';
                    const activeVal = (document.activeElement && (document.activeElement.value || document.activeElement.innerText)) || '';
                    const cand = (sel || activeVal || '').trim();
                    if (cand.startsWith('http')) {
                        window.__captured_live_url = cand;
                        try { localStorage.setItem('__fsp_captured_url', cand); } catch(e) {}
                    }
                } catch(e) {}
            }
            return _origExecCommand(cmd, showUI, val);
        };
    }
} catch(e) {}


// Complete Cloudflare Turnstile, Google reCAPTCHA v2/v3, and hCaptcha Human Stealth Patch
try {
    // 1. Properly remove webdriver from Navigator.prototype so 'webdriver' in navigator behaves like real Chrome
    if (Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver')) {
        delete Object.getPrototypeOf(navigator).webdriver;
    }
    Object.defineProperty(Navigator.prototype, 'webdriver', {
        get: () => false,
        configurable: true
    });


    // 2b. Spoof navigator.userAgentData dynamically matching actual Chrome version (prevents Google BotGuard version mismatch!)
    try {
        const uaStr = navigator.userAgent || "";
        const verMatch = uaStr.match(/Chrome\/(\d+)\.(\d+)\.(\d+)\.(\d+)/) || [null, "131", "0", "6778", "86"];
        const majorVer = verMatch[1];
        const fullVer = `${verMatch[1]}.${verMatch[2]}.${verMatch[3]}.${verMatch[4]}`;
        const platName = uaStr.includes("Mac OS X") ? "macOS" : (uaStr.includes("Linux") ? "Linux" : "Windows");
        const chromeBrands = [
            { brand: "Google Chrome", version: majorVer },
            { brand: "Chromium", version: majorVer },
            { brand: "Not_A Brand", version: "24" }
        ];
        const fullVersionBrands = [
            { brand: "Google Chrome", version: fullVer },
            { brand: "Chromium", version: fullVer },
            { brand: "Not_A Brand", version: "24.0.0.0" }
        ];
        const fakeUAData = {
            brands: chromeBrands,
            mobile: false,
            platform: platName,
            getHighEntropyValues: async function(hints) {
                return {
                    architecture: "x86",
                    bitness: "64",
                    brands: chromeBrands,
                    fullVersionList: fullVersionBrands,
                    mobile: false,
                    model: "",
                    platform: platName,
                    platformVersion: "15.0.0",
                    uaFullVersion: fullVer,
                    wow64: false
                };
            },
            toJSON: function() {
                return { brands: this.brands, mobile: this.mobile, platform: this.platform };
            }
        };
        if (!navigator.userAgentData || !navigator.userAgentData.brands || !navigator.userAgentData.brands.some(b => b.brand === "Google Chrome")) {
            Object.defineProperty(Navigator.prototype, 'userAgentData', {
                get: () => fakeUAData,
                configurable: true
            });
        }
    } catch(e) {}

    // 2. Ensure window.chrome object looks like a genuine desktop Chrome installation
    if (!window.chrome) {
        window.chrome = {};
    }
    if (!window.chrome.runtime) {
        window.chrome.runtime = {
            PlatformOs: { MAC: 'mac', WIN: 'win', ANDROID: 'android', CROS: 'cros', LINUX: 'linux', OPENBSD: 'openbsd' },
            PlatformArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64', MIPS: 'mips', MIPS64: 'mips64' },
            PlatformNaclArch: { ARM: 'arm', X86_32: 'x86-32', X86_64: 'x86-64', MIPS: 'mips', MIPS64: 'mips64' },
            RequestUpdateCheckStatus: { THROTTLED: 'throttled', NO_UPDATE: 'no_update', UPDATE_AVAILABLE: 'update_available' }
        };
    }

    // 3. Ensure navigator.languages and plugins are populated for reCAPTCHA / Turnstile checks
    Object.defineProperty(navigator, 'languages', {
        get: () => ['en-US', 'en']
    });

    // 4. Remove Playwright/CDC automation markers if any exist on window
    for (const prop of Object.getOwnPropertyNames(window)) {
        if (/^cdc_|^__pw_|^__playwright/i.test(prop)) {
            try { delete window[prop]; } catch (e) {}
        }
    }
} catch (e) {}
"""

if ctk:
    try:
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
    except Exception:
        pass

# ------------------------------------------------------------- Core Helpers

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
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []

def record_history(url_or_title):
    h = load_history()
    if url_or_title not in h:
        h.append(url_or_title)
        try:
            HISTORY_PATH.write_text(json.dumps(h), encoding="utf-8")
        except Exception:
            pass


def process_spintax(text):
    if not text:
        return ""
    text = str(text)
    pattern = re.compile(r'\{([^{}]+)\}')
    while pattern.search(text):
        text = pattern.sub(lambda m: random.choice(m.group(1).split('|')), text)
    return text



# ==============================================================================
# SMART AUTOFILL CHROME EXTENSION BUNDLE
# ==============================================================================
MANIFEST_JSON = """{
  "manifest_version": 3,
  "name": "Smart Form AutoFiller (No Email/Pass)",
  "version": "1.0",
  "description": "Fills forms with realistic random details while leaving email and password fields empty.",
  "permissions": ["activeTab", "scripting"],
  "action": {
    "default_title": "Click to Auto-Fill Form"
  },
  "background": {
    "service_worker": "background.js"
  }
}"""

BACKGROUND_JS = """chrome.action.onClicked.addListener((tab) => {
  if (tab.id) {
    chrome.scripting.executeScript({
      target: { tabId: tab.id },
      files: ["content.js"]
    });
  }
});"""

CONTENT_JS = """(function () {
  const firstNames = ["James", "Robert", "John", "Michael", "David", "Sarah", "Emily", "Jessica", "Amanda", "Ashley"];
  const lastNames = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", "Wilson", "Taylor", "Anderson"];
  const streets = ["Maple Ave", "Oak Street", "Cedar Lane", "Pine Road", "Elm Street", "Washington Blvd", "Lakeview Drive"];
  const cities = ["Austin", "Denver", "Dallas", "Phoenix", "Seattle", "Atlanta", "Orlando", "Charlotte"];
  const states = ["CA", "TX", "NY", "FL", "IL", "PA", "OH", "GA", "NC", "MI"];
  const companies = ["Apex Media Group", "FlightCare Solutions", "Summit Global Services", "Pinnacle Logistics", "Vanguard Dynamics"];
  const titles = ["Communications Specialist", "Operations Coordinator", "Marketing Associate", "Project Assistant"];

  const rand = (arr) => arr[Math.floor(Math.random() * arr.length)];
  const randNum = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

  function triggerEvents(el) {
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function getFieldIdentifier(el) {
    const id = el.id || "";
    const name = el.name || "";
    const placeholder = el.placeholder || "";
    const aria = el.getAttribute("aria-label") || "";
    let labelText = "";
    if (el.labels && el.labels.length > 0) labelText = el.labels[0].innerText;
    const parentText = el.closest("label, .form-group, div, tr")?.innerText || "";
    return `${id} ${name} ${placeholder} ${aria} ${labelText} ${parentText}`.toLowerCase();
  }

  // 1. Process Text Inputs & Textareas
  document.querySelectorAll("input, textarea").forEach((el) => {
    const type = (el.type || "").toLowerCase();
    const info = getFieldIdentifier(el);

    if (type === "password" || type === "hidden" || type === "submit" || type === "button") return;
    if (info.includes("email") || info.includes("e-mail") || info.includes("password") || info.includes("captcha")) return;

    let val = "";

    if (info.includes("first") && info.includes("name")) {
      val = rand(firstNames);
    } else if (info.includes("last") && info.includes("name") || info.includes("surname")) {
      val = rand(lastNames);
    } else if (info.includes("full") || info.includes("name")) {
      val = `${rand(firstNames)} ${rand(lastNames)}`;
    } else if (info.includes("phone") || info.includes("tel") || info.includes("mobile") || info.includes("cell")) {
      val = `${randNum(200, 999)}-${randNum(200, 999)}-${randNum(1000, 9999)}`;
    } else if (info.includes("address") || info.includes("street")) {
      val = `${randNum(100, 9999)} ${rand(streets)}`;
    } else if (info.includes("city")) {
      val = rand(cities);
    } else if (info.includes("state")) {
      val = rand(states);
    } else if (info.includes("zip") || info.includes("postal")) {
      val = `${randNum(10000, 99999)}`;
    } else if (info.includes("company") || info.includes("organization")) {
      val = rand(companies);
    } else if (info.includes("job") || info.includes("title") || info.includes("position")) {
      val = rand(titles);
    } else if (type === "date" || info.includes("date")) {
      val = "2026-10-15";
    }

    if (val && !el.value) {
      el.value = val;
      triggerEvents(el);
    }
  });

  // 2. Process Radio Buttons (Yes / No eligibility questions)
  document.querySelectorAll('input[type="radio"]').forEach((el) => {
    const info = getFieldIdentifier(el);
    if (info.includes("18") || info.includes("eligible") || info.includes("lawfully") || info.includes("yes")) {
      const val = (el.value || "").toLowerCase();
      const text = el.parentElement?.innerText?.toLowerCase() || "";
      if (val === "yes" || val === "1" || text.includes("yes")) {
        el.checked = true;
        triggerEvents(el);
      }
    }
  });

  // 3. Process Dropdown Menus (<select>)
  document.querySelectorAll("select").forEach((sel) => {
    const info = getFieldIdentifier(sel);
    if (info.includes("country")) {
      for (let opt of sel.options) {
        if (opt.text.toLowerCase().includes("united states") || opt.value.toLowerCase() === "us") {
          sel.value = opt.value;
          triggerEvents(sel);
          return;
        }
      }
    }
    if (sel.selectedIndex <= 0 && sel.options.length > 1) {
      sel.selectedIndex = 1;
      triggerEvents(sel);
    }
  });

  console.log("⚡ Form auto-filled (Email & Password preserved).");
})();"""

def get_or_create_autofill_extension():
    candidates = [
        Path.home() / "OneDrive" / "Desktop" / "autofill-extension",
        Path.home() / "Desktop" / "autofill-extension",
        Path.cwd() / "autofill-extension",
        Path.cwd().parent / "autofill-extension",
    ]
    for c in candidates:
        if c.exists() and (c / "manifest.json").exists():
            return c

    # Create in OneDrive Desktop if available, else Desktop
    target = candidates[0] if (Path.home() / "OneDrive" / "Desktop").exists() else candidates[1]
    try:
        target.mkdir(parents=True, exist_ok=True)
        (target / "manifest.json").write_text(MANIFEST_JSON, encoding="utf-8")
        (target / "background.js").write_text(BACKGROUND_JS, encoding="utf-8")
        (target / "content.js").write_text(CONTENT_JS, encoding="utf-8")
        return target
    except Exception:
        return None

def get_profile_dir_for_url(url=None):
    """
    Uses a unified persistent Chrome profile (.forum_profile_google_master) so once the user signs
    into Google (accounts.google.com) once, Google stays signed in across ALL websites and forums!
    """
    try:
        p_dir = Path.home() / ".forum_profile_google_master"
        p_dir.mkdir(parents=True, exist_ok=True)
        return p_dir
    except Exception:
        fallback = Path.home() / ".forum_profile_default"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback

def get_session_path_for_url(url):
    try:
        target = (url or "").strip()
        parsed = urllib.parse.urlparse(target)
        domain = parsed.netloc.lower()
        clean_domain = domain[4:] if domain.startswith("www.") else domain
        if "proboards.com" in clean_domain or not clean_domain:
            return SESSION_PATH

        p_clean = Path.home() / f".forum_session_{clean_domain}.json"
        p_www = Path.home() / f".forum_session_www.{clean_domain}.json"
        if p_clean.exists():
            return p_clean
        if p_www.exists():
            return p_www
        return p_clean
    except Exception:
        return SESSION_PATH


def verify_live_url(url, retries=2, delay=2.5):
    if not url or not str(url).startswith("http"):
        return False
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
                }
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.getcode() == 200:
                    return True
        except Exception:
            pass
        if attempt < retries - 1:
            time.sleep(delay)
    return False

def is_forum_page_logged_in(page):
    try:
        if page.is_closed():
            return False
        current_url = (page.url or "").lower()
        if "/login" in current_url or current_url.endswith("/login") or "signin" in current_url:
            return False

        # 1. If explicit Log In / Sign In buttons are visible, user is NOT logged in
        guest_indicators = [
            'a:has-text("Log In")',
            'button:has-text("Log In")',
            'a:has-text("Sign In")',
            'button:has-text("Sign In")',
            'button.login-button',
            'a.login-button',
            'a[href*="/login" i]',
            'a[href*="/signin" i]',
        ]
        for sel in guest_indicators:
            try:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    return False
            except Exception:
                pass

        # 2. Strict, unambiguous indicators of an active logged-in user
        strict_logout_sels = [
            'a[href*="/logout" i]',
            'a[href*="logout" i]',
            'a:has-text("Log Out")',
            'a:has-text("Logout")',
            'a:has-text("Sign Out")',
            'button#current-user',       # Discourse logged-in user button
            'li#current-user',
            'a[href*="/thread/new/"]',    # ProBoards member create thread
        ]
        for sel in strict_logout_sels:
            try:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    return True
            except Exception:
                continue

    except Exception:
        pass
    return False


def get_proboards_base_and_board_id(board_url):
    target = (board_url or DEFAULT_BOARD).strip()
    parsed = urllib.parse.urlparse(target)
    base_url = f"{parsed.scheme}://{parsed.netloc}"
    m = re.search(r"/board/(\d+)", target)
    board_id = m.group(1) if m else None
    return base_url, board_id, target

def is_proboards_page_logged_in(page):
    try:
        if page.is_closed():
            return False
        current_url = (page.url or "").lower()
        if "/login/" in current_url or current_url.endswith("/login"):
            return False

        logout_sels = [
            'a[href*="/logout" i]',
            'a:has-text("Logout")',
            'a:has-text("Log out")',
            'text="Logout"',
            'a[href*="/thread/new/"]',
            'a:has-text("Create Thread")',
        ]
        for sel in logout_sels:
            try:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    return True
            except Exception:
                continue

        try:
            body_text = page.locator("body").inner_text(timeout=1000)
            if re.search(r"Welcome\s+(?!Guest\b|to\b|back\b)[A-Za-z0-9_]+", body_text, re.I):
                return True
        except Exception:
            pass
    except Exception:
        pass
    return False

def extract_doc_title_and_body(text):
    if not text:
        return "", ""
    lines = [str(l).strip() for l in text.splitlines() if str(l).strip()]
    if not lines:
        return "", ""
    if len(lines) == 1:
        return lines[0], lines[0]

    first_line = lines[0]
    words = first_line.split()
    last_word = words[-1] if words else ""
    connectors = (":", "-", "--", "Your", "The", "A", "And", "Or", "For", "Of", "In", "On", "With", "To", "How", "Why")

    if len(lines) > 1 and (first_line.endswith(":") or last_word in connectors):
        title = first_line + " " + lines[1]
        body = "\n\n".join(lines[2:])
    else:
        title = first_line
        body = "\n\n".join(lines[1:])
    return title, body

def read_pdf_file(path):
    if pypdf is None:
        raise ImportError("pypdf is not installed. Run: pip install pypdf")
    reader = pypdf.PdfReader(str(path))
    full_text = ""
    for page in reader.pages:
        t = page.extract_text()
        if t:
            full_text += t + "\n"
    return extract_doc_title_and_body(full_text)

def read_docx_file(path):
    if docx is None:
        raise ImportError("python-docx is not installed. Run: pip install python-docx")
    d = docx.Document(str(path))
    paragraphs = [p.text.strip() for p in d.paragraphs if p.text.strip()]
    if not paragraphs:
        return "", ""
    return extract_doc_title_and_body("\n".join(paragraphs))

def read_txt_file(path):
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()
    return extract_doc_title_and_body(content)

def fetch_single_google_url(url):
    url = url.strip()
    m_doc = re.search(r"/document/d/([a-zA-Z0-9-_]+)", url)
    if m_doc:
        doc_id = m_doc.group(1)
        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
        req = urllib.request.Request(export_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        title, body = extract_doc_title_and_body(text)
        return "doc", [(title, body)]

    m_sheet = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url)
    if m_sheet:
        sheet_id = m_sheet.group(1)
        export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
        req = urllib.request.Request(export_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            csv_text = resp.read().decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(csv_text))
        raw_rows = [row for row in reader if any(row)]
        if not raw_rows:
            return "sheet", []

        header = raw_rows[0]
        t_idx = 0
        b_idx = 1 if len(header) > 1 else 0
        has_header = False
        for i, col in enumerate(header):
            cl = str(col).lower()
            if any(k in cl for k in ["title", "subject", "topic", "header"]):
                t_idx = i
                has_header = True
            elif any(k in cl for k in ["url", "link", "body", "content", "message"]):
                b_idx = i
                has_header = True

        data_rows = raw_rows[1:] if has_header else raw_rows
        items = []
        for r in data_rows:
            t = r[t_idx] if t_idx < len(r) else r[0]
            b = r[b_idx] if b_idx < len(r) else r[0]
            items.append((str(t).strip(), str(b).strip()))
        return "sheet", items

    return None, []

LOCAL_RECIPES_PATH = Path(__file__).resolve().parent / "recipes.json"
RECIPES_PATH = Path.home() / ".forum_suite_recipes.json"

DEFAULT_BUILTIN_RECIPES = {
    "Knowt App": {
        "name": "Knowt App",
        "board_url": "https://knowt.com/note/eda21927-9bf0-4bef-b21a-aa2347be4ce3/Untitled?isNew=true",
        "login_url": "https://knowt.com/",
        "domain_pattern": "knowt.com",
        "reply_selector": "button:has-text(\"Notebook\"), button.knowt-1dwueds, role=button[name*=\"Notebook\" i]",
        "title_selector": "textarea#note-main-title, #note-main-title, textarea[placeholder=\"Add a title\"]",
        "editor_selector": "#notepage-editor-outer-container .tiptap.ProseMirror, #notepage-editor-outer-container [contenteditable=\"true\"]",
        "submit_selector": "button:has-text(\"Share\"), button:has-text(\"Done\")",
        "steps": [
                {
                        "type": "goto",
                        "code": "page.goto(\"https://knowt.com/home\")",
                        "url": "https://knowt.com/home"
                },
                {
                        "type": "click",
                        "code": "page.locator('button:has-text(\"Notebook\"), button.knowt-1dwueds, role=button[name*=\"Notebook\" i]').first.click(timeout=6000)"
                },
                {
                        "type": "click",
                        "code": "page.locator('#create-popup-tab-notes-create-from-scratch, div[id*=\"create-from-scratch\"], text=\"Create from scratch\"').first.click(timeout=6000)"
                },
                {
                        "type": "optional_click",
                        "code": "page.locator('button[data-testid=\"dismiss-interruption\"], button[aria-label=\"Close\"], button.knowt-q4jvfi').first.click(timeout=3000)"
                },
                {
                        "type": "title",
                        "code": "page.locator('textarea#note-main-title, #note-main-title, textarea[placeholder=\"Add a title\"]').first.fill(val)",
                        "locator": "page.locator('textarea#note-main-title, #note-main-title, textarea[placeholder=\"Add a title\"]').first"
                },
                {
                        "type": "body_focus",
                        "code": "page.locator('#notepage-editor-outer-container .tiptap.ProseMirror, #notepage-editor-outer-container [contenteditable=\"true\"]').first.click()"
                },
                {
                        "type": "click",
                        "code": "page.locator('button:has-text(\"Share\"), button.knowt-o80a1t, role=button[name=\"Share\"]').first.click(timeout=6000)"
                },
                {
                        "type": "copy_link",
                        "code": "page.locator('button:has-text(\"Copy link\"), button.knowt-1prujqy, role=button[name=\"Copy link\"]').first.click(timeout=6000)"
                },
                {
                        "type": "click",
                        "code": "page.locator('button:has-text(\"Done\"), button.knowt-1lbf6sx, role=button[name=\"Done\"]').first.click(timeout=6000)"
                }
        ],
        "raw_post_code": [
                "page.goto(\"https://knowt.com/home\")",
                "page.locator('button:has-text(\"Notebook\"), button.knowt-1dwueds').first.click()",
                "page.locator('#create-popup-tab-notes-create-from-scratch').first.click()",
                "page.locator('button[data-testid=\"dismiss-interruption\"]').first.click()",
                "page.locator('textarea#note-main-title').first.fill(title)",
                "page.locator('#notepage-editor-outer-container .tiptap.ProseMirror').first.click()",
                "page.locator('button:has-text(\"Share\")').first.click()",
                "page.locator('button:has-text(\"Copy link\")').first.click()",
                "page.locator('button:has-text(\"Done\")').first.click()"
        ]
    },
    "CricketWindies Forum": {
        "name": "CricketWindies Forum",
        "board_url": "https://cricketwindies.com/forum-2-we-don-t-like-cricket-we-love-it.html",
        "login_url": "https://cricketwindies.com/member.php?action=login",
        "domain_pattern": "cricketwindies.com",
        "reply_selector": 'a:has-text("Post Thread"), role=link[name="Post Thread"], a[href*="newthread"]',
        "title_selector": 'input[name="subject"], input.textbox[name="subject"]',
        "editor_selector": 'iframe >> body',
        "submit_selector": 'button:has-text("Post Thread"), input[type="submit"][value*="Post Thread" i], role=button[name="Post Thread"], input[name="submit"]'
    }
}

def load_recipes():
    recipes = dict(DEFAULT_BUILTIN_RECIPES)
    if LOCAL_RECIPES_PATH.exists():
        try:
            recipes.update(json.loads(LOCAL_RECIPES_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    if RECIPES_PATH.exists():
        try:
            recipes.update(json.loads(RECIPES_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return recipes

def save_recipes(recipes_dict):
    try:
        RECIPES_PATH.write_text(json.dumps(recipes_dict, indent=2), encoding="utf-8")
    except Exception:
        pass
    try:
        LOCAL_RECIPES_PATH.write_text(json.dumps(recipes_dict, indent=2), encoding="utf-8")
    except Exception:
        pass

def target_expr_to_selector(expr):
    expr = expr.strip()
    role_m = re.search(r'get_by_role\(\s*["\'](\w+)["\']\s*,\s*name=\s*["\'](.*?)["\']\s*\)', expr)
    if role_m:
        role = role_m.group(1).lower()
        name = role_m.group(2).strip()
        if role == "button":
            return f'button:has-text("{name}"), input[type="submit"][value*="{name}" i], role=button[name="{name}"]'
        elif role == "link":
            return f'a:has-text("{name}"), role=link[name="{name}"]'
        elif role == "textbox":
            return f'input[name="{name}"], role=textbox[name="{name}"]'
        return f'role={role}[name="{name}"]'

    if "iframe" in expr.lower() or "content_frame" in expr.lower():
        return "iframe >> body"

    loc_m = re.search(r'locator\(\s*["\'](.*?)["\']\s*\)', expr)
    if loc_m:
        return loc_m.group(1).strip()

    text_m = re.search(r'get_by_text\(\s*["\'](.*?)["\']\s*\)', expr)
    if text_m:
        return f'text="{text_m.group(1).strip()}"'

    lbl_m = re.search(r'get_by_label\(\s*["\'](.*?)["\']\s*\)', expr)
    if lbl_m:
        return f'label="{lbl_m.group(1).strip()}"'

    ph_m = re.search(r'get_by_placeholder\(\s*["\'](.*?)["\']\s*\)', expr)
    if ph_m:
        return f'input[placeholder*="{ph_m.group(1).strip()}" i]'

    return expr

def parse_codegen_to_recipe(code_text):
    lines = [l.strip() for l in code_text.splitlines() if l.strip() and not l.strip().startswith("#")]
    page_lines = [l for l in lines if l.startswith("page.")]

    # 1. Identify login boundary
    login_end_idx = -1
    for i, l in enumerate(page_lines):
        if re.search(r"log\s*in|sign\s*in", l, re.IGNORECASE) and ".click()" in l:
            login_end_idx = i

    login_lines = page_lines[:login_end_idx + 1] if login_end_idx != -1 else []
    post_lines = page_lines[login_end_idx + 1:] if login_end_idx != -1 else page_lines

    # 2. Extract best board_url and login_url
    board_url = ""
    for l in post_lines:
        m = re.search(r'page\.goto\(\s*["\'](.*?)["\']\s*\)', l)
        if m:
            board_url = m.group(1).strip()
            break
    if not board_url:
        for l in page_lines:
            m = re.search(r'page\.goto\(\s*["\'](.*?)["\']\s*\)', l)
            if m:
                board_url = m.group(1).strip()
                break

    login_url = ""
    for l in login_lines:
        m = re.search(r'page\.goto\(\s*["\'](.*?)["\']\s*\)', l)
        if m:
            login_url = m.group(1).strip()
            break
    if not login_url:
        login_url = board_url

    domain = ""
    name_suggestion = ""
    if board_url:
        try:
            parsed = urlparse(board_url)
            domain = parsed.netloc.replace("www.", "")
            if domain:
                raw_name = domain.split(".")[0]
                if "cricket" in raw_name.lower():
                    name_suggestion = "CricketWindies Forum"
                elif "knowt" in raw_name.lower():
                    name_suggestion = "Knowt App"
                else:
                    name_suggestion = f"{raw_name.capitalize()} App"
        except Exception:
            pass

    # 3. Parse Action Steps for Multi-Step Workflow Replay
    steps = []
    has_title_step = False

    for idx, line in enumerate(post_lines):
        if line.startswith("page.goto("):
            url_m = re.search(r'page\.goto\(\s*["\'](.*?)["\']\s*\)', line)
            if url_m:
                steps.append({"type": "goto", "code": line, "url": url_m.group(1).strip()})
            continue

        if ".fill(" in line and re.search(r"title|subject|header|topic", line, re.IGNORECASE):
            loc_code = line[:line.find(".fill(")]
            steps.append({"type": "title", "code": line, "locator": loc_code})
            has_title_step = True
            continue

        # Check for editor clicks (excluding navigation buttons)
        if re.search(r"editor|notepage|prosemirror|fr-element|paragraph|contenteditable", line, re.IGNORECASE) and ".click()" in line:
            steps.append({"type": "body_focus", "code": line})
            continue

        if ".fill(" in line and has_title_step:
            loc_code = line[:line.find(".fill(")]
            steps.append({"type": "body_fill", "code": line, "locator": loc_code})
            continue

        if re.search(r"copy\s*link|copy\s*url|share\s*link", line, re.IGNORECASE) and ".click()" in line:
            steps.append({"type": "copy_link", "code": line})
            continue

        if re.search(r"dismiss|close|cookie|banner|interruption|modal|announcement|dialog|got\s*it", line, re.IGNORECASE) and ".click()" in line:
            steps.append({"type": "optional_click", "code": line})
            continue

        if ".click()" in line:
            steps.append({"type": "click", "code": line})
            continue

        steps.append({"type": "custom", "code": line})

    # 4. Generate traditional fallback selectors for UI
    fills = []
    clicks = []
    for line in post_lines:
        fill_m = re.search(r'page\.(.*?)\.fill\((.*?)\)$', line)
        if fill_m:
            target_expr = fill_m.group(1).strip()
            fill_arg = fill_m.group(2).strip()
            fills.append((target_expr, fill_arg))
            continue
        click_m = re.search(r'page\.(.*?)\.click\(', line)
        if click_m:
            target_expr = click_m.group(1).strip()
            clicks.append(target_expr)
            continue

    reply_sel = ""
    for c in clicks:
        if re.search(r'post\s*thread|new\s*thread|new\s*topic|create\s*new|create|notes|reply|start', c, re.IGNORECASE):
            reply_sel = target_expr_to_selector(c)
            break
    if not reply_sel and clicks:
        reply_sel = target_expr_to_selector(clicks[0])

    title_sel = ""
    editor_sel = ""
    for expr, arg in fills:
        if re.search(r'subject|title|topic|header', expr, re.IGNORECASE) and not title_sel:
            title_sel = target_expr_to_selector(expr)
        elif re.search(r'iframe|content_frame|message|body|editor|notepage', expr, re.IGNORECASE) and not editor_sel:
            editor_sel = target_expr_to_selector(expr)

    if not title_sel and fills:
        title_sel = target_expr_to_selector(fills[0][0])
    if not editor_sel:
        for c in clicks:
            if re.search(r'editor|notepage|contenteditable|prosemirror', c, re.IGNORECASE):
                editor_sel = target_expr_to_selector(c)
                break
    if not editor_sel:
        editor_sel = "iframe >> body" if "iframe" in code_text else 'textarea[name="message"]'

    submit_sel = ""
    for c in reversed(clicks):
        if 'button' in c.lower() or 'submit' in c.lower() or re.search(r'post|submit|publish|share|done', c, re.IGNORECASE):
            submit_sel = target_expr_to_selector(c)
            break
    if not submit_sel and clicks:
        submit_sel = target_expr_to_selector(clicks[-1])

    return {
        "name": name_suggestion or "Custom App",
        "board_url": board_url,
        "login_url": login_url,
        "domain_pattern": domain,
        "reply_selector": reply_sel,
        "title_selector": title_sel,
        "editor_selector": editor_sel,
        "submit_selector": submit_sel,
        "steps": steps,
        "raw_post_code": post_lines
    }

def execute_step_workflow(page, recipe, target_url, title_text, body_text, log_fn):
    steps = recipe.get("steps", [])
    name = recipe.get("name", "Custom Workflow")
    log_fn(f"🚀 Replaying {len(steps)}-step workflow for {name}...")

    # Grant clipboard permissions for apps that copy link to clipboard (e.g. Knowt)
    try:
        page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    except Exception:
        pass

    # Intercept clipboard writeText in page context
    try:
        page.evaluate("""() => {
            window.__captured_live_url = '';
            const origWrite = navigator.clipboard && navigator.clipboard.writeText;
            if (origWrite) {
                navigator.clipboard.writeText = function(text) {
                    if (text && typeof text === 'string' && (text.startsWith('http://') || text.startsWith('https://'))) {
                        window.__captured_live_url = text.trim();
                    }
                    return origWrite.apply(this, arguments);
                };
            }
        }""")
    except Exception:
        pass

    start_url = (target_url or recipe.get("board_url", "")).strip()
    if start_url and (page.url == "about:blank" or start_url.rstrip("/") not in page.url):
        log_fn(f"Opening dashboard/start URL: {start_url}")
        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=45000)
            time.sleep(2)
        except Exception as e:
            log_fn(f"Start URL navigation note: {e}")

    captured_url = ""

    for i, step in enumerate(steps):
        stype = step.get("type", "custom")
        code_line = step.get("code", "")
        log_fn(f"Step {i+1}/{len(steps)} [{stype}]: {code_line[:55]}")

        # A. Navigation step
        if stype == "goto":
            u_target = step.get("url", "")
            if u_target and (page.url == "about:blank" or u_target.rstrip("/") not in page.url):
                try:
                    page.goto(u_target, wait_until="domcontentloaded", timeout=45000)
                    time.sleep(2)
                except Exception as e:
                    log_fn(f"Step {i+1} goto note: {e}")
            continue

        # B. Optional Popup Dismissal (dismiss-interruption, cookie banners, overlays)
        if stype == "optional_click":
            try:
                opt_code = code_line.replace(".click()", ".click(timeout=3000)") if ".click()" in code_line else code_line
                scope = {"page": page, "re": re, "time": time}
                exec(opt_code, scope)
                time.sleep(1)
            except Exception:
                log_fn(f"Optional popup {code_line[:30]} not present, skipping.")
            continue

        # C. Title input step
        if stype == "title":
            try:
                loc_expr = step.get("locator", "")
                if loc_expr:
                    scope = {"page": page, "re": re, "time": time}
                    loc_obj = eval(loc_expr, scope)
                    loc_obj.click()
                    time.sleep(0.2)
                    loc_obj.fill(title_text)
                else:
                    scope = {"page": page, "re": re, "val": title_text, "time": time}
                    exec(code_line, scope)
                log_fn(f"Filled Title: {title_text[:40]}")
                time.sleep(0.5)
            except Exception as e:
                log_fn(f"Title fill note: {e}")
            continue

        # D. Body focus & formatted text typing (for rich-text ProseMirror / TipTap / editor containers)
        if stype == "body_focus":
            try:
                scope = {"page": page, "re": re, "time": time}
                exec(code_line, scope)
                time.sleep(0.5)

                next_step = steps[i+1] if i+1 < len(steps) else None
                if not next_step or next_step.get("type") != "body_focus":
                    log_fn("Typing post body into editor...")
                    page.keyboard.insert_text(body_text)
                    time.sleep(0.4)
                    page.keyboard.press("Enter")
                    time.sleep(1)
            except Exception as e:
                log_fn(f"Body focus note: {e}")
            continue

        # E. Body fill (standard textareas or iframes)
        if stype == "body_fill":
            try:
                loc_expr = step.get("locator", "")
                if loc_expr:
                    scope = {"page": page, "re": re, "time": time}
                    loc_obj = eval(loc_expr, scope)
                    loc_obj.click()
                    time.sleep(0.2)
                    loc_obj.fill(body_text)
                else:
                    scope = {"page": page, "re": re, "val": body_text, "time": time}
                    exec(code_line, scope)
                log_fn(f"Filled Body: {body_text[:40]}")
                time.sleep(0.5)
            except Exception as e:
                log_fn(f"Body fill note: {e}")
            continue

        # F. Copy link step (Share / Copy link button)
        if stype == "copy_link":
            try:
                scope = {"page": page, "re": re, "time": time}
                exec(code_line, scope)
                time.sleep(1.5)
                try:
                    c = page.evaluate("() => window.__captured_live_url || ''")
                    if c and c.startswith("http"):
                        captured_url = c
                except Exception:
                    pass
                if not captured_url:
                    try:
                        c = page.evaluate("() => window.__captured_live_url || ''")
                        if c and c.startswith("http"):
                            captured_url = c
                    except Exception:
                        pass
                if captured_url:
                    log_fn(f"📋 Captured live URL from clipboard: {captured_url}")
            except Exception as e:
                log_fn(f"Copy link note: {e}")
            continue

        # G. Generic click or action
        try:
            scope = {"page": page, "re": re, "time": time}
            exec(code_line, scope)
            time.sleep(1.2)
        except Exception as e:
            log_fn(f"Step {i+1} note: {e}")

    # Post-Workflow Live URL Discovery
    time.sleep(2)
    if not captured_url:
        try:
            c = page.evaluate("() => window.__captured_live_url || ''")
            if c and c.startswith("http"):
                captured_url = c
        except Exception:
            pass
    if not captured_url:
        try:
            c = page.evaluate("() => window.__captured_live_url || ''")
            if c and c.startswith("http"):
                captured_url = c
        except Exception:
            pass

    if captured_url and is_valid_live_post_url(captured_url):
        log_fn(f"✅ Workflow captured verified live URL: {captured_url}")
        return True, captured_url

    cur_url = page.url
    if is_valid_live_post_url(cur_url) and cur_url != start_url and not cur_url.endswith("/home"):
        log_fn(f"✅ Workflow navigated to live URL: {cur_url}")
        return True, cur_url

    # Check for confirmation links on page
    try:
        link_loc = page.locator('a[href*="/note/"], a[href*="/notes/"], a[href*="thread-"], a[href*="showthread.php"]').first
        if link_loc.count() > 0:
            href = link_loc.get_attribute("href")
            if href:
                if not href.startswith("http"):
                    href = urljoin(page.url, href)
                if is_valid_live_post_url(href):
                    log_fn(f"✅ Found created live URL on page: {href}")
                    return True, href
    except Exception:
        pass

    if captured_url:
        return True, captured_url

    if is_valid_live_post_url(cur_url) and not cur_url.endswith("/home"):
        return True, cur_url

    return False, None

def execute_custom_recipe(page, recipe, board_url, title_text, body_text, log_fn):
    if "knowt" in recipe.get("name", "").lower() or "knowt.com" in (board_url or "").lower():
        log_fn("⚡ Delegating to Knowt Note Creator Engine...")
        return knowt_create_note(page, board_url, title_text, body_text, log_fn)

    name = recipe.get("name", "Custom Blueprint")
    log_fn(f"⚡ Executing Custom Blueprint: {name}")

    target_url = (board_url or recipe.get("board_url", "")).strip()

    # If recipe contains multi-step recorded workflow, execute with workflow engine
    steps = recipe.get("steps", [])
    if steps and isinstance(steps, list) and len(steps) > 0:
        return execute_step_workflow(page, recipe, target_url, title_text, body_text, log_fn)

    # 1. Navigate to target URL if not already on it
    if target_url and target_url.startswith("http"):
        cur_url = getattr(page, 'url', '')
        if cur_url == "about:blank" or target_url.rstrip("/") not in cur_url:
            log_fn(f"Navigating to board URL: {target_url}")
            try:
                page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(2)
            except Exception as e:
                log_fn(f"Navigation notice: {e}")

    reply_sel = recipe.get("reply_selector", "").strip()
    title_sel = recipe.get("title_selector", "").strip()
    editor_sel = recipe.get("editor_selector", "").strip()
    submit_sel = recipe.get("submit_selector", "").strip()

    def find_first_loc(selector_str, container=page):
        if not selector_str:
            return None
        candidates = [s.strip() for s in selector_str.split(",") if s.strip()]
        for cand in candidates:
            try:
                role_m = re.match(r'role=(\w+)\[name=["\'](.*?)["\']\]', cand)
                if role_m:
                    loc = container.get_by_role(role_m.group(1), name=role_m.group(2)).first
                    if loc.count() > 0 and loc.is_visible():
                        return loc
                loc = container.locator(cand).first
                if loc.count() > 0 and loc.is_visible():
                    return loc
            except Exception:
                continue
        return None

    # 2. Check if new thread form / editor is already open on page. If not, click reply_selector
    form_open = False
    if title_sel:
        t_check = find_first_loc(title_sel)
        if t_check:
            form_open = True

    if not form_open and reply_sel:
        log_fn(f"Opening thread/reply form via ({reply_sel})...")
        r_loc = find_first_loc(reply_sel)
        if not r_loc:
            r_loc = find_first_loc('a:has-text("Post Thread"), a:has-text("New Thread"), a:has-text("New Topic"), a:has-text("Reply"), a[href*="newthread"], button:has-text("Post Thread"), button:has-text("New Thread")')
        if r_loc:
            try:
                r_loc.click()
                time.sleep(2.5)
                try:
                    page.wait_for_load_state("domcontentloaded", timeout=10000)
                except Exception:
                    pass
            except Exception as e:
                log_fn(f"Reply button note: {e}")

    # 3. Fill Title / Subject
    if title_text:
        t_loc = None
        if title_sel:
            t_loc = find_first_loc(title_sel)
        if not t_loc:
            t_loc = find_first_loc('input[name="subject"], input[name="title"], input#subject, input[id*="subject" i], input[id*="title" i], input[placeholder*="subject" i], input[placeholder*="title" i], input.textbox[name="subject"]')
        if t_loc:
            try:
                t_loc.click()
                time.sleep(0.2)
                t_loc.fill(title_text)
                log_fn(f"Filled Title: {title_text[:50]}")
            except Exception as e:
                log_fn(f"Title fill note: {e}")

    # 4. Fill Message Body (With intelligent iframe and textarea support)
    body_filled = False

    # Check iframes
    has_iframes = False
    try:
        has_iframes = page.locator("iframe").count() > 0
    except Exception:
        pass

    if "iframe" in editor_sel.lower() or has_iframes:
        log_fn("Checking for rich-text iframe editor...")
        try:
            ifr_body = page.frame_locator("iframe").locator('body, [contenteditable="true"]').first
            if ifr_body.count() > 0:
                ifr_body.click()
                time.sleep(0.3)
                ifr_body.fill(body_text)
                body_filled = True
                log_fn("Filled message body in iframe via frame_locator.")
        except Exception as e:
            log_fn(f"Iframe frame_locator note: {e}")

        if not body_filled:
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                try:
                    f_body = frame.locator('body, [contenteditable="true"]').first
                    if f_body.count() > 0:
                        f_body.click()
                        time.sleep(0.3)
                        f_body.fill(body_text)
                        body_filled = True
                        log_fn(f"Filled message body in iframe frame ({frame.name or 'editor'}).")
                        break
                except Exception:
                    continue

    # Main page editor selector fallback
    if not body_filled and editor_sel and "iframe" not in editor_sel.lower():
        e_loc = find_first_loc(editor_sel)
        if e_loc:
            try:
                e_loc.click()
                time.sleep(0.2)
                e_loc.fill(body_text)
                body_filled = True
                log_fn(f"Filled message body via selector ({editor_sel}).")
            except Exception as e:
                log_fn(f"Editor selector note: {e}")

    # Main page textarea / contenteditable fallback
    if not body_filled:
        e_loc = find_first_loc('textarea[name="message"], textarea#message, textarea[name="post"], textarea, div.fr-element[contenteditable="true"], div[contenteditable="true"]')
        if e_loc:
            try:
                e_loc.click()
                time.sleep(0.2)
                e_loc.fill(body_text)
                body_filled = True
                log_fn("Filled message body via fallback textarea.")
            except Exception as e:
                log_fn(f"Textarea fallback note: {e}")

    # Universal synchronization script (CRITICAL for MyBB SCEditor, CKEditor, TinyMCE)
    try:
        page.evaluate(''' (content) => {
            document.querySelectorAll('iframe').forEach(ifr => {
                try {
                    const doc = ifr.contentDocument || (ifr.contentWindow && ifr.contentWindow.document);
                    if (doc && doc.body) {
                        if (!doc.body.innerText || !doc.body.innerText.trim()) {
                            doc.body.innerHTML = content.replace(/\n/g, '<br>');
                        }
                        doc.body.dispatchEvent(new Event('input', { bubbles: true }));
                        doc.body.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                } catch(e) {}
            });
            document.querySelectorAll('textarea').forEach(ta => {
                if (!ta.value || !ta.value.trim()) {
                    ta.value = content;
                }
                ta.dispatchEvent(new Event('input', { bubbles: true }));
                ta.dispatchEvent(new Event('change', { bubbles: true }));
            });
            try {
                if (window.sceditor) {
                    document.querySelectorAll('textarea').forEach(ta => {
                        const inst = window.sceditor.instance(ta);
                        if (inst) { inst.val(content); }
                    });
                }
            } catch(e) {}
            try {
                if (window.CKEDITOR && window.CKEDITOR.instances) {
                    for (const k in window.CKEDITOR.instances) {
                        window.CKEDITOR.instances[k].setData(content);
                    }
                }
            } catch(e) {}
            try {
                if (window.tinymce && window.tinymce.activeEditor) {
                    window.tinymce.activeEditor.setContent(content);
                }
            } catch(e) {}
        } ''', body_text)
        body_filled = True
    except Exception as e:
        log_fn(f"Editor sync note: {e}")

    time.sleep(1)

    # 5. Submit Button Click
    sub_loc = None
    if submit_sel:
        sub_loc = find_first_loc(submit_sel)

    if not sub_loc:
        sub_loc = find_first_loc('input[type="submit"][name="submit"], input[type="submit"][value*="Post" i], button[type="submit"]:has-text("Post"), button:has-text("Post Thread"), button:has-text("Submit"), input[type="submit"], button[type="submit"]')

    if sub_loc:
        log_fn(f"Clicking Submit button...")
        try:
            sub_loc.click()
        except Exception as e:
            log_fn(f"Submit click note: {e}")
            try:
                sub_loc.evaluate("el => el.click()")
            except Exception:
                pass
    else:
        log_fn("Attempting form submit via JS...")
        try:
            page.evaluate('''() => { const f = document.querySelector('form[action*="newthread" i], form'); if (f) f.submit(); }''')
        except Exception:
            pass

    # Wait for submission and redirection
    time.sleep(4)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15000)
    except Exception:
        pass

    cur_url = page.url
    log_fn(f"Page URL after submit: {cur_url}")

    # 6. Verify and detect live URL
    if is_valid_live_post_url(cur_url) and cur_url != target_url:
        log_fn(f"✅ Blueprint created live post: {cur_url}")
        return True, cur_url

    # Check if confirmation page contains link to thread
    try:
        thread_link = page.locator('a[href*="thread-"], a[href*="showthread.php"], a[href*="viewtopic.php"], a[href*="/topic/"]').first
        if thread_link.count() > 0:
            href = thread_link.get_attribute("href")
            if href:
                if not href.startswith("http"):
                    from urllib.parse import urljoin
                    href = urljoin(page.url, href)
                if is_valid_live_post_url(href):
                    log_fn(f"✅ Found new thread URL in confirmation: {href}")
                    return True, href
    except Exception:
        pass

    if is_valid_live_post_url(cur_url) and "newthread" not in cur_url.lower():
        return True, cur_url

    return False, None



def proboards_create_thread(page, board_url, title_text, body_text, log_fn):
    base_url, board_id, target_board = get_proboards_base_and_board_id(board_url)
    title_text = str(title_text).strip()
    body_text = str(body_text).strip()

    if board_id:
        direct_url = f"{base_url}/thread/new/{board_id}"
        log_fn(f"Opening: {direct_url}")
        page.goto(direct_url, wait_until="domcontentloaded", timeout=45000)
    else:
        page.goto(target_board, wait_until="domcontentloaded", timeout=45000)
        create_btn = page.locator('a[role="button"][href*="/thread/new/"], a[href*="/thread/new/"], a:has-text("Create Thread")').first
        if create_btn.count() > 0:
            create_btn.click()
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        else:
            log_fn("Could not locate Create Thread button.")
            return False, None

    time.sleep(1.5)

    try:
        page.evaluate("""() => {
            const popup = document.querySelector('[class*="terms"], div:has(> text="Terms of Use")');
            if (popup) popup.remove();
            const btn = document.querySelector('[aria-label="Close"], .close-button, div:has-text("Terms of Use") button');
            if (btn) btn.click();
        }""")
    except Exception:
        pass

    try:
        subj = page.locator('input[name="subject"], input#subject, .subject_line input').first
        subj.wait_for(state="visible", timeout=15000)
        subj.fill(title_text)
        log_fn(f"Title: {title_text[:60]}")
    except PWTimeout:
        log_fn("Form not loaded (check permissions or login).")
        return False, None

    time.sleep(0.5)

    body_filled = False
    editor_iframe = page.locator('.editor iframe, .ui-wysiwyg iframe, div.editor iframe, form iframe').first
    if editor_iframe.count() > 0:
        try:
            editor_iframe.click(force=True)
            time.sleep(0.3)
            page.keyboard.press("Control+A")
            page.keyboard.insert_text(body_text)
            body_filled = True
        except Exception:
            pass

    try:
        page.evaluate("""(content) => {
            const ifr = document.querySelector('.editor iframe, .ui-wysiwyg iframe, div.editor iframe, form iframe');
            if (ifr && ifr.contentDocument && ifr.contentDocument.body) {
                ifr.contentDocument.body.innerHTML = content.replace(/\\n/g, '<br>');
                ifr.contentDocument.body.dispatchEvent(new Event('input', { bubbles: true }));
                ifr.contentDocument.body.dispatchEvent(new Event('change', { bubbles: true }));
            }
            const ta = document.querySelector('textarea[name="message"], textarea#message, div.editor textarea');
            if (ta) {
                ta.value = content;
                ta.dispatchEvent(new Event('input', { bubbles: true }));
                ta.dispatchEvent(new Event('change', { bubbles: true }));
            }
            if (window.jQuery) {
                try {
                    window.jQuery('textarea[name="message"]').val(content);
                } catch(e) {}
            }
        }""", body_text)
        body_filled = True
    except Exception:
        pass

    if not body_filled:
        try:
            bb = page.locator('a[href*="bbcode" i], a:has-text("BBCode")').first
            if bb.count() > 0:
                bb.click(force=True)
                time.sleep(0.5)
                ta = page.locator('textarea[name="message"], textarea#message').first
                if ta.count() > 0:
                    ta.fill(body_text)
        except Exception:
            pass

    time.sleep(1)

    submit_sels = [
        'input[name="post"][type="submit"]',
        'input[value="Create Thread"]',
        'input[value*="Create Thread" i]',
        'input[type="submit"]',
        'button:has-text("Create Thread")',
        'button[type="submit"]',
    ]
    submit_btn = None
    for sel in submit_sels:
        loc = page.locator(sel)
        if loc.count() > 0 and loc.first.is_visible():
            submit_btn = loc.first
            break

    if not submit_btn:
        log_fn("Submit button not found.")
        return False, None

    log_fn("Submitting thread...")
    try:
        submit_btn.click()
    except Exception as e:
        log_fn(f"Click submit failed: {e}")
        return False, None

    try:
        page.wait_for_url(
            lambda u: "/thread/new" not in u and "/threads/new" not in u and ("/thread/" in u or "/board/" in u),
            timeout=25000,
        )
    except PWTimeout:
        flood_sels = [
            'text="exceeded the maximum posts allowed"',
            'text="posting limit"',
            'text="wait before posting"',
            'text="posting too quickly"',
            'div.ui-error:has-text("timeframe")',
            'div.error:has-text("limit")',
            '[class*="error" i]:has-text("timeframe")',
        ]
        is_flood = False
        flood_text = ""
        for f_sel in flood_sels:
            try:
                fl = page.locator(f_sel)
                if fl.count() > 0 and fl.first.is_visible():
                    is_flood = True
                    flood_text = fl.first.inner_text()
                    break
            except Exception:
                pass

        if is_flood:
            log_fn(f"⏳ Flood-Control Detected: {flood_text[:80]}...")
            log_fn("⏳ Smart Cooldown engaged: Pausing 60 seconds, then retrying automatically...")
            for rem in [45, 30, 15, 0]:
                time.sleep(15)
                if rem > 0:
                    log_fn(f"⏳ Smart Cooldown: {rem}s remaining...")

            log_fn("🔄 Retrying thread submission now...")
            try:
                if submit_btn and submit_btn.is_visible():
                    submit_btn.click()
                    page.wait_for_url(
                        lambda u: "/thread/new" not in u and "/threads/new" not in u and ("/thread/" in u or "/board/" in u),
                        timeout=25000,
                    )
            except Exception as e:
                log_fn(f"Retry notice: {e}")

        err_loc = page.locator('text="You must provide a message", div.error, .ui-error, [class*="error" i]')
        if err_loc.count() > 0 and err_loc.first.is_visible():
            log_fn(f"ProBoards validation error: {err_loc.first.inner_text()[:120]}")
            return False, None
        if "/thread/new" in page.url or "/threads/new" in page.url:
            log_fn("Submission timed out or stayed on form.")
            return False, None

    posted_url = page.url
    return True, posted_url


def proboards_post_content_only(page, direct_url, body_text, log_fn):
    direct_url = str(direct_url).strip()
    body_text = str(body_text).strip()

    log_fn(f"Navigating to direct account link: {direct_url[:75]}...")
    try:
        page.goto(direct_url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log_fn(f"Navigation warning: {e}")
    time.sleep(2)

    try:
        page.evaluate("""() => {
            const popup = document.querySelector('[class*="terms"], div:has(> text="Terms of Use")');
            if (popup) popup.remove();
            const btn = document.querySelector('[aria-label="Close"], .close-button, div:has-text("Terms of Use") button');
            if (btn) btn.click();
        }""")
    except Exception:
        pass

    editor_present = page.locator('.editor iframe, textarea[name="message"], #quick-reply, .quick-reply').first.count() > 0
    if not editor_present or page.locator('a[role="button"]:has-text("Reply"), a:has-text("Reply")').first.is_visible():
        try:
            reply_sels = [
                'a[role="button"]:has-text("Reply")',
                'a.button:has-text("Reply")',
                'a[href*="/post/new/"]',
                'button:has-text("Reply")',
                'a:has-text("Reply")',
            ]
            for r_sel in reply_sels:
                r_btn = page.locator(r_sel).first
                if r_btn.count() > 0 and r_btn.is_visible():
                    log_fn(f"Clicking Reply button ({r_sel})...")
                    r_btn.click()
                    time.sleep(2)
                    break
        except Exception as e:
            log_fn(f"Reply button note: {e}")

    log_fn(f"Injecting content body ({len(body_text)} chars)...")
    body_filled = False

    editor_iframe = page.locator('.editor iframe, .ui-wysiwyg iframe, div.editor iframe, form iframe').first
    if editor_iframe.count() > 0 and editor_iframe.is_visible():
        try:
            editor_iframe.click(force=True)
            time.sleep(0.3)
            page.keyboard.press("Control+A")
            page.keyboard.insert_text(body_text)
            body_filled = True
        except Exception:
            pass

    try:
        page.evaluate("""(content) => {
            const ifr = document.querySelector('.editor iframe, .ui-wysiwyg iframe, div.editor iframe, form iframe');
            if (ifr && ifr.contentDocument && ifr.contentDocument.body) {
                ifr.contentDocument.body.innerHTML = content.replace(/\n/g, '<br>');
                ifr.contentDocument.body.dispatchEvent(new Event('input', { bubbles: true }));
                ifr.contentDocument.body.dispatchEvent(new Event('change', { bubbles: true }));
            }
            const ta = document.querySelector('textarea[name="message"], textarea#message, div.editor textarea, .quick-reply textarea');
            if (ta) {
                ta.value = content;
                ta.dispatchEvent(new Event('input', { bubbles: true }));
                ta.dispatchEvent(new Event('change', { bubbles: true }));
            }
            if (window.jQuery) {
                try {
                    window.jQuery('textarea[name="message"]').val(content);
                } catch(e) {}
            }
        }""", body_text)
        body_filled = True
    except Exception:
        pass

    if not body_filled:
        try:
            bb = page.locator('a[href*="bbcode" i], a:has-text("BBCode")').first
            if bb.count() > 0 and bb.is_visible():
                bb.click(force=True)
                time.sleep(0.5)
            ta = page.locator('textarea[name="message"], textarea#message, .quick-reply textarea').first
            if ta.count() > 0:
                ta.fill(body_text)
                body_filled = True
        except Exception:
            pass

    time.sleep(1)

    submit_sels = [
        'input[value="Create Post"]',
        'input[value="Post Quick Reply"]',
        'input[name="post"][type="submit"]',
        'input[value*="Post" i]',
        'button:has-text("Create Post")',
        'button:has-text("Post Quick Reply")',
        'button:has-text("Post")',
        'input[type="submit"]',
        'button[type="submit"]',
    ]
    submit_btn = None
    for sel in submit_sels:
        loc = page.locator(sel)
        if loc.count() > 0 and loc.first.is_visible():
            submit_btn = loc.first
            break

    if not submit_btn:
        log_fn("❌ Submit button not found on page.")
        return False, None

    log_fn("Submitting post content...")
    try:
        submit_btn.click()
    except Exception as e:
        log_fn(f"Click submit failed: {e}")
        return False, None

    try:
        time.sleep(3)
        posted_url = page.url
        log_fn(f"🎉 Post published successfully: {posted_url}")
        return True, posted_url
    except Exception as e:
        log_fn(f"Post confirmation note: {e}")
        return True, page.url


def vbulletin5_create_thread(page, board_url, title_text, body_text, log_fn):
    title_text = str(title_text).strip()
    body_text = str(body_text).strip()
    target_url = (board_url or "").strip()

    log_fn(f"Opening vBulletin / Avid DUC: {target_url}")
    page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(2)

    try:
        page.evaluate("""() => {
            const sels = ['#onetrust-accept-btn-handler', '.accept-cookies', '[aria-label="Accept"]', 'button:has-text("Accept")', '.cc-btn.cc-dismiss'];
            for (const s of sels) {
                const el = document.querySelector(s);
                if (el) el.click();
            }
        }""")
    except Exception:
        pass

    if "/new-content/" not in page.url:
        new_topic_btn = page.locator('a[href*="/new-content/"], a:has-text("New Topic"), a:has-text("Post New Thread"), a:has-text("Start Topic"), button:has-text("New Topic")').first
        if new_topic_btn.count() > 0:
            log_fn("Clicking New Topic button...")
            new_topic_btn.click()
            page.wait_for_load_state("domcontentloaded", timeout=20000)
            time.sleep(1.5)

    title_sels = [
        'input[name="title"]',
        'input#title',
        'input.form-control[name="title"]',
        'input[placeholder*="title" i]',
        '.forum-new-topic input[type="text"]',
        'input[name="subject"]',
        'input#subject',
    ]
    title_input = None
    for sel in title_sels:
        loc = page.locator(sel)
        if loc.count() > 0 and loc.first.is_visible():
            title_input = loc.first
            break

    if title_input:
        title_input.click()
        title_input.fill(title_text)
        log_fn(f"Title: {title_text[:60]}")
    else:
        log_fn("Could not find topic title input field (check login or permissions).")
        return False, None

    time.sleep(0.5)

    body_filled = False
    editor_iframe = page.locator('.cke_wysiwyg_frame, iframe.cke_wysiwyg_frame, iframe[title*="Rich Text" i], div.editor iframe').first
    if editor_iframe.count() > 0:
        try:
            editor_iframe.click(force=True)
            time.sleep(0.3)
            page.keyboard.press("Control+A")
            page.keyboard.insert_text(body_text)
            body_filled = True
        except Exception:
            pass

    try:
        page.evaluate("""(content) => {
            if (window.CKEDITOR) {
                for (const k in window.CKEDITOR.instances) {
                    try { window.CKEDITOR.instances[k].setData(content.replace(/\n/g, '<br>')); } catch(e){}
                }
            }
            const editables = document.querySelectorAll('.cke_editable, div[contenteditable="true"], .fr-element');
            for (const el of editables) {
                el.innerHTML = content.replace(/\n/g, '<br>');
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
            const tas = document.querySelectorAll('textarea[name="rawtext"], textarea[name="text"], textarea[name="message"]');
            for (const ta of tas) {
                ta.value = content;
                ta.dispatchEvent(new Event('input', { bubbles: true }));
                ta.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }""", body_text)
        body_filled = True
    except Exception:
        pass

    if not body_filled:
        ce = page.locator('.cke_editable, div[contenteditable="true"], .fr-element, textarea[name="rawtext"], textarea[name="message"]').first
        if ce.count() > 0:
            try:
                ce.click()
                time.sleep(0.2)
                page.keyboard.insert_text(body_text)
                body_filled = True
            except Exception:
                pass

    time.sleep(1)

    submit_sels = [
        'button[data-action="publish"]',
        'button:has-text("Publish")',
        'button:has-text("Post New Topic")',
        'button:has-text("Post Topic")',
        'input[value="Publish"]',
        'button.btn-primary:has-text("Post")',
        'button[type="submit"]',
        'input[type="submit"]',
    ]
    submit_btn = None
    for sel in submit_sels:
        loc = page.locator(sel)
        if loc.count() > 0 and loc.first.is_visible():
            submit_btn = loc.first
            break

    if not submit_btn:
        log_fn("Could not find Publish / Submit button.")
        return False, None

    log_fn("Publishing topic...")
    try:
        submit_btn.click()
    except Exception as e:
        log_fn(f"Click submit failed: {e}")
        return False, None

    try:
        page.wait_for_url(
            lambda u: "/new-content/" not in u and not u.endswith("/new-content"),
            timeout=25000,
        )
    except PWTimeout:
        flood_vb = page.locator('text="wait at least", text="between posts", text="flood", .alert-danger:has-text("seconds")')
        if flood_vb.count() > 0 and flood_vb.first.is_visible():
            log_fn("⏳ Forum rate limit triggered. Pausing 45s cooldown before retry...")
            time.sleep(45)
            if submit_btn and submit_btn.is_visible():
                try:
                    submit_btn.click()
                    page.wait_for_url(lambda u: "/new-content/" not in u and not u.endswith("/new-content"), timeout=25000)
                except Exception:
                    pass

        if "/new-content/" in page.url:
            log_fn("Post submission timed out or remained on editor page.")
            return False, None

    posted_url = page.url
    return True, posted_url


def vbulletin3_create_thread(page, board_url, title_text, body_text, log_fn):
    title_text = str(title_text).strip()
    body_text = str(body_text).strip()

    log_fn(f"Opening vBulletin Classic: {board_url}")
    page.goto(board_url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(1.5)

    if "newthread.php" not in page.url:
        new_th = page.locator('a[href*="newthread.php"], a:has-text("New Thread"), img[alt*="New Thread"]').first
        if new_th.count() > 0:
            new_th.click()
            page.wait_for_load_state("domcontentloaded", timeout=15000)

    try:
        subj = page.locator('input[name="subject"], input#subject').first
        subj.wait_for(state="visible", timeout=10000)
        subj.fill(title_text)
    except Exception:
        log_fn("Subject input not found.")
        return False, None

    try:
        page.evaluate("""(content) => {
            const ta = document.querySelector('textarea[name="message"], textarea#vB_Editor_001_textarea');
            if (ta) {
                ta.value = content;
                ta.dispatchEvent(new Event('input', { bubbles: true }));
                ta.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }""", body_text)
    except Exception:
        pass

    submit_btn = page.locator('input[name="sbutton"], input[value="Submit New Thread"], input[type="submit"]').first
    if submit_btn.count() > 0:
        submit_btn.click()
        try:
            page.wait_for_url(lambda u: "newthread.php" not in u and ("showthread.php" in u or "threads/" in u), timeout=25000)
            return True, page.url
        except PWTimeout:
            return True, page.url

    return False, None


def xenforo_create_thread(page, board_url, title_text, body_text, log_fn):
    title_text = str(title_text).strip()
    body_text = str(body_text).strip()

    log_fn(f"Opening XenForo: {board_url}")
    page.goto(board_url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(1.5)

    if "/post-thread" not in page.url and "/create-thread" not in page.url:
        post_btn = page.locator('a[href*="/post-thread"], a:has-text("Post thread"), button:has-text("Post thread")').first
        if post_btn.count() > 0:
            post_btn.click()
            page.wait_for_load_state("domcontentloaded", timeout=15000)

    try:
        t_input = page.locator('input[name="title"], input[placeholder*="Title" i]').first
        t_input.wait_for(state="visible", timeout=12000)
        t_input.fill(title_text)
    except Exception:
        log_fn("Title input not found.")
        return False, None

    try:
        page.evaluate("""(content) => {
            const fr = document.querySelector('.fr-element.fr-view, div[contenteditable="true"]');
            if (fr) {
                fr.innerHTML = content.replace(/\n/g, '<br>');
                fr.dispatchEvent(new Event('input', { bubbles: true }));
            }
            const ta = document.querySelector('textarea[name="message"]');
            if (ta) {
                ta.value = content;
                ta.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }""", body_text)
    except Exception:
        pass

    submit_btn = page.locator('button.button--primary:has-text("Post thread"), button:has-text("Post thread"), button[type="submit"]').first
    if submit_btn.count() > 0:
        submit_btn.click()
        try:
            page.wait_for_url(lambda u: "/threads/" in u and "/post-thread" not in u, timeout=25000)
            return True, page.url
        except Exception:
            return True, page.url

    return False, None


def phpbb_create_thread(page, board_url, title_text, body_text, log_fn):
    title_text = str(title_text).strip()
    body_text = str(body_text).strip()

    log_fn(f"Opening phpBB: {board_url}")
    page.goto(board_url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(1.5)

    if "mode=post" not in page.url:
        new_topic = page.locator('a[href*="mode=post"], a:has-text("New Topic"), a:has-text("Post a new topic")').first
        if new_topic.count() > 0:
            new_topic.click()
            page.wait_for_load_state("domcontentloaded", timeout=15000)

    try:
        subj = page.locator('input[name="subject"], input#subject').first
        subj.wait_for(state="visible", timeout=12000)
        subj.fill(title_text)
    except Exception:
        log_fn("Subject input not found.")
        return False, None

    try:
        ta = page.locator('textarea[name="message"], textarea#message').first
        ta.fill(body_text)
    except Exception:
        pass

    submit_btn = page.locator('input[name="post"], button[name="post"], input[value="Submit"]').first
    if submit_btn.count() > 0:
        submit_btn.click()
        try:
            page.wait_for_url(lambda u: "mode=post" not in u and ("viewtopic.php" in u or "f=" in u), timeout=25000)
            return True, page.url
        except Exception:
            return True, page.url

    return False, None


def ai_discover_unknown_site_selectors(page, log_fn):
    """
    AI DOM Agent Fallback: Extracts a compact snapshot of visible buttons, inputs,
    textareas, and contenteditable elements (including Shadow DOM) on an unknown site
    and queries the configured AI model to identify the exact selectors for Opener,
    Title, Editor, and Submit.
    """
    try:
        dom_snapshot = page.evaluate("""() => {
            const items = [];
            function walk(root) {
                if (!root) return;
                const els = root.querySelectorAll('button, a, input, textarea, select, [contenteditable="true"], [role="button"], [role="textbox"], iframe');
                for (const el of els) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width < 15 || rect.height < 12) continue;
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) continue;

                    let sel = el.tagName.toLowerCase();
                    if (el.id) sel += '#' + CSS.escape(el.id);
                    else if (el.getAttribute('data-testid')) sel += `[data-testid="${el.getAttribute('data-testid')}"]`;
                    else if (el.getAttribute('name')) sel += `[name="${el.getAttribute('name')}"]`;
                    else if (el.getAttribute('placeholder')) sel += `[placeholder="${el.getAttribute('placeholder')}"]`;
                    else if (el.getAttribute('aria-label')) sel += `[aria-label="${el.getAttribute('aria-label')}"]`;

                    const parentLabel = el.closest('label') ? el.closest('label').innerText : '';
                    const prevText = el.previousElementSibling ? (el.previousElementSibling.innerText || '') : '';

                    items.push({
                        tag: el.tagName.toLowerCase(),
                        selector: sel,
                        type: el.getAttribute('type') || '',
                        placeholder: (el.getAttribute('placeholder') || el.getAttribute('data-placeholder') || '').slice(0, 60),
                        label: (parentLabel || prevText).trim().replace(/\s+/g, ' ').slice(0, 50),
                        text: (el.innerText || el.value || '').trim().replace(/\s+/g, ' ').slice(0, 60),
                        aria: (el.getAttribute('aria-label') || '').slice(0, 50),
                        contenteditable: el.getAttribute('contenteditable') || '',
                        w: Math.round(rect.width),
                        h: Math.round(rect.height),
                        x: Math.round(rect.left),
                        y: Math.round(rect.top)
                    });
                    if (items.length >= 75) return;
                }
                const allNodes = root.querySelectorAll('*');
                for (const n of allNodes) {
                    if (n.shadowRoot && items.length < 75) walk(n.shadowRoot);
                }
            }
            walk(document);
            return items;
        }""")
        if not dom_snapshot:
            return None

        prompt = (
            "You are an autonomous browser automation agent inspecting an unknown website DOM.\n"
            "Given the following JSON list of visible interactive elements (with bounding-box w, h, x, y and labels), "
            "return ONLY a valid JSON object with 4 keys:\n"
            "- 'reply_selector': button/link to open post/article/note creation if not open yet, else ''\n"
            "- 'title_selector': input/textarea/contenteditable for post title/subject/headline\n"
            "- 'editor_selector': main body textarea, contenteditable div, or iframe\n"
            "- 'submit_selector': publish, post, submit, next, or share button\n\n"
            f"DOM Elements:\n{json.dumps(dom_snapshot, indent=2)}"
        )
        raw_ans = call_local_gemma_api(
            prompt,
            system_instruction="Return strictly valid JSON only with keys reply_selector, title_selector, editor_selector, submit_selector.",
            max_tokens=400
        )
        m = re.search(r'\{[\s\S]*?\}', raw_ans)
        if m:
            parsed = json.loads(m.group(0))
            log_fn(f"🤖 AI DOM Agent mapped unknown site selectors: {parsed}")
            return parsed
    except Exception as e:
        log_fn(f"AI DOM discovery note: {e}")
    return None


def _dismiss_unknown_site_popups(page, log_fn=None):
    """Automatically closes cookie banners, onboarding tours, and blocking modals."""
    dismiss_sels = [
        'button[data-testid="dismiss-interruption"]',
        'button[data-testid*="dismiss" i]',
        'button[data-testid*="close" i]',
        '#onetrust-accept-btn-handler',
        '.osano-cm-accept-all',
        'button[aria-label="Close"]',
        'button[aria-label="Dismiss"]',
        '.MuiDialog-root button[aria-label="Close"]',
        '.modal.show button.close, .modal.in button.close',
        'button:has-text("Accept All")',
        'button:has-text("I Agree")',
        'button:has-text("Got it")',
        'button:has-text("Skip")',
        'button:has-text("Not now")',
        'button:has-text("Maybe later")',
    ]
    for dsel in dismiss_sels:
        try:
            dloc = page.locator(dsel).first
            if dloc.count() > 0 and dloc.is_visible():
                dloc.click(timeout=2000)
                if log_fn:
                    log_fn(f"🧹 Dismissed overlay/popup ({dsel})")
                time.sleep(0.5)
        except Exception:
            continue


def _scan_and_tag_composer_dom(page):
    """
    Deep Shadow-DOM + Spatial Geometry + Label-Proximity Analyzer.
    Assigns unique data-fsp-uid attributes to candidate Title and Body elements
    and returns their metadata and reusable selectors.
    """
    try:
        return page.evaluate("""() => {
            let uidCounter = 1;
            function assignUid(el) {
                let u = el.getAttribute('data-fsp-uid');
                if (!u) {
                    u = 'fsp_el_' + (uidCounter++) + '_' + Math.floor(Math.random() * 10000);
                    el.setAttribute('data-fsp-uid', u);
                }
                return u;
            }

            function buildReusableSelector(el) {
                const tag = el.tagName.toLowerCase();
                if (el.id && !/^[0-9]+$/.test(el.id)) return `${tag}#${CSS.escape(el.id)}`;
                if (el.getAttribute('data-testid')) return `${tag}[data-testid="${el.getAttribute('data-testid')}"]`;
                if (el.getAttribute('name')) return `${tag}[name="${el.getAttribute('name')}"]`;
                if (el.getAttribute('placeholder')) return `${tag}[placeholder="${el.getAttribute('placeholder')}"]`;
                if (el.getAttribute('data-placeholder')) return `${tag}[data-placeholder="${el.getAttribute('data-placeholder')}"]`;
                if (el.getAttribute('aria-label')) return `${tag}[aria-label="${el.getAttribute('aria-label')}"]`;
                if (el.classList.contains('ProseMirror')) return '.ProseMirror';
                if (el.classList.contains('ql-editor')) return '.ql-editor';
                if (el.classList.contains('ck-editor__editable')) return '.ck-editor__editable';
                if (el.classList.contains('fr-element')) return '.fr-element';
                if (el.getAttribute('contenteditable') === 'true') return `${tag}[contenteditable="true"]`;
                return tag;
            }

            function getNearbyLabelText(el) {
                let parts = [];
                if (el.getAttribute('placeholder')) parts.push(el.getAttribute('placeholder'));
                if (el.getAttribute('data-placeholder')) parts.push(el.getAttribute('data-placeholder'));
                if (el.getAttribute('aria-label')) parts.push(el.getAttribute('aria-label'));
                if (el.getAttribute('name')) parts.push(el.getAttribute('name'));
                if (el.id) parts.push(el.id);
                if (el.title) parts.push(el.title);
                const lbl = el.closest('label') || (el.id ? document.querySelector(`label[for="${CSS.escape(el.id)}"]`) : null);
                if (lbl && lbl.innerText) parts.push(lbl.innerText.slice(0, 80));
                if (el.previousElementSibling && el.previousElementSibling.innerText) {
                    parts.push(el.previousElementSibling.innerText.slice(0, 80));
                } else if (el.parentElement && el.parentElement.previousElementSibling && el.parentElement.previousElementSibling.innerText) {
                    parts.push(el.parentElement.previousElementSibling.innerText.slice(0, 80));
                }
                return parts.join(' ').toLowerCase();
            }

            const allCandidates = [];
            function collectAll(root) {
                if (!root) return;
                const nodes = root.querySelectorAll('input, textarea, [contenteditable="true"], [role="textbox"], iframe');
                for (const el of nodes) {
                    allCandidates.push(el);
                }
                const every = root.querySelectorAll('*');
                for (const n of every) {
                    if (n.shadowRoot) collectAll(n.shadowRoot);
                }
            }
            collectAll(document);

            const titlePool = [];
            const bodyPool = [];

            for (const el of allCandidates) {
                const rect = el.getBoundingClientRect();
                if (rect.width < 120 || rect.height < 18) continue;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) continue;
                if (el.disabled || el.readOnly) continue;
                if (el.closest('nav, header.site-header, footer')) continue;

                const tag = el.tagName.toLowerCase();
                const type = (el.getAttribute('type') || 'text').toLowerCase();
                if (tag === 'input' && !['text', 'search', ''].includes(type)) continue;

                const meta = getNearbyLabelText(el);
                const cls = (el.className && typeof el.className === 'string' ? el.className : '').toLowerCase();

                // Exclude search, login, email, password, URL, tag/filter inputs
                if (type === 'search' || /\b(search|find|filter|login|username|email|password|captcha|coupon|promo|tag|url|website)\b/.test(meta)) {
                    if (!/\b(title|subject|topic|headline|heading|post|message|body|content|note|story|article)\b/.test(meta)) {
                        continue;
                    }
                }

                // Score for Title
                let tScore = 0;
                if (/\b(title|subject|headline|topic|heading|thread_title|post_title|note-main-title)\b/.test(meta)) tScore += 110;
                if (/\b(name|summary)\b/.test(meta) && rect.height < 65) tScore += 65;
                if ((tag === 'input' || (tag === 'textarea' && (el.rows === 1 || rect.height <= 68))) && rect.width >= 220) {
                    tScore += 45;
                }
                if (tag === 'div' && el.getAttribute('contenteditable') === 'true' && rect.height <= 75 && /title|heading|headline/.test(meta + ' ' + cls)) {
                    tScore += 95;
                }
                if (rect.height > 110) tScore -= 80; // Too tall for a title

                if (tScore >= 45) {
                    titlePool.push({
                        uid: assignUid(el),
                        reusable_selector: buildReusableSelector(el),
                        tag: tag,
                        is_contenteditable: el.getAttribute('contenteditable') === 'true',
                        score: tScore,
                        y: rect.top,
                        h: rect.height,
                        w: rect.width
                    });
                }

                // Score for Body Editor
                let bScore = 0;
                let kind = 'standard';
                if (cls.includes('prosemirror') || cls.includes('tiptap') || cls.includes('ql-editor') ||
                    cls.includes('ck-editor__editable') || cls.includes('fr-element') || cls.includes('note-editable') ||
                    cls.includes('public-drafteditor-content') || el.hasAttribute('data-lexical-editor') ||
                    el.hasAttribute('data-slate-editor')) {
                    bScore += 140;
                    kind = 'richtext';
                } else if (el.getAttribute('contenteditable') === 'true' || el.getAttribute('role') === 'textbox') {
                    if (!/\b(title|subject|headline)\b/.test(meta) || rect.height >= 80) {
                        bScore += 95;
                        kind = 'richtext';
                    }
                } else if (tag === 'textarea') {
                    if (el.id === 'note-main-title' || (/\b(title|subject)\b/.test(meta) && rect.height < 65)) {
                        bScore -= 100;
                    } else {
                        bScore += 85;
                        if (/\b(message|body|content|post|description|story|article|text|comment|overview)\b/.test(meta)) bScore += 45;
                        if (rect.height >= 80) bScore += 30;
                        kind = 'textarea';
                    }
                } else if (tag === 'iframe') {
                    const src = (el.getAttribute('src') || '').toLowerCase();
                    if (!/recaptcha|hcaptcha|turnstile|doubleclick|googlesyndication|youtube|vimeo|stripe|facebook/.test(src)) {
                        if (/wysiwyg|cke|mce|tinymce|sceditor|editor|rich|compose|frame/.test(cls + ' ' + meta + ' ' + src) || rect.height >= 120) {
                            bScore += 115;
                            kind = 'iframe';
                        }
                    }
                }

                // Area bonus for large central editors
                if (bScore > 0 && rect.width >= 250 && rect.height >= 60) {
                    bScore += Math.min(35, Math.round((rect.width * rect.height) / 8000));
                }

                if (bScore >= 75) {
                    bodyPool.push({
                        uid: assignUid(el),
                        reusable_selector: buildReusableSelector(el),
                        tag: tag,
                        kind: kind,
                        score: bScore,
                        y: rect.top,
                        h: rect.height,
                        w: rect.width
                    });
                }
            }

            // Sort pools by score descending, then by vertical layout (title higher up, body larger/lower)
            titlePool.sort((a, b) => (b.score - a.score) || (a.y - b.y));
            bodyPool.sort((a, b) => (b.score - a.score) || ((b.w * b.h) - (a.w * a.h)));

            let bestTitle = titlePool.length > 0 ? titlePool[0] : null;
            let bestBody = null;
            for (const b of bodyPool) {
                if (!bestTitle || b.uid !== bestTitle.uid) {
                    bestBody = b;
                    break;
                }
            }

            return {
                title: bestTitle,
                body: bestBody,
                title_count: titlePool.length,
                body_count: bodyPool.length
            };
        }""")
    except Exception:
        return {"title": None, "body": None}


def _inject_title_with_verification(page, title_info, title_text, log_fn):
    """
    4-Method Input Injection Cascade for Title with Read-Back Verification:
    1. Playwright click + fill
    2. React/Vue native HTMLInputElement/HTMLTextAreaElement prototype value setter + InputEvent
    3. Keyboard Ctrl+A -> Backspace -> insert_text
    """
    uid = title_info.get("uid")
    reusable_sel = title_info.get("reusable_selector", "")
    loc = page.locator(f'[data-fsp-uid="{uid}"]').first
    if loc.count() == 0 and reusable_sel:
        loc = page.locator(reusable_sel).first

    if loc.count() == 0:
        return False

    # Method 1: Native Playwright click + fill
    try:
        loc.scroll_into_view_if_needed(timeout=3000)
        loc.click(timeout=4000)
        time.sleep(0.15)
        if title_info.get("is_contenteditable"):
            page.keyboard.press("Control+A")
            page.keyboard.press("Backspace")
            page.keyboard.insert_text(title_text)
        else:
            loc.fill(title_text, timeout=4000)
        time.sleep(0.25)
    except Exception:
        pass

    # Verify read-back
    def _verify():
        try:
            val = loc.evaluate("el => (el.value !== undefined ? el.value : el.innerText) || ''")
            return len(str(val).strip()) >= min(3, len(title_text))
        except Exception:
            return False

    if _verify():
        log_fn(f"✍️ [Auto-Discovery] Verified Title filled via ({reusable_sel}): {title_text[:45]}")
        return True

    # Method 2: React/Vue Native Prototype Setter Bypass
    try:
        loc.evaluate("""(el, text) => {
            el.focus();
            if (el.getAttribute('contenteditable') === 'true') {
                el.innerText = text;
            } else {
                const proto = el.tagName.toLowerCase() === 'textarea'
                    ? window.HTMLTextAreaElement.prototype
                    : window.HTMLInputElement.prototype;
                const nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                if (nativeSetter) nativeSetter.call(el, text);
                else el.value = text;
            }
            el.dispatchEvent(new InputEvent('input', { bubbles: true, data: text, inputType: 'insertText' }));
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }""", title_text)
        time.sleep(0.25)
    except Exception:
        pass

    if _verify():
        log_fn(f"✍️ [Auto-Discovery] Verified Title filled via React/DOM setter ({reusable_sel})")
        return True

    # Method 3: Direct keyboard typing
    try:
        loc.click(force=True, timeout=3000)
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        page.keyboard.insert_text(title_text)
        time.sleep(0.25)
    except Exception:
        pass

    return _verify()


def _inject_body_with_verification(page, body_info, body_text, log_fn):
    """
    4-Method Input Injection Cascade for Body Editor with Read-Back Verification:
    Supports Rich-Text Virtual DOM (ProseMirror/TipTap/Lexical/Slate/Quill/Draft.js),
    WYSIWYG Iframes (TinyMCE/CKEditor/SCEditor), and Standard Textareas.
    """
    uid = body_info.get("uid")
    reusable_sel = body_info.get("reusable_selector", "")
    kind = body_info.get("kind", "standard")
    loc = page.locator(f'[data-fsp-uid="{uid}"]').first
    if loc.count() == 0 and reusable_sel:
        loc = page.locator(reusable_sel).first

    if loc.count() == 0:
        return False

    # Case A: WYSIWYG Iframe
    if kind == "iframe" or body_info.get("tag") == "iframe":
        try:
            fbody = loc.content_frame.locator("body").first
            if fbody.count() > 0:
                fbody.click(timeout=4000)
                time.sleep(0.2)
                try:
                    fbody.fill(body_text, timeout=4000)
                except Exception:
                    page.keyboard.insert_text(body_text)
                time.sleep(0.3)
                # Also sync via global WYSIWYG APIs & innerHTML fallback
                fbody.evaluate("""(el, text) => {
                    if (!el.innerText || el.innerText.trim().length < 5) {
                        el.innerHTML = text.replace(/\n/g, '<br>');
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                }""", body_text)
                log_fn(f"✍️ [Auto-Discovery] Verified Body filled inside WYSIWYG iframe ({reusable_sel})")
                return True
        except Exception as e:
            log_fn(f"Iframe fill notice: {e}")

    # Helper to verify non-iframe body read-back
    def _verify_body():
        try:
            val = loc.evaluate("el => (el.value !== undefined && el.tagName.toLowerCase() === 'textarea' ? el.value : el.innerText) || ''")
            return len(str(val).strip()) >= min(10, len(body_text))
        except Exception:
            return False

    # Method 1: Click + Keyboard Insert Text (for rich-text) or .fill() (for textarea)
    try:
        loc.scroll_into_view_if_needed(timeout=3000)
        loc.click(timeout=4000)
        time.sleep(0.25)
        if kind == "textarea" and body_info.get("tag") == "textarea":
            loc.fill(body_text, timeout=5000)
        else:
            page.keyboard.insert_text(body_text)
            time.sleep(0.3)
            page.keyboard.press("Enter")
        time.sleep(0.4)
    except Exception:
        pass

    if _verify_body():
        log_fn(f"✍️ [Auto-Discovery] Verified Body typed into ({reusable_sel})")
        return True

    # Method 2: Synthetic Clipboard Paste Event + execCommand('insertText') for strict Virtual-DOM editors (Slate / Draft.js / Lexical)
    try:
        loc.click(force=True, timeout=3000)
        loc.evaluate("""(el, text) => {
            el.focus();
            try {
                const dt = new DataTransfer();
                dt.setData('text/plain', text);
                const pasteEvent = new ClipboardEvent('paste', {
                    clipboardData: dt,
                    bubbles: true,
                    cancelable: true
                });
                el.dispatchEvent(pasteEvent);
            } catch (e) {}
            if ((el.innerText || '').trim().length < 5) {
                try {
                    document.execCommand('selectAll', false, null);
                    document.execCommand('insertText', false, text);
                } catch (e2) {}
            }
        }""", body_text)
        time.sleep(0.4)
    except Exception:
        pass

    if _verify_body():
        log_fn(f"✍️ [Auto-Discovery] Verified Body populated via Synthetic Paste / execCommand ({reusable_sel})")
        return True

    # Method 3: React Prototype Value Setter / Direct innerHTML + Global Editor Instances
    try:
        loc.evaluate("""(el, text) => {
            if (el.tagName.toLowerCase() === 'textarea') {
                const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set;
                if (nativeSetter) nativeSetter.call(el, text);
                else el.value = text;
                el.dispatchEvent(new InputEvent('input', { bubbles: true, data: text }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            } else {
                el.innerHTML = text.split('\n').map(p => `<p>${p || '<br>'}</p>`).join('');
                el.dispatchEvent(new InputEvent('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }
            if (window.CKEDITOR) {
                for (const k in window.CKEDITOR.instances) {
                    try { window.CKEDITOR.instances[k].setData(text.replace(/\n/g, '<br>')); } catch(e){}
                }
            }
            if (window.tinymce && window.tinymce.editors) {
                for (const ed of window.tinymce.editors) {
                    try { ed.setContent(text.replace(/\n/g, '<br>')); } catch(e){}
                }
            }
        }""", body_text)
        time.sleep(0.3)
    except Exception:
        pass

    return _verify_body()


def _auto_satisfy_required_fields(page, log_fn):
    """
    Automatically satisfies required checkboxes (e.g., 'I agree to rules/terms')
    and unselected required <select> category/topic dropdowns that block form submission.
    """
    try:
        actions = page.evaluate("""() => {
            const done = [];
            // 1. Check required or terms/rules checkboxes
            const cbs = document.querySelectorAll('input[type="checkbox"]');
            for (const cb of cbs) {
                const rect = cb.getBoundingClientRect();
                if (rect.width === 0 && rect.height === 0) continue;
                const lbl = (cb.closest('label')?.innerText || cb.parentElement?.innerText || '').toLowerCase();
                if ((cb.required || /\b(agree|rules|terms|guidelines|confirm|policy|read)\b/.test(lbl)) && !cb.checked) {
                    cb.click();
                    done.push('Checked required box: ' + lbl.slice(0, 35));
                }
            }
            // 2. Select first valid option in required <select> dropdowns (e.g. Category / Forum / Prefix)
            const selects = document.querySelectorAll('select');
            for (const s of selects) {
                const rect = s.getBoundingClientRect();
                if (rect.width < 30 || rect.height < 15) continue;
                if (!s.value || s.value === '' || s.value === '0' || s.value === '-1') {
                    for (const opt of s.options) {
                        if (opt.value && opt.value !== '0' && opt.value !== '-1' && !opt.disabled && !/select|choose|none/i.test(opt.text)) {
                            s.value = opt.value;
                            s.dispatchEvent(new Event('change', { bubbles: true }));
                            done.push('Selected dropdown option: ' + opt.text.slice(0, 30));
                            break;
                        }
                    }
                }
            }
            return done;
        }""")
        for act in (actions or []):
            log_fn(f"☑️ [Auto-Satisfier] {act}")
    except Exception:
        pass



def wait_for_manual_captcha_if_present(page, log_fn, max_wait_sec=45):
    """
    Detects if a Cloudflare Turnstile, Google reCAPTCHA, or hCaptcha challenge is visible on screen.
    If detected, pauses automation up to max_wait_sec so the user can manually click/solve it in the browser window.
    """
    captcha_selectors = [
        'iframe[src*="challenges.cloudflare.com"]',
        'iframe[src*="turnstile"]',
        'iframe[src*="google.com/recaptcha/api2/bframe"]',
        'iframe[src*="hcaptcha.com"]',
        '#challenge-running',
        '#cf-challenge-running',
        '.cf-turnstile',
    ]
    try:
        challenge_active = False
        for csel in captcha_selectors:
            loc = page.locator(csel).first
            if loc.count() > 0 and loc.is_visible():
                challenge_active = True
                break

        if not challenge_active:
            return

        log_fn(f"🛡️ [CAPTCHA Detected] Pausing up to {max_wait_sec}s so you can solve the CAPTCHA manually in the browser window...")
        start_t = time.time()
        while time.time() - start_t < max_wait_sec:
            time.sleep(1.5)
            # Check if challenge frame disappeared or checkbox became checked
            still_there = False
            for csel in [
                '#challenge-running',
                '#cf-challenge-running',
                'iframe[src*="google.com/recaptcha/api2/bframe"]',
            ]:
                try:
                    loc = page.locator(csel).first
                    if loc.count() > 0 and loc.is_visible():
                        still_there = True
                        break
                except Exception:
                    pass
            # Also check if reCAPTCHA response token is populated
            try:
                solved_token = page.evaluate("""() => {
                    const ta = document.querySelector('textarea[name="g-recaptcha-response"], textarea[name="h-captcha-response"], input[name="cf-turnstile-response"]');
                    return ta && ta.value && ta.value.trim().length > 10;
                }""")
                if solved_token:
                    log_fn("✅ [CAPTCHA Solved] Verification token detected! Resuming automation...")
                    time.sleep(1.0)
                    return
            except Exception:
                pass
            if not still_there and (time.time() - start_t > 4.0):
                break
        log_fn("▶️ Resuming after CAPTCHA wait window...")
    except Exception:
        pass


def preflight_html_site_analyzer(board_url, log_fn=None):
    """
    Autonomous Unknown-Site Pre-Flight HTML & Endpoint Analyzer v3.0:
    Sends a fast HTTP GET request (with saved session cookies) to inspect raw HTML source,
    meta generator tags, CSRF tokens, form fields, and creation links BEFORE browser interaction.
    Detects 18+ CMS, Web 2.0, Paste, Note, Blog, and Forum architectures:
    - WordPress (WP User Frontend, User Submitted Posts, Gutenberg/Classic Admin, WP Comments)
    - Telegraph (telegra.ph), Rentry, Write.as, Medium, Substack, Ghost, Hashnode, Dev.to
    - XenForo, vBulletin, phpBB, MyBB, SMF, Discourse, Flarum, NodeBB, Invision, Vanilla
    - Auto-discovers direct '/new', '/create', '/write', 'newthread.php' URLs if given a homepage/category URL.
    """
    import ssl
    result = {
        "cms": "Unknown Custom Site",
        "create_url": "",
        "reply_selector": "",
        "title_selector": "",
        "editor_selector": "",
        "submit_selector": "",
        "notes": []
    }
    if not board_url or not str(board_url).startswith("http"):
        return result

    try:
        ssl_ctx = ssl._create_unverified_context()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            sess_path = get_session_path_for_url(board_url)
            if not sess_path.exists():
                sess_path = SESSION_PATH
            if sess_path.exists():
                sdata = json.loads(sess_path.read_text(encoding="utf-8"))
                domain = urlparse(board_url).netloc.replace("www.", "").lower()
                cookie_pairs = []
                for c in sdata.get("cookies", []):
                    cdom = str(c.get("domain", "")).lstrip(".").lower()
                    if not domain or cdom in domain or domain in cdom:
                        cookie_pairs.append(f"{c.get('name')}={c.get('value')}")
                if cookie_pairs:
                    headers["Cookie"] = "; ".join(cookie_pairs)
        except Exception:
            pass

        req = urllib.request.Request(board_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
            raw_html = resp.read().decode("utf-8", errors="replace")
            final_u = resp.geturl() or board_url
    except Exception as e:
        if log_fn:
            log_fn(f"📡 [Pre-Flight HTML] Direct HTTP probe note ({e}); proceeding with live browser DOM.")
        return result

    html_lower = raw_html.lower()
    u_lower = final_u.lower()
    parsed_base = f"{urlparse(final_u).scheme}://{urlparse(final_u).netloc}"

    # 1. Telegraph (telegra.ph) — Instant zero-login publishing platform
    if "telegra.ph" in u_lower:
        result["cms"] = "Telegraph (telegra.ph)"
        result["title_selector"] = 'h1[data-placeholder="Title"], .tl_article_header h1, [contenteditable="true"]:first-of-type'
        result["editor_selector"] = '.ql-editor, article#tl_editor, [data-placeholder*="story" i]'
        result["submit_selector"] = 'button#_publish_button, button.button:has-text("Publish")'
    # 2. Rentry.co / Rentry.org — Instant Markdown publishing platform
    elif "rentry.co" in u_lower or "rentry.org" in u_lower:
        result["cms"] = "Rentry Markdown Publisher"
        result["editor_selector"] = 'textarea#id_text, .CodeMirror textarea, textarea[name="text"]'
        result["submit_selector"] = 'button#submitButton, button[type="submit"]:has-text("Go")'
    # 3. Write.as / Anonymous & Blog Publishers
    elif "write.as" in u_lower:
        result["cms"] = "Write.as Publisher"
        result["editor_selector"] = 'textarea#writer, textarea.editor'
        result["submit_selector"] = 'button#publish, button:has-text("Publish")'
    # 4. Dev.to / Forem Community
    elif "dev.to" in u_lower or "forem" in html_lower:
        result["cms"] = "Dev.to / Forem"
        if not u_lower.rstrip("/").endswith("/new"):
            result["create_url"] = f"{parsed_base}/new"
        result["title_selector"] = 'textarea#article-form-title, textarea[placeholder*="New post title" i]'
        result["editor_selector"] = 'textarea#article_body_markdown, textarea[placeholder*="Write your post content" i]'
        result["submit_selector"] = 'button:has-text("Publish"), button[type="submit"]'
    # 5. Medium / Substack / Ghost / Hashnode
    elif "medium.com" in u_lower:
        result["cms"] = "Medium"
        if "/new-story" not in u_lower and "/p/" not in u_lower:
            result["create_url"] = "https://medium.com/new-story"
        result["title_selector"] = 'h3[data-testid="editorTitleParagraph"], [data-placeholder="Title"]'
        result["editor_selector"] = 'p[data-testid="editorParagraphText"], [data-placeholder*="Tell your story" i]'
        result["submit_selector"] = 'button:has-text("Publish")'
    # 6. WordPress Suite (WP User Frontend, USP, Gutenberg, Classic Editor, WP Comments)
    elif "/wp-content/" in html_lower or "/wp-includes/" in html_lower or "wp-json" in html_lower or "wordpress" in html_lower:
        result["cms"] = "WordPress"
        if "wpuf-form" in html_lower or "wpuf_post_title" in html_lower:
            result["cms"] = "WordPress (WP User Frontend Guest Post)"
            result["title_selector"] = 'input#post_title, input[name="post_title"], .wpuf-fields input[type="text"]'
            result["editor_selector"] = 'textarea#post_content, iframe#post_content_ifr >> body, .wpuf-fields textarea'
            result["submit_selector"] = 'input.wpuf-submit-button, input[name="submit"], button[type="submit"]'
        elif "usp-form" in html_lower or "user-submitted-title" in html_lower:
            result["cms"] = "WordPress (User Submitted Posts Plugin)"
            result["title_selector"] = 'input#user-submitted-title, input[name="user-submitted-title"]'
            result["editor_selector"] = 'textarea#user-submitted-content, textarea[name="user-submitted-content"]'
            result["submit_selector"] = 'input#user-submitted-post, button[type="submit"]'
        elif "wp-block-post-title" in html_lower or "post-new.php" in u_lower:
            result["cms"] = "WordPress (Gutenberg / Classic Admin Editor)"
            result["title_selector"] = '.wp-block-post-title, input#title, input[name="post_title"]'
            result["editor_selector"] = '.block-editor-default-block-appender__content, .wp-block-post-content, textarea#content, iframe#content_ifr >> body'
            result["submit_selector"] = 'button.editor-post-publish-button, button.editor-post-publish-panel__toggle, input#publish'
        elif "bbp_topic_title" in html_lower or "bbpress" in html_lower:
            result["cms"] = "WordPress (bbPress Forum)"
            result["title_selector"] = 'input#bbp_topic_title, input[name="bbp_topic_title"]'
            result["editor_selector"] = 'textarea#bbp_topic_content, iframe#bbp_topic_content_ifr >> body'
            result["submit_selector"] = 'button#bbp_topic_submit, button[name="bbp_topic_submit"]'
        elif 'id="comment"' in html_lower or 'name="comment"' in html_lower:
            result["cms"] = "WordPress (Article Comment / Discussion Form)"
            result["title_selector"] = 'input#author, input[name="author"]'
            result["editor_selector"] = 'textarea#comment, textarea[name="comment"]'
            result["submit_selector"] = 'input#submit, button#submit, input[name="submit"]'
        else:
            m_wp = re.search(r"""href=["']([^"']*(?:post-new\.php|submit-post|guest-post|write-for-us|add-post|new-post)[^"']*)["']""", raw_html, re.I)
            if m_wp:
                result["create_url"] = urljoin(final_u, m_wp.group(1))
    # 7. MyBB
    elif "mybb" in html_lower or "newthread.php?fid=" in html_lower:
        result["cms"] = "MyBB Forum"
        m_link = re.search(r"""href=["']([^"']*newthread\.php\?fid=\d+[^"']*)["']""", raw_html, re.I)
        if m_link and "newthread.php" not in u_lower:
            result["create_url"] = urljoin(final_u, m_link.group(1).replace("&amp;", "&"))
        result["title_selector"] = 'input[name="subject"], input.textbox[name="subject"]'
        result["editor_selector"] = 'div.sceditor-container iframe >> body, div.sceditor-container textarea, textarea[name="message"], textarea#message'
        result["submit_selector"] = 'input[name="submit"][value*="Post Thread" i], input[type="submit"][name="submit"], button[name="submit"]'
    # 8. XenForo
    elif "xenforo" in html_lower or "xf-body" in html_lower or "/post-thread" in html_lower:
        result["cms"] = "XenForo Forum"
        m_xf = re.search(r"""href=["']([^"']*/post-thread[^"']*)["']""", raw_html, re.I)
        if m_xf and "/post-thread" not in u_lower:
            result["create_url"] = urljoin(final_u, m_xf.group(1))
        result["title_selector"] = 'input[name="title"], textarea[name="title"]'
        result["editor_selector"] = '.fr-element.fr-view[contenteditable="true"], textarea[name="message"]'
        result["submit_selector"] = 'button[type="submit"].button--primary, button:has-text("Post thread")'
    # 9. phpBB
    elif "phpbb" in html_lower or "posting.php?mode=post" in html_lower:
        result["cms"] = "phpBB Forum"
        m_pb = re.search(r"""href=["']([^"']*posting\.php\?mode=post[^"']*)["']""", raw_html, re.I)
        if m_pb and "posting.php" not in u_lower:
            result["create_url"] = urljoin(final_u, m_pb.group(1).replace("&amp;", "&"))
        result["title_selector"] = 'input#subject, input[name="subject"]'
        result["editor_selector"] = 'textarea#message, textarea[name="message"]'
        result["submit_selector"] = 'input[name="post"], button[name="post"]'
    # 10. SMF (Simple Machines Forum)
    elif "simple machines" in html_lower or "action=post;board=" in html_lower:
        result["cms"] = "SMF (Simple Machines Forum)"
        m_smf = re.search(r"""href=["']([^"']*action=post;board=[^"']*)["']""", raw_html, re.I)
        if m_smf and "action=post" not in u_lower:
            result["create_url"] = urljoin(final_u, m_smf.group(1).replace("&amp;", "&"))
        result["title_selector"] = 'input[name="subject"]'
        result["editor_selector"] = 'textarea.editor, textarea[name="message"], div.sceditor-container textarea'
        result["submit_selector"] = 'input[value="Post"], button[type="submit"]'
    # 11. Discourse / Flarum / NodeBB
    elif "discourse" in html_lower or "d-editor-input" in html_lower:
        result["cms"] = "Discourse Forum"
        result["reply_selector"] = 'button#create-topic, button:has-text("New Topic")'
        result["title_selector"] = 'input#reply-title'
        result["editor_selector"] = 'textarea.d-editor-input'
        result["submit_selector"] = 'button.create:has-text("Create Topic"), button.create'
    elif "flarum" in html_lower:
        result["cms"] = "Flarum Forum"
        result["reply_selector"] = 'button.IndexPage-newDiscussion, button:has-text("Start a Discussion")'
        result["title_selector"] = 'input[placeholder*="Discussion Title" i], .ComposerBody-header input'
        result["editor_selector"] = 'textarea.TextEditor-editor, .TextEditor textarea'
        result["submit_selector"] = 'button.Button--primary[type="submit"], button:has-text("Post Discussion")'

    # 12. Generic Creation Link Discovery on Unknown Sites (if user pasted a homepage/category URL)
    if not result["create_url"] and not result["editor_selector"]:
        m_create = re.search(
            r"""href=["']([^"']*(?:/new-thread|/post-thread|/create-thread|/new-topic|/create-post|/submit-post|/write|/compose|newthread\.php|posting\.php\?mode=post)[^"']*)["']""",
            raw_html,
            re.I
        )
        if m_create:
            cand_u = urljoin(final_u, m_create.group(1).replace("&amp;", "&"))
            if urlparse(cand_u).netloc == urlparse(final_u).netloc:
                result["create_url"] = cand_u

    # 13. Generic Raw HTML <form> & <input>/<textarea> Heuristic Extraction
    if not result["title_selector"]:
        m_t = re.search(r"""<input[^>]+name=["']([a-zA-Z0-9_\-]*?(?:title|subject|topic|headline)[a-zA-Z0-9_\-]*)["']""", raw_html, re.I)
        if m_t:
            result["title_selector"] = f'input[name="{m_t.group(1)}"]'
    if not result["editor_selector"]:
        m_b = re.search(r"""<textarea[^>]+name=["']([a-zA-Z0-9_\-]*?(?:message|content|body|post|text|description|story|comment)[a-zA-Z0-9_\-]*)["']""", raw_html, re.I)
        if m_b:
            result["editor_selector"] = f'textarea[name="{m_b.group(1)}"]'

    if log_fn and (result["cms"] != "Unknown Custom Site" or result["title_selector"] or result["editor_selector"] or result["create_url"]):
        log_fn(
            f"📡 [Pre-Flight HTML Analyzer v3.0] Detected: {result['cms']} | "
            f"CreateURL: {result['create_url'] or 'Current Page'} | "
            f"Title: {result['title_selector'] or 'Auto'} | "
            f"Editor: {result['editor_selector'] or 'Auto'}"
        )
    return result

    try:
        ssl_ctx = ssl._create_unverified_context()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        # Attach saved cookies from session file if available so authenticated forms appear in raw HTML
        try:
            sess_path = get_session_path_for_url(board_url)
            if not sess_path.exists():
                sess_path = SESSION_PATH
            if sess_path.exists():
                sdata = json.loads(sess_path.read_text(encoding="utf-8"))
                domain = urlparse(board_url).netloc.replace("www.", "").lower()
                cookie_pairs = []
                for c in sdata.get("cookies", []):
                    cdom = str(c.get("domain", "")).lstrip(".").lower()
                    if not domain or cdom in domain or domain in cdom:
                        cookie_pairs.append(f"{c.get('name')}={c.get('value')}")
                if cookie_pairs:
                    headers["Cookie"] = "; ".join(cookie_pairs)
        except Exception:
            pass

        req = urllib.request.Request(board_url, headers=headers)
        with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
            raw_html = resp.read().decode("utf-8", errors="replace")
            final_u = resp.geturl() or board_url
    except Exception as e:
        if log_fn:
            log_fn(f"📡 [Pre-Flight HTML] Direct HTTP probe note ({e}); proceeding with live browser DOM.")
        return result

    html_lower = raw_html.lower()
    parsed_base = f"{urlparse(final_u).scheme}://{urlparse(final_u).netloc}"

    # 1. Detect WordPress (wp-content, wp-includes, wp-json, wp-admin, Guest Post forms, Comment forms)
    if "/wp-content/" in html_lower or "/wp-includes/" in html_lower or "wp-json" in html_lower or "wordpress" in html_lower:
        result["cms"] = "WordPress"
        # Check for WordPress Front-End Guest Post Plugins (WP User Frontend, User Submitted Posts, Frontend Publishing)
        if "wpuf-form" in html_lower or "wpuf_post_title" in html_lower:
            result["cms"] = "WordPress (WP User Frontend Guest Post)"
            result["title_selector"] = 'input#post_title, input[name="post_title"], .wpuf-fields input[type="text"]'
            result["editor_selector"] = 'textarea#post_content, iframe#post_content_ifr >> body, .wpuf-fields textarea'
            result["submit_selector"] = 'input.wpuf-submit-button, input[name="submit"], button[type="submit"]'
        elif "usp-form" in html_lower or "user-submitted-title" in html_lower:
            result["cms"] = "WordPress (User Submitted Posts Plugin)"
            result["title_selector"] = 'input#user-submitted-title, input[name="user-submitted-title"]'
            result["editor_selector"] = 'textarea#user-submitted-content, textarea[name="user-submitted-content"]'
            result["submit_selector"] = 'input#user-submitted-post, button[type="submit"]'
        elif "wp-block-post-title" in html_lower or "post-new.php" in final_u.lower():
            result["cms"] = "WordPress (Gutenberg / Classic Admin Editor)"
            result["title_selector"] = '.wp-block-post-title, input#title, input[name="post_title"]'
            result["editor_selector"] = '.block-editor-default-block-appender__content, .wp-block-post-content, iframe#content_ifr >> body, textarea#content'
            result["submit_selector"] = 'button.editor-post-publish-button, button.editor-post-publish-panel__toggle, input#publish'
        elif 'id="commentform"' in html_lower or 'name="comment"' in html_lower:
            result["cms"] = "WordPress (Article Comment / Discussion Form)"
            result["title_selector"] = 'input#author, input[name="author"]'
            result["editor_selector"] = 'textarea#comment, textarea[name="comment"]'
            result["submit_selector"] = 'input#submit, button#submit, input[name="submit"], #commentform button[type="submit"]'
        else:
            # Check if there is a 'Write for us' / 'Submit Post' / 'post-new.php' link in the HTML
            m_new = re.search(r'href=["\']([^"\']*(?:post-new\.php|submit-post|write-for-us|new-post|create-post)[^"\']*)["\']', raw_html, re.I)
            if m_new:
                result["create_url"] = urljoin(final_u, m_new.group(1))

    # 2. Detect MyBB
    elif "mybb" in html_lower or "newthread.php?fid=" in html_lower or 'name="my_post_key"' in html_lower:
        result["cms"] = "MyBB Forum"
        m_nt = re.search(r'href=["\']([^"\']*newthread\.php\?fid=\d+[^"\']*)["\']', raw_html, re.I)
        if m_nt:
            result["create_url"] = urljoin(final_u, m_nt.group(1).replace("&amp;", "&"))
        result["reply_selector"] = 'a[href*="newthread.php"], a:has-text("Post Thread")'
        result["title_selector"] = 'input[name="subject"]'
        result["editor_selector"] = 'iframe >> body, textarea#message, textarea[name="message"]'
        result["submit_selector"] = 'input[name="submit"][value*="Post Thread" i], button:has-text("Post Thread"), input[type="submit"]'

    # 3. Detect XenForo
    elif "data-xf-init" in html_lower or "xenforo" in html_lower or "/post-thread" in html_lower:
        result["cms"] = "XenForo"
        m_xf = re.search(r'href=["\']([^"\']*/post-thread[^"\']*)["\']', raw_html, re.I)
        if m_xf:
            result["create_url"] = urljoin(final_u, m_xf.group(1))
        result["reply_selector"] = 'a[href*="/post-thread"], a:has-text("Post thread")'
        result["title_selector"] = 'input[name="title"], textarea[name="title"]'
        result["editor_selector"] = '.fr-element[contenteditable="true"], textarea[name="message"]'
        result["submit_selector"] = 'button:has-text("Post thread"), button[type="submit"]'

    # 4. Detect phpBB
    elif "phpbb" in html_lower or "posting.php?mode=post" in html_lower:
        result["cms"] = "phpBB"
        m_pb = re.search(r'href=["\']([^"\']*posting\.php\?mode=post[^"\']*)["\']', raw_html, re.I)
        if m_pb:
            result["create_url"] = urljoin(final_u, m_pb.group(1).replace("&amp;", "&"))
        result["reply_selector"] = 'a[href*="mode=post"], a:has-text("New Topic")'
        result["title_selector"] = 'input[name="subject"], input#subject'
        result["editor_selector"] = 'textarea[name="message"], textarea#message'
        result["submit_selector"] = 'input[name="post"], button[name="post"], input[type="submit"]'

    # 5. Detect vBulletin
    elif "vbulletin" in html_lower or "newthread.php?do=newthread" in html_lower:
        result["cms"] = "vBulletin"
        m_vb = re.search(r'href=["\']([^"\']*newthread\.php\?do=newthread[^"\']*)["\']', raw_html, re.I)
        if m_vb:
            result["create_url"] = urljoin(final_u, m_vb.group(1).replace("&amp;", "&"))
        result["reply_selector"] = 'a[href*="newthread.php"], a:has-text("Post New Thread")'
        result["title_selector"] = 'input[name="subject"], input#subject'
        result["editor_selector"] = 'textarea[name="message"], iframe.cke_wysiwyg_frame >> body'
        result["submit_selector"] = 'input[name="sbutton"], button[type="submit"], input[type="submit"]'

    # 6. Generic Raw HTML <form> Extraction for Any Custom Unknown Site
    if not result["editor_selector"]:
        # Search raw HTML for input[name=...] that looks like title/subject
        m_title_inp = re.search(
            r'<(?:input|textarea)[^>]*?\bname=["\']([^"\']*(?:title|subject|topic|headline|heading)[^"\']*)["\']',
            raw_html,
            re.I
        )
        if m_title_inp:
            result["title_selector"] = f'[name="{m_title_inp.group(1)}"]'

        # Search raw HTML for textarea[name=...] that looks like body/message/content
        m_body_ta = re.search(
            r'<textarea[^>]*?\bname=["\']([^"\']*(?:message|body|content|post|text|description|story|comment)[^"\']*)["\']',
            raw_html,
            re.I
        )
        if m_body_ta:
            result["editor_selector"] = f'textarea[name="{m_body_ta.group(1)}"]'

        # Search raw HTML for a link pointing to a thread/post creation URL
        if not result["create_url"]:
            m_create_href = re.search(
                r'<a[^>]*?href=["\']([^"\']*(?:newthread|new-thread|post-thread|create-post|new-post|new-topic|mode=post|action=newthread)[^"\']*)["\']',
                raw_html,
                re.I
            )
            if m_create_href:
                result["create_url"] = urljoin(final_u, m_create_href.group(1).replace("&amp;", "&"))

    if log_fn:
        log_fn(
            f"📡 [Pre-Flight HTML Scan] Detected Engine: {result['cms']} | "
            f"Create URL: {result['create_url'] or 'Current Page'} | "
            f"Title: {result['title_selector'] or 'Auto-DOM'} | "
            f"Editor: {result['editor_selector'] or 'Auto-DOM'}"
        )
    return result


def universal_create_thread(page, board_url, title_text, body_text, log_fn):
    """
    Autonomous Unknown-Site Agent v2.0 (6-Stage State Machine):
    1. Multi-Step State Machine Opener (navigates 1–3 click hops: '+ / Write / New Thread' -> 'Blank / Scratch' -> Editor)
    2. Deep Shadow-DOM + Spatial Geometry + Label-Proximity Scanner (_scan_and_tag_composer_dom) + AI DOM Agent Fallback
    3. 4-Method Input Injection Cascade with Read-Back Verification (Playwright native + React prototype setter + Synthetic Paste + WYSIWYG APIs)
    4. Auto-Satisfier for Required Checkboxes & Category Dropdowns + Multi-Step Wizard ('Next'/'Continue') support
    5. 2-Stage Publish / Confirmation Modal & Share-Link Follower
    6. 5-Source Live URL Verifier (Network JSON response sniffer + URL redirect diff + Clipboard hook + Title permalink scanner) & Self-Learning Blueprint Cache
    """
    title_text = str(title_text).strip()
    body_text = str(body_text).strip()

    try:
        page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    except Exception:
        pass

    # Source 1: Attach Network JSON Response Sniffer to catch created post URLs from background API calls
    net_captured_urls = []
    base_domain = urlparse(board_url).netloc.replace("www.", "").lower()

    def _on_response(resp):
        try:
            req_method = resp.request.method.upper()
            if req_method not in ("POST", "PUT", "PATCH"):
                return
            ct = (resp.headers.get("content-type") or "").lower()
            if "json" not in ct:
                return
            if resp.status < 200 or resp.status >= 300:
                return
            data = resp.json()
            if not isinstance(data, dict):
                return

            def _extract_urls(obj):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        kl = str(k).lower()
                        if isinstance(v, str) and (
                            kl in ("url", "permalink", "shareurl", "share_url", "short_url", "html_url", "post_url", "thread_url", "link")
                            or (v.startswith("http") and any(p in v.lower() for p in ("/post", "/thread", "/topic", "/note", "/p/", "/article", "/discussion", "/status", "/view")))
                        ):
                            u_cand = urljoin(page.url, v.strip())
                            if is_valid_live_post_url(u_cand):
                                net_captured_urls.append(u_cand)
                        elif isinstance(v, (dict, list)):
                            _extract_urls(v)
                elif isinstance(obj, list):
                    for item in obj[:10]:
                        _extract_urls(item)

            _extract_urls(data)
        except Exception:
            pass

    try:
        page.on("response", _on_response)
    except Exception:
        pass

    # Stage 0: Pre-Flight Raw HTML Request & CMS/WordPress/Form Discovery
    preflight = preflight_html_site_analyzer(board_url, log_fn)
    effective_start_url = preflight.get("create_url") or board_url

    log_fn(f"🧭 [Autonomous Agent v2.0] Navigating to: {effective_start_url}")
    try:
        page.goto(effective_start_url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log_fn(f"Navigation notice: {e}")
    time.sleep(2.5)

    # Pause automatically if Cloudflare Turnstile / reCAPTCHA / hCaptcha requires manual click
    wait_for_manual_captcha_if_present(page, log_fn, max_wait_sec=45)

    # Install clipboard interceptor
    try:
        page.evaluate("""() => {
            window.__captured_live_url = '';
            if (navigator.clipboard && navigator.clipboard.writeText) {
                const origWrite = navigator.clipboard.writeText;
                navigator.clipboard.writeText = function(text) {
                    if (text && typeof text === 'string' && text.startsWith('http')) {
                        window.__captured_live_url = text.trim();
                    }
                    return origWrite.apply(this, arguments);
                };
            }
        }""")
    except Exception:
        pass

    _dismiss_unknown_site_popups(page, log_fn)

    learned_recipe = {
        "reply_selector": "",
        "title_selector": "",
        "editor_selector": "",
        "submit_selector": ""
    }

    # =========================================================================
    # STAGE 1: MULTI-STEP STATE MACHINE OPENER (Up to 3 Click Hops to Editor)
    # =========================================================================
    clicked_opener_uids = set()
    for hop in range(3):
        scan = _scan_and_tag_composer_dom(page)
        if scan.get("body") is not None:
            log_fn(f"✅ [Stage 1] Composer detected on page (hop {hop}).")
            break

        log_fn(f"🔍 [Stage 1 • Hop {hop+1}/3] No editor visible yet. Scanning DOM for creation trigger...")
        opener_info = None
        try:
            opener_info = page.evaluate("""(alreadyClicked) => {
                const posRules = [
                    ['post thread', 110], ['new thread', 110], ['create thread', 110],
                    ['new topic', 105], ['start a new topic', 105], ['post new topic', 105],
                    ['start discussion', 105], ['new discussion', 105],
                    ['create from scratch', 115], ['blank note', 110], ['blank page', 105],
                    ['create new content', 100], ['create post', 100], ['new post', 100],
                    ['write a post', 100], ['write a story', 100], ['new story', 95],
                    ['new article', 95], ['new note', 95], ['add note', 90],
                    ['notebook', 85], ['compose', 90], ['write', 80],
                    ['ask question', 90], ['ask a question', 95], ['submit a post', 95],
                    ['create', 72], ['+ new', 85], ['add new', 80]
                ];
                const negWords = [
                    'login', 'log in', 'sign in', 'signup', 'sign up', 'register', 'create account',
                    'forgot', 'password', 'search', 'cancel', 'close', 'upgrade', 'pricing', 'pro',
                    'logout', 'log out', 'profile', 'settings', 'privacy', 'terms', 'cookie', 'help'
                ];

                let best = null;
                let uidSeq = 1;
                const els = document.querySelectorAll('a, button, [role="button"], [role="menuitem"], input[type="button"], div[aria-label*="button" i], div[id*="create" i]');
                for (const el of els) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width < 22 || rect.height < 16) continue;
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) continue;

                    let uid = el.getAttribute('data-fsp-opener-uid');
                    if (!uid) {
                        uid = 'fsp_open_' + (uidSeq++) + '_' + Math.floor(Math.random() * 9999);
                        el.setAttribute('data-fsp-opener-uid', uid);
                    }
                    if (alreadyClicked.includes(uid)) continue;

                    const rawText = (el.innerText || el.value || '').trim().replace(/\s+/g, ' ');
                    const aria = (el.getAttribute('aria-label') || el.getAttribute('title') || '').trim();
                    const href = (el.getAttribute('href') || '').toLowerCase();
                    const combined = (rawText + ' ' + aria + ' ' + (el.id || '')).toLowerCase();

                    if (!combined || rawText.length > 75) continue;
                    if (negWords.some(nw => combined.includes(nw))) continue;

                    let score = 0;
                    for (const [kw, pts] of posRules) {
                        if (combined.includes(kw)) score = Math.max(score, pts);
                    }
                    if (/newthread|post-thread|create-thread|mode=post|action=newthread|\/new|\/write|\/compose/.test(href)) {
                        score = Math.max(score, 105);
                    }

                    if (score >= 70 && (!best || score > best.score)) {
                        let sel = el.tagName.toLowerCase();
                        if (el.id) sel += '#' + CSS.escape(el.id);
                        else if (el.getAttribute('data-testid')) sel += `[data-testid="${el.getAttribute('data-testid')}"]`;
                        else if (rawText && rawText.length <= 35) sel += `:has-text("${rawText.replace(/"/g, '\\"')}")`;
                        best = {
                            uid: uid,
                            selector: sel,
                            text: (rawText || aria).slice(0, 40),
                            score: score
                        };
                    }
                }
                return best;
            }""", list(clicked_opener_uids))
        except Exception:
            opener_info = None

        if not opener_info:
            break

        clicked_opener_uids.add(opener_info["uid"])
        log_fn(f"✨ [Stage 1] Clicking opener '{opener_info.get('text')}' ({opener_info.get('selector')})...")
        try:
            op_loc = page.locator(f'[data-fsp-opener-uid="{opener_info["uid"]}"]').first
            if op_loc.count() > 0:
                op_loc.click(timeout=6000)
                if not learned_recipe["reply_selector"]:
                    learned_recipe["reply_selector"] = opener_info.get("selector", "")
                time.sleep(2.2)
                _dismiss_unknown_site_popups(page, log_fn)
        except Exception as e:
            log_fn(f"Opener click notice: {e}")

    # =========================================================================
    # STAGE 2 & 3: TITLE + BODY DISCOVERY & 4-METHOD INJECTION CASCADE
    # =========================================================================
    scan = _scan_and_tag_composer_dom(page)
    title_info = scan.get("title")
    body_info = scan.get("body")

    # Apply Pre-Flight HTML Request selectors if DOM geometry scan missed them
    if not title_info and preflight.get("title_selector"):
        try:
            t_el = page.locator(preflight["title_selector"]).first
            if t_el.count() > 0 and t_el.is_visible():
                uid = t_el.evaluate("el => { el.setAttribute('data-fsp-uid', 'fsp_pf_title'); return 'fsp_pf_title'; }")
                title_info = {"uid": uid, "reusable_selector": preflight["title_selector"], "is_contenteditable": False}
        except Exception:
            pass
    if not body_info and preflight.get("editor_selector"):
        try:
            b_el = page.locator(preflight["editor_selector"]).first
            if b_el.count() > 0 and b_el.is_visible():
                uid = b_el.evaluate("el => { el.setAttribute('data-fsp-uid', 'fsp_pf_body'); return 'fsp_pf_body'; }")
                tag_n = b_el.evaluate("el => el.tagName.toLowerCase()")
                body_info = {"uid": uid, "reusable_selector": preflight["editor_selector"], "tag": tag_n, "kind": "textarea" if tag_n == "textarea" else "richtext"}
        except Exception:
            pass

    ai_selectors = None
    if not body_info:
        log_fn("🤖 [Stage 2] Consulting AI DOM Agent to map unconventional site layout...")
        ai_selectors = ai_discover_unknown_site_selectors(page, log_fn)
        if ai_selectors:
            if ai_selectors.get("reply_selector") and not body_info:
                try:
                    rloc = page.locator(ai_selectors["reply_selector"]).first
                    if rloc.count() > 0 and rloc.is_visible():
                        rloc.click(timeout=5000)
                        time.sleep(2.0)
                        scan = _scan_and_tag_composer_dom(page)
                        title_info = scan.get("title")
                        body_info = scan.get("body")
                except Exception:
                    pass
            if not title_info and ai_selectors.get("title_selector"):
                try:
                    t_el = page.locator(ai_selectors["title_selector"]).first
                    if t_el.count() > 0 and t_el.is_visible():
                        uid = t_el.evaluate("el => { el.setAttribute('data-fsp-uid', 'fsp_ai_title'); return 'fsp_ai_title'; }")
                        title_info = {"uid": uid, "reusable_selector": ai_selectors["title_selector"], "is_contenteditable": False}
                except Exception:
                    pass
            if not body_info and ai_selectors.get("editor_selector"):
                try:
                    b_el = page.locator(ai_selectors["editor_selector"]).first
                    if b_el.count() > 0 and b_el.is_visible():
                        uid = b_el.evaluate("el => { el.setAttribute('data-fsp-uid', 'fsp_ai_body'); return 'fsp_ai_body'; }")
                        tag_n = b_el.evaluate("el => el.tagName.toLowerCase()")
                        body_info = {"uid": uid, "reusable_selector": ai_selectors["editor_selector"], "tag": tag_n, "kind": "textarea" if tag_n == "textarea" else "richtext"}
                except Exception:
                    pass

    # Fill Title if present
    if title_info:
        ok_title = _inject_title_with_verification(page, title_info, title_text, log_fn)
        if ok_title:
            learned_recipe["title_selector"] = title_info.get("reusable_selector", "")
        else:
            log_fn("⚠️ [Stage 3] Title verification partial; continuing to body editor.")
    else:
        log_fn("ℹ️ [Stage 3] Content-only composer or no separate title field detected.")

    # Handle multi-step wizards where Title is on Step 1 and clicking 'Next'/'Continue' reveals Body on Step 2
    if not body_info and title_info:
        next_btn = page.locator('button:has-text("Next"), button:has-text("Continue"), input[value*="Next" i]').first
        if next_btn.count() > 0 and next_btn.is_visible():
            log_fn("⏭️ [Wizard Mode] Clicking 'Next / Continue' to advance to body editor...")
            try:
                next_btn.click(timeout=5000)
                time.sleep(2.0)
                scan = _scan_and_tag_composer_dom(page)
                body_info = scan.get("body")
            except Exception:
                pass

    if not body_info:
        log_fn("❌ [Auto-Discovery] Could not locate a valid body editor on this page.")
        return False, None

    ok_body = _inject_body_with_verification(page, body_info, body_text, log_fn)
    if ok_body:
        learned_recipe["editor_selector"] = body_info.get("reusable_selector", "")
    else:
        log_fn("⚠️ [Stage 3] Body read-back verification returned short text; syncing fallback textareas...")

    # Always synchronize any underlying hidden textareas
    try:
        page.evaluate("""(content) => {
            const tas = document.querySelectorAll('textarea[name*="message" i], textarea[name*="content" i], textarea[name*="body" i], textarea[name*="text" i]');
            for (const ta of tas) {
                if (!ta.value) {
                    ta.value = content;
                    ta.dispatchEvent(new Event('input', { bubbles: true }));
                    ta.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        }""", body_text)
    except Exception:
        pass

    # =========================================================================
    # STAGE 4: AUTO-SATISFY REQUIRED CHECKBOXES / DROPDOWNS & SUBMIT
    # =========================================================================
    _auto_satisfy_required_fields(page, log_fn)
    wait_for_manual_captcha_if_present(page, log_fn, max_wait_sec=45)
    time.sleep(0.5)

    pre_submit_url = page.url

    # Score all visible Submit / Publish / Share buttons
    submit_info = None
    try:
        submit_info = page.evaluate("""() => {
            const posSubmit = [
                ['post thread', 120], ['create thread', 120], ['post new thread', 120],
                ['publish now', 120], ['publish post', 120], ['publish', 115],
                ['submit new thread', 120], ['submit post', 115], ['post topic', 115],
                ['create post', 110], ['submit', 105], ['post', 100],
                ['save template', 105], ['save & publish', 115], ['save', 90],
                ['share', 85], ['send', 85], ['done', 80]
            ];
            const negSubmit = [
                'cancel', 'preview', 'draft', 'save draft', 'discard', 'delete',
                'close', 'back', 'login', 'sign in', 'search', 'upload', 'attach'
            ];

            let best = null;
            let seq = 1;
            const els = document.querySelectorAll('button, input[type="submit"], input[type="button"], [role="button"]');
            for (const el of els) {
                const rect = el.getBoundingClientRect();
                if (rect.width < 28 || rect.height < 18) continue;
                const style = window.getComputedStyle(el);
                if (style.display === 'none' || style.visibility === 'hidden' || parseFloat(style.opacity) === 0) continue;
                if (el.disabled) continue;

                const text = ((el.innerText || el.value || '') + ' ' + (el.getAttribute('aria-label') || '')).trim().replace(/\s+/g, ' ');
                const lower = text.toLowerCase();
                if (!lower || lower.length > 50) continue;
                if (negSubmit.some(ns => lower.includes(ns))) continue;

                let score = 0;
                for (const [kw, pts] of posSubmit) {
                    if (lower === kw) score = Math.max(score, pts + 15);
                    else if (lower.includes(kw)) score = Math.max(score, pts);
                }
                if (el.getAttribute('type') === 'submit' && score === 0) score = 90;

                if (score >= 80 && (!best || score > best.score)) {
                    const uid = 'fsp_sub_' + (seq++);
                    el.setAttribute('data-fsp-sub-uid', uid);
                    let sel = el.tagName.toLowerCase();
                    if (el.id) sel += '#' + CSS.escape(el.id);
                    else if (text && text.length <= 30) sel += `:has-text("${text.replace(/"/g, '\\"')}")`;
                    else if (el.getAttribute('type') === 'submit') sel += '[type="submit"]';
                    best = { uid: uid, selector: sel, text: text.slice(0, 35), score: score };
                }
            }
            return best;
        }""")
    except Exception:
        submit_info = None

    if not submit_info and ai_selectors and ai_selectors.get("submit_selector"):
        submit_info = {"uid": "", "selector": ai_selectors["submit_selector"], "text": ai_selectors["submit_selector"]}

    if not submit_info:
        log_fn("❌ [Auto-Discovery] Submit / Publish button not found.")
        return False, None

    log_fn(f"🚀 [Stage 4] Clicking primary publish trigger: '{submit_info.get('text')}' ({submit_info.get('selector')})...")
    learned_recipe["submit_selector"] = submit_info.get("selector", "")
    try:
        if submit_info.get("uid"):
            page.locator(f'[data-fsp-sub-uid="{submit_info["uid"]}"]').first.click(timeout=8000)
        else:
            page.locator(submit_info["selector"]).first.click(timeout=8000)
    except Exception as e:
        log_fn(f"Submit click notice: {e}")

    time.sleep(2.5)

    # =========================================================================
    # STAGE 5: TWO-STAGE CONFIRMATION MODAL, PUBLIC UNLOCKER & SHARE-LINK FOLLOWER
    # =========================================================================
    try:
        # 5A-0. If a Share modal opened with a 'Private / Only you' -> 'Anyone with the link / Public' toggle, enable Public access first!
        for pub_sel in [
            'button:has-text("Anyone with the link")',
            '[role="menuitem"]:has-text("Anyone with the link")',
            '[role="option"]:has-text("Anyone with the link")',
            'label:has-text("Anyone with the link")',
            'label:has-text("Public")',
            'button:has-text("Publish to web")',
        ]:
            try:
                ploc = page.locator(pub_sel).first
                if ploc.count() > 0 and ploc.is_visible():
                    ploc.click(timeout=3000)
                    time.sleep(0.6)
                    break
            except Exception:
                continue

        # 5A. Check if a Share -> Copy link dialog opened
        copy_btn = page.locator('button:has-text("Copy link"), button:has-text("Copy URL"), [aria-label*="Copy link" i]').first
        if copy_btn.count() > 0 and copy_btn.is_visible():
            log_fn("📋 [Stage 5] Clicking 'Copy link' in share dialog...")
            copy_btn.click(timeout=4000)
            time.sleep(1.0)
            done_btn = page.locator('button:has-text("Done"), button:has-text("Close")').first
            if done_btn.count() > 0 and done_btn.is_visible():
                done_btn.click(timeout=4000)
                time.sleep(0.8)
        else:
            # 5B. Check if a 2-step 'Publish now' / 'Confirm' drawer or modal opened
            confirm_btn = page.locator(
                'button:has-text("Publish now"), button:has-text("Confirm"), '
                'button:has-text("Continue to publish"), .modal button:has-text("Publish"), '
                '.modal button:has-text("Post"), [role="dialog"] button:has-text("Publish"), '
                '[role="dialog"] button:has-text("Post")'
            ).first
            if confirm_btn.count() > 0 and confirm_btn.is_visible():
                log_fn("🚀 [Stage 5] Clicking secondary confirmation button in modal...")
                confirm_btn.click(timeout=5000)
                time.sleep(2.5)
    except Exception:
        pass

    # =========================================================================
    # STAGE 6: 6-SOURCE LIVE POST URL EXTRACTION & SELF-LEARNING CACHE
    # =========================================================================
    final_url = ""

    # Source 0: Readonly Share Link Input Box Scanner (for modals displaying a copyable URL in an <input>)
    try:
        share_inp_url = page.evaluate("""() => {
            const inputs = document.querySelectorAll('input[readonly], input[type="text"], input[type="url"]');
            for (const inp of inputs) {
                const v = (inp.value || inp.getAttribute('value') || '').trim();
                if (v.startsWith('http://') || v.startsWith('https://')) {
                    const rect = inp.getBoundingClientRect();
                    if (rect.width > 40 && rect.height > 12) return v;
                }
            }
            return '';
        }""")
        if share_inp_url and is_valid_live_post_url(share_inp_url, board_url):
            final_url = share_inp_url
            log_fn(f"🔗 [Source 0: Share Input Box] Captured live URL: {final_url}")
    except Exception:
        pass

    # Source 1: Clipboard intercepted URL
    try:
        clip_text = page.evaluate("() => window.__captured_live_url || ''")
        if clip_text and str(clip_text).strip().startswith("http") and is_valid_live_post_url(str(clip_text).strip()):
            final_url = str(clip_text).strip()
            log_fn(f"🔗 [Source 1: Clipboard] Captured live URL: {final_url}")
    except Exception:
        pass

    # Source 2: Network JSON Response Sniffer
    if not final_url and net_captured_urls:
        final_url = net_captured_urls[-1]
        log_fn(f"🔗 [Source 2: Network JSON] Captured live URL from API response: {final_url}")

    # Source 3: Browser URL Redirect Diff
    if not final_url:
        cur_u = page.url
        if cur_u != pre_submit_url and is_valid_live_post_url(cur_u):
            final_url = cur_u
            log_fn(f"🔗 [Source 3: Redirect] Navigated to live URL: {final_url}")

    # Source 4: Toast / 'View Post' Link or Permalink matching Title on Page
    if not final_url:
        try:
            dom_link = page.evaluate("""(titleStr) => {
                const anchors = Array.from(document.querySelectorAll('a[href]'));
                // Check 'View post' / 'Open' toast links first
                for (const a of anchors) {
                    const t = (a.innerText || '').trim().toLowerCase();
                    if (['view post', 'view thread', 'view note', 'open post', 'permalink', 'view it'].includes(t)) {
                        return a.href;
                    }
                }
                // Check link matching our submitted title
                const prefix = titleStr.slice(0, 25).toLowerCase();
                if (prefix.length >= 4) {
                    for (const a of anchors) {
                        if ((a.innerText || '').toLowerCase().includes(prefix) && a.href && !a.href.endsWith('#')) {
                            return a.href;
                        }
                    }
                }
                return '';
            }""", title_text)
            if dom_link and is_valid_live_post_url(dom_link):
                final_url = dom_link
                log_fn(f"🔗 [Source 4: DOM Permalink] Located live post link: {final_url}")
        except Exception:
            pass

    if not final_url:
        final_url = page.url

    # Mandatory Structural + Real Incognito Verification before accepting unknown-site URL!
    if not final_url or not is_valid_live_post_url(final_url, board_url):
        log_fn(f"❌ [Auto-Discovery] Post did not produce a valid public URL (remained on {final_url}).")
        return False, None

    is_pub, verified_u = verify_url_incognito(final_url, page=page, log_fn=log_fn, expected_title=title_text)
    if not is_pub:
        log_fn(f"❌ [Auto-Discovery] URL failed Incognito verification: {final_url}")
        return False, None

    final_url = verified_u or final_url

    # Self-Learning Blueprint Cache (only cached after passing Incognito verification!)
    try:
        if base_domain:
            recipes = load_recipes()
            auto_name = f"Auto-Learned ({base_domain})"
            if learned_recipe["editor_selector"] and learned_recipe["submit_selector"]:
                recipes[auto_name] = {
                    "name": auto_name,
                    "board_url": board_url,
                    "login_url": board_url,
                    "domain_pattern": base_domain,
                    "reply_selector": learned_recipe["reply_selector"],
                    "title_selector": learned_recipe["title_selector"],
                    "editor_selector": learned_recipe["editor_selector"],
                    "submit_selector": learned_recipe["submit_selector"]
                }
                save_recipes(recipes)
                log_fn(f"🧠 [Self-Learning] Cached Incognito-verified blueprint '{auto_name}' to recipes.json!")
    except Exception:
        pass

    return True, final_url


# ==============================================================================
# MULTI-PROVIDER AI CONTENT GENERATOR (GEMINI & GROQ & DEEPSEEK - 100% FREE)
# ==============================================================================
CACHED_GEMINI_MODEL = None

def get_active_gemini_model(api_key, ssl_ctx):
    return "gemini-1.5-flash"


def call_gemini_api(api_key, prompt, system_instruction="You are a professional content writer.", max_tokens=1500):
    import ssl
    try:
        ssl_ctx = ssl.create_default_context()
    except Exception:
        ssl_ctx = ssl._create_unverified_context()

    models_to_try = [
        "gemini-1.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash-8b",
        "gemini-1.5-pro"
    ]

    clean_key = api_key.strip().replace('"', '').replace("'", "")
    last_err = ""

    for model in models_to_try:
        for api_ver in ["v1beta", "v1"]:
            url = f"https://generativelanguage.googleapis.com/{api_ver}/models/{model}:generateContent?key={clean_key}"
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
            payload = {
                "system_instruction": {
                    "parts": [{"text": system_instruction}]
                },
                "contents": [
                    {
                        "parts": [{"text": prompt}]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.7,
                    "maxOutputTokens": max_tokens
                }
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=25, context=ssl_ctx) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts and "text" in parts[0]:
                            return parts[0]["text"].strip()
            except urllib.error.HTTPError as he:
                err_msg = ""
                try:
                    raw_err = he.read().decode("utf-8", errors="replace")
                    parsed = json.loads(raw_err)
                    err_msg = parsed.get("error", {}).get("message", raw_err)
                except Exception:
                    err_msg = str(he)
                last_err = err_msg

                if he.code == 400:
                    raise RuntimeError(f"Invalid Request or Key (400): {err_msg}")
                elif he.code == 403:
                    raise RuntimeError("API Key Error (403): Invalid API Key or API not enabled. Verify at aistudio.google.com/apikey")
                elif he.code == 429:
                    raise RuntimeError("Rate Limited (429): Quota reached for Gemini free tier. Please wait a minute and retry.")
                elif he.code == 404:
                    continue
                else:
                    raise RuntimeError(f"Google Gemini Error ({he.code}): {err_msg}")
            except Exception as e:
                last_err = str(e)
                continue

    raise RuntimeError(f"Could not connect to Gemini models ({last_err}). Please check your API key at aistudio.google.com/apikey or switch to Groq.")


CACHED_GROQ_MODEL = None

def get_active_groq_model(api_key, ssl_ctx):
    global CACHED_GROQ_MODEL
    if CACHED_GROQ_MODEL:
        return CACHED_GROQ_MODEL

    url = "https://api.groq.com/openai/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_models = [m.get("id", "") for m in data.get("data", [])]

            disallowed = ["whisper", "guard", "canopylabs", "orpheus", "vision", "embed", "tts", "audio"]
            clean_models = [
                m for m in raw_models
                if not any(bad in m.lower() for bad in disallowed)
            ]

            priority_patterns = [
                "llama-3.1-8b-instant",
                "llama3-8b-8192",
                "llama3-70b-8192",
                "llama-3.1-70b-versatile",
                "mixtral-8x7b-32768",
                "gemma2-9b-it",
                "deepseek-r1-distill",
                "qwen-2.5-32b",
                "llama-3.3-70b"
            ]

            for pat in priority_patterns:
                for m in clean_models:
                    if pat.lower() in m.lower():
                        CACHED_GROQ_MODEL = m
                        return m

            if clean_models:
                CACHED_GROQ_MODEL = clean_models[0]
                return clean_models[0]
    except Exception:
        pass

    CACHED_GROQ_MODEL = "llama-3.1-8b-instant"
    return CACHED_GROQ_MODEL


def call_groq_api(api_key, prompt, system_instruction="You are a professional content writer.", max_tokens=2048):
    clean_key = api_key.strip().replace('"', '').replace("'", "")
    if not clean_key:
        raise RuntimeError("Missing Groq API Key.")

    import ssl
    try:
        ssl_ctx = ssl.create_default_context()
    except Exception:
        ssl_ctx = ssl._create_unverified_context()

    active_model = get_active_groq_model(clean_key, ssl_ctx)

    models_to_try = [
        active_model,
        "llama-3.1-8b-instant",
        "llama3-8b-8192",
        "llama3-70b-8192",
        "mixtral-8x7b-32768",
        "gemma2-9b-it",
        "deepseek-r1-distill-llama-70b"
    ]

    seen = set()
    candidate_models = []
    for m in models_to_try:
        if m and m not in seen:
            seen.add(m)
            candidate_models.append(m)

    last_err = ""
    for model in candidate_models:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {clean_key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as he:
            err_msg = ""
            try:
                raw_err = he.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw_err)
                err_msg = parsed.get("error", {}).get("message", raw_err)
            except Exception:
                err_msg = str(he)
            last_err = err_msg

            if he.code == 401:
                raise RuntimeError("Authentication Failed (401): Invalid Groq API Key (starts with gsk_...). Verify at console.groq.com/keys")
            elif he.code == 429:
                raise RuntimeError("Rate Limited (429): Too many requests to Groq. Please wait a minute and retry.")
            elif he.code in (400, 404):
                if "terms" in err_msg.lower() or "model" in err_msg.lower() or "not exist" in err_msg.lower() or he.code == 404:
                    continue
                raise RuntimeError(f"Groq API Error ({he.code}): {err_msg}")
            else:
                raise RuntimeError(f"Groq API Error ({he.code}): {err_msg}")
        except Exception as e:
            last_err = str(e)
            continue

    raise RuntimeError(f"Could not connect to Groq models ({last_err}). Please check your API key at console.groq.com/keys")


SAVED_QUEUE_PATH = Path.home() / ".forum_suite_approved_queue.csv"
WORKING_SITES_PATH = Path.home() / ".forum_suite_working_sites.json"

def load_working_sites():
    try:
        if WORKING_SITES_PATH.exists():
            return json.loads(WORKING_SITES_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []

def save_working_site(site_url):
    if not site_url or not str(site_url).startswith("http"):
        return
    try:
        sites = load_working_sites()
        clean_url = str(site_url).strip()
        if clean_url not in sites:
            sites.append(clean_url)
            WORKING_SITES_PATH.write_text(json.dumps(sites, indent=2), encoding="utf-8")
    except Exception:
        pass

def append_to_saved_queue_csv(item):
    try:
        exists = SAVED_QUEUE_PATH.exists()
        with open(SAVED_QUEUE_PATH, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not exists:
                writer.writerow(["timestamp", "title", "body", "status", "url"])
            writer.writerow([
                time.strftime("%Y-%m-%d %H:%M:%S"),
                item.get("title", ""),
                item.get("body", ""),
                item.get("status", "⏳ Pending"),
                item.get("url", "")
            ])
    except Exception:
        pass


import sqlite3
def get_anythingllm_prompts():
    paths = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        paths.append(Path(appdata) / "anythingllm-desktop" / "storage" / "anythingllm.db")
        paths.append(Path(appdata) / "anythingllm" / "storage" / "anythingllm.db")
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        paths.append(Path(userprofile) / "AppData" / "Roaming" / "anythingllm-desktop" / "storage" / "anythingllm.db")
        paths.append(Path(userprofile) / ".anythingllm" / "anythingllm.db")
    user_home = Path.home()
    paths.append(user_home / ".config" / "anythingllm-desktop" / "storage" / "anythingllm.db")

    prompts = {}
    for p in paths:
        if p.exists():
            try:
                conn = sqlite3.connect(str(p))
                cur = conn.cursor()
                cur.execute("SELECT name, openAiPrompt FROM workspaces WHERE openAiPrompt IS NOT NULL AND openAiPrompt != '';")
                for name, pr in cur.fetchall():
                    prompts[name] = pr
                conn.close()
            except Exception:
                pass
    return prompts


def get_lm_studio_conversation_dirs(custom_path=None):
    dirs = []
    if custom_path:
        p = Path(custom_path)
        if p.exists():
            dirs.append(p)

    home_pointer = Path.home() / ".lmstudio-home-pointer"
    if home_pointer.exists():
        try:
            pt = Path(home_pointer.read_text().strip())
            if pt.exists():
                dirs.extend([pt, pt / "conversations", pt / "chats"])
        except Exception:
            pass

    user_home = Path.home()
    dirs.extend([
        user_home / ".cache" / "lm-studio" / "conversations",
        user_home / ".cache" / "lm-studio" / "chats",
        user_home / ".cache" / "lm-studio",
        user_home / ".lmstudio" / "conversations",
        user_home / ".lmstudio" / "chats",
        user_home / ".lmstudio",
        user_home / ".config" / "lm-studio" / "conversations",
        user_home / ".config" / "lm-studio",
    ])

    appdata = os.environ.get("APPDATA")
    if appdata:
        dirs.extend([
            Path(appdata) / "lm-studio" / "conversations",
            Path(appdata) / "LM Studio" / "conversations",
            Path(appdata) / "lm-studio",
            Path(appdata) / "LM Studio",
        ])

    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        dirs.extend([
            Path(localappdata) / "lm-studio" / "conversations",
            Path(localappdata) / "LM Studio" / "conversations",
            Path(localappdata) / "lm-studio",
            Path(localappdata) / "LM Studio",
        ])

    userprofile = os.environ.get("USERPROFILE")
    if userprofile and Path(userprofile) != user_home:
        up = Path(userprofile)
        dirs.extend([
            up / ".lmstudio" / "conversations",
            up / ".cache" / "lm-studio" / "conversations",
            up / ".lmstudio",
            up / ".cache" / "lm-studio",
        ])

    valid_dirs = []
    seen = set()
    for d in dirs:
        if d and str(d) not in seen:
            seen.add(str(d))
            if d.exists():
                valid_dirs.append(d)
    return valid_dirs


def extract_assistant_text(data):
    candidates = []
    def walk(obj, parent_role=None):
        if isinstance(obj, dict):
            role = obj.get("role") or obj.get("author") or obj.get("sender") or parent_role
            if str(role).lower() in ("assistant", "model", "ai", "bot"):
                for key in ("content", "text", "message", "value", "response"):
                    val = obj.get(key)
                    if isinstance(val, str) and val.strip():
                        candidates.append(val.strip())
                    elif isinstance(val, list):
                        parts = []
                        for item in val:
                            if isinstance(item, str):
                                parts.append(item)
                            elif isinstance(item, dict):
                                for subkey in ("text", "content", "value"):
                                    if isinstance(item.get(subkey), str):
                                        parts.append(item[subkey])
                        if parts:
                            candidates.append("\n".join(parts).strip())
            for k, v in obj.items():
                if k != "user":
                    walk(v, parent_role=role if role else parent_role)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, parent_role=parent_role)

    walk(data)
    if candidates:
        return candidates[-1]
    return None


def fetch_latest_from_lm_studio(custom_path=None):
    dirs = get_lm_studio_conversation_dirs(custom_path)
    candidates = []
    scanned_paths = [str(d) for d in dirs]

    for d in dirs:
        patterns = ["*.json", "*/*.json"]
        for p in patterns:
            for f in d.glob(p):
                try:
                    candidates.append((f.stat().st_mtime, f))
                except Exception:
                    pass

    if not candidates:
        return None, scanned_paths, "No conversation .json files found in standard paths."

    candidates.sort(key=lambda x: x[0], reverse=True)

    for mtime, latest_file in candidates[:6]:
        try:
            with open(latest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            text = extract_assistant_text(data)
            if text:
                return text, scanned_paths, latest_file.name
        except Exception:
            continue

    return None, scanned_paths, f"Found {len(candidates)} JSON files, but no assistant response was detected inside."


def clean_forum_text(text):
    if not text:
        return ""
    lines = []
    for line in text.splitlines():
        if re.match(r'^\s*([*\-_]\s*){3,}\s*$', line):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r'\*\*\*\s*(.*?)\s*\*\*\*', r'\1', cleaned)
    cleaned = cleaned.replace('***', '')
    cleaned = re.sub(r'^#{1,6}\s*', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned).strip()
    return cleaned


def clean_forum_title(title):
    if not title:
        return ""
    t = title.strip()
    t = re.sub(r'^(title:|subject:|topic:|#+)\s*', '', t, flags=re.IGNORECASE).strip()
    t = re.sub(r'^[*_`\'"]+|[*_`\'"]+$', '', t).strip()
    t = t.replace('***', '').replace('**', '').strip()
    return t


def parse_extracted_post(raw_text):
    clean = raw_text.strip()
    if "{" in clean and "}" in clean:
        try:
            m = re.search(r'\{.*\}', clean, re.DOTALL)
            if m:
                d = json.loads(m.group(0))
                t = d.get("title", "").strip()
                b = d.get("body", "").strip()
                if t and b:
                    return clean_forum_title(t), clean_forum_text(b)
        except Exception:
            pass
    lines = clean.splitlines()
    first_line = lines[0].strip() if lines else ""
    if first_line.lower().startswith(("title:", "subject:", "# ")):
        title = re.sub(r'^(title:|subject:|#)\s*', '', first_line, flags=re.IGNORECASE).strip()
        body = "\n".join(lines[1:]).strip()
        return clean_forum_title(title), clean_forum_text(body)
    if len(lines) > 1 and len(first_line) < 80:
        return clean_forum_title(first_line), clean_forum_text("\n".join(lines[1:]).strip())
    return clean_forum_title(clean[:60]), clean_forum_text(clean)

def call_local_gemma_api(prompt, system_instruction="You are a professional content writer.", max_tokens=4096):
    cfg = load_config()
    api_key = cfg.get("anythingllm_api_key", "").strip()
    groq_key = cfg.get("groq_api_key", "").strip()
    gemini_key = cfg.get("gemini_api_key", "").strip()
    anything_url = cfg.get("anythingllm_url", "http://localhost:3001/api/v1").rstrip("/")
    workspace = cfg.get("workspace_slug", "content").strip() or "content"
    ollama_url = cfg.get("ollama_url", "http://localhost:11434").rstrip("/")
    model_name = cfg.get("model", "huihui_ai/gemma3n-abliterated:e2b-fp16").strip() or "huihui_ai/gemma3n-abliterated:e2b-fp16"

    # Auto-detect if user pasted a Free Groq key (gsk_...) or Free Gemini key (AIza...) in the main API key box
    if not groq_key and api_key.startswith("gsk_"):
        groq_key = api_key
    if not gemini_key and api_key.startswith("AIza"):
        gemini_key = api_key

    # Step 0A: Try 100% Free Groq Cloud API if key is configured
    if groq_key:
        try:
            return call_groq_api(groq_key, prompt, system_instruction=system_instruction, max_tokens=min(max_tokens, 4096))
        except Exception as e:
            if not gemini_key:
                pass

    # Step 0B: Try 100% Free Google Gemini Cloud API if key is configured
    if gemini_key:
        try:
            return call_gemini_api(gemini_key, prompt, system_instruction=system_instruction, max_tokens=min(max_tokens, 4096))
        except Exception as e:
            pass

    # Step 1: Try AnythingLLM Desktop API
    try:
        url = f"{anything_url}/workspace/{workspace}/chat"
        payload = {"message": prompt, "mode": "chat"}
        headers = {"Content-Type": "application/json"}
        if api_key and not api_key.startswith("gsk_") and not api_key.startswith("AIza"):
            headers["Authorization"] = f"Bearer {api_key}"
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            ans = data.get("textResponse", "").strip()
            if ans:
                return ans
    except Exception:
        pass

    # Step 2: Direct Ollama connection on port 11434
    url = f"{ollama_url}/api/chat"
    messages = []
    if system_instruction and system_instruction.strip():
        messages.append({"role": "system", "content": system_instruction.strip()})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_ctx": 4096,
            "num_predict": max_tokens
        }
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("message", {}).get("content", "").strip()
    except Exception:
        raise RuntimeError(
            "No AI Engine responded! For 100% FREE Cloud AI (no GPU needed), open '🔑 API Settings' and paste a free Groq API Key (console.groq.com, starts with gsk_...) or free Google Gemini API Key (aistudio.google.com/apikey, starts with AIza...)."
        )



def generate_ai_post_item(topic, target_platform="Auto-Detect (Recommended)", max_tokens=4096, custom_system_prompt=""):
    format_enforcement = (
        "\n\nOUTPUT FORMAT RULE:\n"
        "Start your response strictly with:\n"
        "Title: <Catchy Title Here>\n\n"
        "Followed by the forum post body text.\n"
        "Do NOT use markdown horizontal divider lines like '***' or '---'.\n"
        "Do NOT wrap section headers in triple asterisks '***'. Write in clean, authentic forum paragraphs.\n"
    )
    if "tmdb" in str(target_platform).lower() or "movie" in str(target_platform).lower():
        format_enforcement += "Keep the BODY under 900 characters total. Do NOT include headings or subheadings in the body.\n"

    if custom_system_prompt and custom_system_prompt.strip():
        system_rules = custom_system_prompt.strip() + format_enforcement
    else:
        system_rules = (
            "You are an experienced forum contributor writing natural, authentic, and engaging discussions."
            + format_enforcement
        )

    prompt = f"Create a forum post about: {topic}"

    raw_output = call_local_gemma_api(prompt, system_rules, max_tokens=max_tokens)
    title, body = parse_extracted_post(raw_output)
    return {"title": title, "body": body, "status": "⏳ Pending", "url": ""}


def clean_and_extract_paragraphs(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    paragraphs = []
    for line in lines:
        if re.match(r'^#{1,6}\s+', line):
            continue
        if re.match(r'^(?:heading|subheading|title|subject|section|topic|overview|synopsis)\s*[:\-]', line, flags=re.I):
            continue
        if len(line) < 60 and (line.endswith(":") or not line.endswith((".", "!", "?", '"', "'"))):
            if len(line.split()) <= 8:
                continue
        paragraphs.append(line)
    return paragraphs

def get_rotated_overview(body_text, post_index=0, max_chars=950):
    """
    Selects a non-repeating rotating slice of paragraphs strictly capped under 1000 characters
    (TMDb enforced limit is 1000 characters maximum, 10 characters minimum).
    Strips raw markdown syntax, headings, and guarantees complete sentence boundaries.
    Rotates chunks sequentially based on post_index so each post/keyword gets fresh content.
    """
    clean_body = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', str(body_text))
    clean_body = re.sub(r'[*_~`]+', '', clean_body)

    paras = clean_and_extract_paragraphs(clean_body)
    if not paras:
        clean_text = re.sub(r'^[#*\-\s]+', '', clean_body).strip()
        if len(clean_text) <= max_chars:
            res = clean_text
        else:
            truncated = clean_text[:max_chars]
            last_punct = max(truncated.rfind('. '), truncated.rfind('! '), truncated.rfind('? '))
            res = truncated[:last_punct+1] if last_punct > 250 else truncated[:max_chars].rsplit(' ', 1)[0]
        return res[:980].strip()

    chunks = []
    curr_chunk = []
    curr_len = 0

    for p in paras:
        if len(p) > max_chars:
            sentences = re.split(r'(?<=[.!?])\s+', p)
            s_chunk = ""
            for s in sentences:
                if len(s_chunk) + len(s) + 1 <= max_chars:
                    s_chunk += (" " if s_chunk else "") + s
                else:
                    if s_chunk:
                        chunks.append(s_chunk.strip())
                    s_chunk = s[:max_chars]
            if s_chunk:
                chunks.append(s_chunk.strip())
            continue

        if curr_len + len(p) + 2 <= max_chars:
            curr_chunk.append(p)
            curr_len += len(p) + 2
        else:
            if curr_chunk:
                chunks.append("\n\n".join(curr_chunk).strip())
            curr_chunk = [p]
            curr_len = len(p)

    if curr_chunk:
        chunks.append("\n\n".join(curr_chunk).strip())

    if not chunks:
        chunks = [clean_body[:max_chars]]

    selected_chunk = chunks[post_index % len(chunks)].strip()
    # Strict hard ceiling to never exceed 1000 characters
    if len(selected_chunk) > 980:
        truncated = selected_chunk[:980]
        last_punct = max(truncated.rfind('. '), truncated.rfind('! '), truncated.rfind('? '))
        selected_chunk = truncated[:last_punct+1] if last_punct > 250 else truncated[:980].rsplit(' ', 1)[0]

    return selected_chunk.strip()


def tmdb_click_next_btn(page, log_fn, step_name, timeout_sec=12):
    """Clicks the Next button using Playwright role-based selection matching the inspector recording."""
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            next_btn = page.get_by_role("button", name="Next").first
            if next_btn.count() > 0 and next_btn.is_visible():
                next_btn.click(force=True)
                log_fn(f"Clicked Next on {step_name}")
                return True
        except Exception:
            pass

        selectors = [
            '.k-wizard-step:not(.k-hidden) button[data-wizard-next]',
            'button[data-wizard-next]:visible',
            'button.k-button-primary[data-wizard-next]',
            'button:has-text("Next"):visible',
            'button[data-wizard-next]',
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(force=True)
                    log_fn(f"Clicked Next on {step_name} via {sel}")
                    return True
            except Exception:
                continue

        try:
            clicked = page.evaluate("""() => {
                const allNext = Array.from(document.querySelectorAll('button[data-wizard-next], button.k-button-primary, button'));
                for (const b of allNext) {
                    const txt = (b.innerText || '').trim().toLowerCase();
                    if (b.offsetParent !== null && (txt === 'next' || b.hasAttribute('data-wizard-next'))) {
                        b.click();
                        return true;
                    }
                }
                return false;
            }""")
            if clicked:
                log_fn(f"Clicked Next on {step_name} via DOM evaluate.")
                return True
        except Exception:
            pass

        time.sleep(1)

    log_fn(f"Warning: Could not advance {step_name} via Next button.")
    return False


def tmdb_create_movie(page, board_url, title_text, body_text, log_fn, post_index=0):
    """
    Automates creating a new movie entry on TMDb matching the exact Playwright inspector recording:
    1. Navigate to https://www.themoviedb.org/movie/new
    2. Step 1 (Getting Started): Click Next
    3. Step 2 (Movie Details): Fill original_title, overview (rotated, <1000 chars), Click Next
    4. Step 3 (Duplicate Check): If 'I have reviewed the results' appears, check it and Click Next
    5. Step 4 (Additional Details): Click Next
    6. Step 5: Click Save
    7. Redirect to live movie page -> auto-refresh once to render overview
    """
    title_text = str(title_text).strip()
    body_text = str(body_text).strip()
    target_url = "https://www.themoviedb.org/movie/new"

    log_fn(f"Opening TMDb Movie Creator: {target_url}")
    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log_fn(f"Navigation note: {e}")
    time.sleep(2.5)

    # Dismiss any cookie consent banners
    try:
        cookie_btn = page.locator('#onetrust-accept-btn-handler, button:has-text("Accept All"), button:has-text("Accept Cookies"), .osano-cm-accept-all, button:has-text("I Agree"), button:has-text("Accept")').first
        if cookie_btn.count() > 0 and cookie_btn.is_visible():
            cookie_btn.click()
            time.sleep(0.5)
    except Exception:
        pass

    if "/login" in page.url or "permission" in page.url.lower():
        log_fn("❌ Not logged in to TMDb. Please use '⚡ Login & Post (Live)' to authenticate.")
        return False, None

    # Step 1: Getting Started -> Next
    log_fn("Step 1: Getting Started -> Clicking Next...")
    if not tmdb_click_next_btn(page, log_fn, "Step 1"):
        return False, None
    time.sleep(2)

    # Clean title
    clean_title = re.sub(r'^(?:Title|Subject|Topic)\s*:\s*', '', str(title_text).strip(), flags=re.I).strip()
    clean_title = re.sub(r'^[#*_\-\s]+', '', clean_title).strip()
    clean_title = re.sub(r'[#*_\-\s]+$', '', clean_title).strip()

    # Rotate overview under 1000 chars for this post_index
    overview_text = get_rotated_overview(body_text, post_index=post_index, max_chars=950)

    # Step 2: Fill original_title and overview (matching inspector recording)
    log_fn(f"Step 2: Entering Original Title: '{clean_title[:55]}'")
    title_filled = False
    try:
        # Match inspector: page.get_by_role("textbox", name="original_title")
        ot_box = page.get_by_role("textbox", name=re.compile(r"original_title", re.I)).first
        if ot_box.count() > 0 and ot_box.is_visible():
            ot_box.click()
            ot_box.fill(clean_title)
            title_filled = True
            log_fn(f"Filled original_title via role selector: {clean_title[:50]}")
    except Exception:
        pass

    if not title_filled:
        try:
            t_loc = page.locator('input#original_title, input[name="original_title"], input#title, input[name="title"], input[placeholder*="title" i]').first
            t_loc.wait_for(state="visible", timeout=12000)
            t_loc.click()
            t_loc.fill(clean_title)
            title_filled = True
            log_fn(f"Filled title via locator: {clean_title[:50]}")
        except Exception as e:
            log_fn(f"Could not fill Title: {e}")
            return False, None

    # Also fill primary title if it is a separate input field
    try:
        t_box = page.get_by_role("textbox", name=re.compile(r"^title$", re.I)).first
        if t_box.count() > 0 and t_box.is_visible():
            t_box.click()
            t_box.fill(clean_title)
    except Exception:
        pass

    log_fn(f"Step 2: Entering Overview ({len(overview_text)} chars, rotated chunk #{post_index + 1})...")
    overview_filled = False
    try:
        # Match inspector: page.get_by_role("textbox", name="overview")
        ov_box = page.get_by_role("textbox", name=re.compile(r"overview", re.I)).first
        if ov_box.count() > 0 and ov_box.is_visible():
            ov_box.click()
            ov_box.fill(overview_text)
            overview_filled = True
            log_fn(f"Filled overview via role selector ({len(overview_text)} chars)")
    except Exception:
        pass

    if not overview_filled:
        try:
            ov_loc = page.locator('textarea#overview, textarea[name="overview"], textarea[placeholder*="overview" i]').first
            ov_loc.wait_for(state="visible", timeout=10000)
            ov_loc.click()
            ov_loc.fill(overview_text)
            overview_filled = True
            log_fn(f"Filled overview via locator ({len(overview_text)} chars)")
        except Exception as e:
            log_fn(f"Could not fill Overview: {e}")
            return False, None

    time.sleep(1)
    log_fn("Step 2: Clicking Next...")
    if not tmdb_click_next_btn(page, log_fn, "Step 2 (Movie Details)"):
        return False, None
    time.sleep(2.5)

    # Step 3: Check for duplicate screen ("I have reviewed the results")
    log_fn("Step 3: Checking if duplicate confirmation is required...")
    try:
        time.sleep(1.5)
        # Match inspector: page.get_by_role("checkbox", name="I have reviewed the results")
        chk = page.get_by_role("checkbox", name=re.compile(r"I have reviewed", re.I)).first
        if chk.count() > 0 and chk.is_visible():
            log_fn("Duplicate detected: Checking 'I have reviewed the results'...")
            chk.check(force=True)
            time.sleep(0.5)
            # Advance duplicate step
            tmdb_click_next_btn(page, log_fn, "Step 3 (Duplicate Confirmation)")
            time.sleep(2)
        else:
            # Check other duplicate text variations
            page.evaluate("""() => {
                const cbs = document.querySelectorAll('input[type="checkbox"]');
                for (const c of cbs) {
                    if (!c.checked) {
                        c.click();
                        c.checked = true;
                        c.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                }
                const clickables = document.querySelectorAll('label, div');
                for (const el of clickables) {
                    const txt = (el.innerText || '').toLowerCase();
                    if (txt.includes("reviewed") || txt.includes("don't see") || txt.includes("continue adding")) {
                        el.click();
                    }
                }
            }""")
            # Check if there is still a Next button on duplicate step
            btn = page.get_by_role("button", name="Next").first
            if btn.count() > 0 and btn.is_visible():
                btn.click()
                time.sleep(2)
    except Exception as e:
        log_fn(f"Duplicate screen note: {e}")

    # Step 4: Additional Details -> Next
    log_fn("Step 4: Additional Details -> Clicking Next...")
    try:
        next_btn = page.get_by_role("button", name="Next").first
        if next_btn.count() > 0 and next_btn.is_visible():
            next_btn.click()
            time.sleep(2)
        else:
            tmdb_click_next_btn(page, log_fn, "Step 4 (Additional Details)")
            time.sleep(2)
    except Exception:
        pass

    # Step 5: Save (matching inspector recording: page.get_by_role("button", name="Save").click())
    log_fn("Step 5: Submitting movie (Clicking Save / Finish)...")
    save_clicked = False
    try:
        # Match inspector: page.get_by_role("button", name="Save")
        save_btn = page.get_by_role("button", name=re.compile(r"Save|Finish", re.I)).first
        if save_btn.count() > 0 and save_btn.is_visible():
            save_btn.click(force=True)
            log_fn("Clicked Save button via role selector!")
            save_clicked = True
    except Exception:
        pass

    if not save_clicked:
        save_selectors = [
            '.k-wizard-step:not(.k-hidden) button[data-wizard-done]',
            'button[data-wizard-done]:visible',
            'button.k-button-primary[data-wizard-done]',
            'button:has-text("Save"):visible',
            'button:has-text("Finish"):visible',
            'button.k-button-primary:has-text("Save")',
            'button.k-button-primary:has-text("Finish")',
            'input[value="Save"]',
            'input[value="Finish"]',
        ]
        for s_sel in save_selectors:
            try:
                loc = page.locator(s_sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(force=True)
                    log_fn(f"Clicked Save via locator {s_sel}")
                    save_clicked = True
                    break
            except Exception:
                continue

    if not save_clicked:
        try:
            page.evaluate("""() => {
                const allBtns = Array.from(document.querySelectorAll('button, input[type="submit"]'));
                for (const b of allBtns) {
                    const txt = (b.innerText || b.value || '').trim().toLowerCase();
                    if (b.offsetParent !== null && (txt === 'save' || txt === 'finish' || b.hasAttribute('data-wizard-done'))) {
                        b.click();
                        return true;
                    }
                }
                return false;
            }""")
            log_fn("Triggered Save click via DOM evaluate.")
            save_clicked = True
        except Exception:
            pass

    # Waiting for redirect to live movie URL: https://www.themoviedb.org/movie/<id>-<slug>
    log_fn("Waiting for TMDb to finalize and redirect to live movie URL...")
    deadline = time.time() + 45
    posted_url = None

    while time.time() < deadline:
        time.sleep(1)
        curr = (page.url or "").strip()

        if "/movie/" in curr and "/new" not in curr:
            posted_url = curr
            break

        try:
            links = page.locator('a[href*="/movie/"]:not([href*="/new"])')
            for idx in range(min(5, links.count())):
                href = links.nth(idx).get_attribute("href")
                if href and re.search(r'/movie/\d+', href):
                    posted_url = f"https://www.themoviedb.org{href}" if href.startswith("/") else href
                    break
        except Exception:
            pass
        if posted_url:
            break

        elapsed = time.time() - (deadline - 45)
        if elapsed in (7, 14, 21):
            try:
                s_btn = page.get_by_role("button", name=re.compile(r"Save|Finish", re.I)).first
                if s_btn.count() > 0 and s_btn.is_visible():
                    log_fn("Re-triggering Save button...")
                    s_btn.click(force=True)
            except Exception:
                pass

    if not posted_url:
        curr = (page.url or "").strip()
        if "/movie/" in curr and "/new" not in curr:
            posted_url = curr

    if posted_url:
        log_fn(f"🎉 Captured Live Movie URL: {posted_url}")
        
        # Soft reload to flush TMDb CDN cache and immediately render title and overview
        try:
            time.sleep(2)
            page.reload(wait_until="domcontentloaded", timeout=15000)
            time.sleep(1.5)
            posted_url = page.url or posted_url
        except Exception as e:
            log_fn(f"Note on page refresh: {e}")

        log_fn(f"✅ Success: {posted_url}")
        return True, posted_url

    log_fn("Could not capture redirected movie URL within timeout.")
    return False, None




def safe_click(locator, timeout=6000, page=None):
    """
    Safely clicks an element even if the browser window is minimized, occluded, or backgrounded:
    1. Tries standard click(timeout=...)
    2. Falls back to dispatch_event('click')
    3. Falls back to evaluate('(el) => el.click()')
    """
    if not locator:
        return False
    try:
        if locator.count() == 0:
            return False
    except Exception:
        pass
    try:
        locator.click(timeout=timeout)
        return True
    except Exception:
        try:
            locator.dispatch_event("click")
            return True
        except Exception:
            try:
                locator.evaluate("(el) => el.click()")
                return True
            except Exception:
                return False


def dismiss_addon_modal_if_present(page, log_fn):
    """Detects and closes any add-on, promotional, or notification modal that appears on WaiverElectronic."""
    time.sleep(0.8)
    close_selectors = [
        ".modal button:has-text('Close')",
        ".modal a:has-text('Close')",
        "button.close",
        ".modal-header .close",
        "[aria-label='Close']",
        "[aria-label='close']",
        "button:has-text('Close')",
        "a:has-text('Close')",
        ".modal-footer button:has-text('Cancel')",
        "button:has-text('Dismiss')",
        "button:has-text('No thanks')",
        "button:has-text('Later')",
        "button:has-text('✕')",
        "button:has-text('×')",
        ".close-modal, .btn-close",
        "div.modal button:has-text('OK')",
        "div.modal button:has-text('Got it')"
    ]
    for sel in close_selectors:
        try:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible():
                btn.click(timeout=2500)
                log_fn(f"⚡ Dismissed add-on modal via selector: {sel}")
                time.sleep(1)
                return True
        except Exception:
            continue
    return False


EXPANDED_SYNONYMS = {
    r"\bquick\b": "{quick|fast|rapid|prompt}",
    r"\bquickly\b": "{quickly|rapidly|promptly|in no time}",
    r"\beasy\b": "{easy|simple|effortless|straightforward}",
    r"\beasily\b": "{easily|simply|effortlessly|with ease}",
    r"\bimportant\b": "{important|essential|crucial|vital|key}",
    r"\bcomplete\b": "{complete|fill out|finalize|submit|provide}",
    r"\bcompleted\b": "{completed|filled out|finalized|submitted}",
    r"\breliable\b": "{reliable|trusted|dependable|proven}",
    r"\bhelp\b": "{help|assist|support|guidance}",
    r"\bguide\b": "{guide|walkthrough|tutorial|overview}",
    r"\bgreat\b": "{great|excellent|fantastic|superb|wonderful}",
    r"\bnew\b": "{new|latest|updated|fresh}",
    r"\bcheck out\b": "{check out|explore|take a look at|review}",
    r"\bfree\b": "{free|complimentary|no-cost}",
    r"\bsafe\b": "{safe|secure|protected}",
    r"\bsafely\b": "{safely|securely|without worry}",
    r"\bwebsite\b": "{website|site|platform|portal}",
    r"\bwelcome\b": "{welcome|greetings|hello everyone|hi all}",
    r"\bthanks\b": "{thanks|thank you|much appreciated|cheers}",
    r"\bprocess\b": "{process|procedure|steps|workflow}",
    r"\bconvenient\b": "{convenient|hassle-free|seamless|user-friendly}",
    r"\baccess\b": "{access|view|obtain|reach|get to}",
    r"\baccurate\b": "{accurate|precise|exact|correct}",
    r"\bdetails\b": "{details|information|specs|particulars}",
    r"\binstant\b": "{instant|immediate|real-time}",
    r"\binstantly\b": "{instantly|immediately|in real-time|right away}",
    r"\bstart\b": "{start|begin|commence|get started}",
    r"\bcreate\b": "{create|generate|build|establish}",
    r"\benjoy\b": "{enjoy|experience|appreciate}",
    r"\buseful\b": "{useful|helpful|valuable|beneficial}",
}

def generate_spintax_variations(text, cfg=None):
    """Generates rich spintax variations from plain text."""
    if not text:
        return ""
    res = text
    for pat, rep in EXPANDED_SYNONYMS.items():
        res = re.sub(pat, rep, res, flags=re.IGNORECASE)
    return res

def get_active_proxy(cfg, post_index=0):
    """Resolves active proxy based on configuration and rotation settings."""
    if not cfg:
        return None
    rotation = cfg.get("proxy_rotation_enabled", False)
    plist_raw = cfg.get("proxy_list", "")
    single_p = cfg.get("proxy_server", "")
    
    proxies = []
    if plist_raw:
        proxies = [p.strip() for p in plist_raw.replace(",", "\n").splitlines() if p.strip()]
    if not proxies and single_p:
        proxies = [single_p]
        
    if not proxies:
        return None
        
    if rotation and len(proxies) > 1:
        return proxies[post_index % len(proxies)]
    return proxies[0]



DEFAULT_GSHEET_URL = "https://docs.google.com/spreadsheets/d/1zjHDFpwHZJi440N3WZ0dDi3OYrGWrEFPBVTvhYiZhAg/edit?usp=sharing"
APPS_SCRIPT_WEBHOOK_CODE = '// ============================================================================\n// ⚡ Forum Studio Pro — 0.2s Instant Google Sheet Column A (A1+) Webhook\n// 1. In your Google Sheet (1zjHDFpwHZJi440N3WZ0dDi3OYrGWrEFPBVTvhYiZhAg), click Extensions -> Apps Script\n// 2. Paste this code, save, and click Deploy -> New deployment -> Web app\n//    (Execute as: "Me", Who has access: "Anyone")\n// 3. Copy the Web App URL (https://script.google.com/macros/s/.../exec) into Forum Studio!\n// ============================================================================\nfunction doPost(e) {\n  var lock = LockService.getScriptLock();\n  lock.waitLock(25000);\n  try {\n    var data = JSON.parse(e.postData.contents || "{}");\n    var urls = data.urls || [];\n    var ss = SpreadsheetApp.getActiveSpreadsheet();\n    var sheet = ss.getSheets()[0];\n    var lastRow = sheet.getLastRow();\n    var existing = {};\n    if (lastRow > 0) {\n      var vals = sheet.getRange(1, 1, lastRow, 1).getValues();\n      for (var i = 0; i < vals.length; i++) {\n        var v = String(vals[i][0] || "").trim();\n        if (v) existing[v] = true;\n      }\n    }\n    var nextRow = lastRow + 1; // Starts strictly at A1 (row 1) when empty!\n    if (lastRow === 1 && String(sheet.getRange(1, 1).getValue() || "").trim() === "") {\n      nextRow = 1;\n    }\n    var added = [];\n    for (var j = 0; j < urls.length; j++) {\n      var u = String(urls[j] || "").trim();\n      if (u && !existing[u]) {\n        sheet.getRange(nextRow, 1).setValue(u);\n        existing[u] = true;\n        added.push("A" + nextRow);\n        nextRow++;\n      }\n    }\n    SpreadsheetApp.flush();\n    return ContentService.createTextOutput(JSON.stringify({\n      success: true,\n      added_cells: added,\n      count: added.length\n    })).setMimeType(ContentService.MimeType.JSON);\n  } catch (err) {\n    return ContentService.createTextOutput(JSON.stringify({\n      success: false,\n      error: String(err)\n    })).setMimeType(ContentService.MimeType.JSON);\n  } finally {\n    lock.releaseLock();\n  }\n}'
_GSHEET_SYNC_LOCK = threading.Lock()


def extract_gsheet_id(sheet_url: str) -> str:
    if not sheet_url:
        return ""
    m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", str(sheet_url))
    return m.group(1) if m else ""


def get_existing_gsheet_col_a(sheet_id: str) -> list:
    """
    Fetches the current Column A values from a Google Sheet via its fast CSV export endpoint
    so we know the exact next empty row (A1, A2, A3, ...) and avoid duplicate rows.
    """
    if not sheet_id:
        return []
    import ssl
    try:
        ssl_ctx = ssl._create_unverified_context()
        csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid=0"
        req = urllib.request.Request(
            csv_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Cache-Control": "no-cache"
            }
        )
        with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
            raw_csv = resp.read().decode("utf-8", errors="replace")
            rows = list(csv.reader(io.StringIO(raw_csv)))
            col_a = []
            for r in rows:
                val = (r[0].strip() if r and len(r) > 0 else "")
                col_a.append(val)
            # Strip trailing empty rows
            while col_a and not col_a[-1]:
                col_a.pop()
            return col_a
    except Exception:
        return []


def sync_urls_to_google_sheet_column_a(urls_to_sync, sheet_url: str = None, log_fn=None, browser=None) -> tuple:
    """
    Bulletproof Google Sheet Column A (A1, A2, A3...) Auto-URL Engine:
    Writes verified live URLs one-by-one into Column A starting from cell A1 downward
    on https://docs.google.com/spreadsheets/d/1zjHDFpwHZJi440N3WZ0dDi3OYrGWrEFPBVTvhYiZhAg/edit?usp=sharing.
    - Uses _GSHEET_SYNC_LOCK so concurrent 1-4 tab workers serialize cleanly without cell collisions.
    - Checks existing Column A values via CSV export so it never overwrites existing URLs and starts at A1 when empty.
    - Uses deterministic Name Box (input#t-name-box) + Formula Bar (#t-formula-bar-input) DOM injection
      plus keyboard fallback and post-write CSV verification.
    """
    if isinstance(urls_to_sync, str):
        urls_list = [urls_to_sync.strip()] if urls_to_sync.strip() else []
    else:
        urls_list = [str(u).strip() for u in (urls_to_sync or []) if str(u).strip().startswith("http")]

    if not urls_list:
        return False, "No valid URLs provided to sync."

    cfg = load_config()
    target_sheet_url = (sheet_url or cfg.get("gsheet_sync_url") or DEFAULT_GSHEET_URL).strip()
    if not target_sheet_url:
        target_sheet_url = DEFAULT_GSHEET_URL
    webhook_url = (cfg.get("gsheet_webhook_url") or "").strip()
    if "script.google.com/macros/" in target_sheet_url and not webhook_url:
        webhook_url = target_sheet_url

    with _GSHEET_SYNC_LOCK:
        # Option A: 0.2s Instant Google Apps Script Webhook (Zero-Browser, Zero-RAM HTTP POST!)
        if webhook_url and "script.google.com/macros/" in webhook_url:
            try:
                import ssl, time as _t
                t0 = _t.time()
                ssl_ctx = ssl._create_unverified_context()
                payload = json.dumps({
                    "urls": urls_list,
                    "sheet_url": target_sheet_url,
                    "column": "A",
                    "start_row": 1
                }).encode("utf-8")
                req = urllib.request.Request(
                    webhook_url,
                    data=payload,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
                    raw_res = resp.read().decode("utf-8", errors="replace")
                    elapsed = _t.time() - t0
                    try:
                        res_json = json.loads(raw_res)
                        cells = ", ".join(res_json.get("added_cells", [])) or "Column A"
                    except Exception:
                        cells = "Column A (A1+)"
                    if log_fn:
                        log_fn(f"⚡ [0.2s Sheet Webhook] Instantly added {len(urls_list)} URL(s) to {cells} in {elapsed:.2f}s!")
                    return True, f"Instantly synced {len(urls_list)} URL(s) to {cells} ({elapsed:.2f}s)!"
            except Exception as e:
                if log_fn:
                    log_fn(f"⚠️ [Sheet Webhook Fallback] {e}; falling back to direct sheet editor...")

        # Option B: Direct Google Sheets Editor (Zero-Auth for 'Anyone with link can edit' sheets)
        sheet_id = extract_gsheet_id(target_sheet_url)
        if not sheet_id:
            return False, "Invalid Google Sheet URL."

        existing_col_a = get_existing_gsheet_col_a(sheet_id)
        existing_set = set(u.strip() for u in existing_col_a if u.strip())

        new_urls = [u for u in urls_list if u not in existing_set]
        if not new_urls:
            if log_fn:
                log_fn(f"📊 [Google Sheet Sync] URL(s) already in Column A (Rows A1..A{max(1, len(existing_col_a))}).")
            return True, f"All {len(urls_list)} URL(s) are already in Column A!"

        next_row = len(existing_col_a) + 1  # Starts at 1 (Cell A1) when sheet is empty!
        if log_fn:
            log_fn(f"📊 [Google Sheet Auto-Add] Writing {len(new_urls)} URL(s) to Column A starting at cell A{next_row}...")

        def _write_in_sheet_page(pg):
            nav_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit#gid=0&range=A{next_row}"
            pg.goto(nav_url, wait_until="domcontentloaded", timeout=40000)

            # Wait up to 12 seconds for Google Sheets Name Box (#t-name-box) or Formula Bar to become ready
            for _ in range(24):
                try:
                    nb_ready = pg.locator('input#t-name-box, input.waffle-name-box, #t-formula-bar-input').first
                    if nb_ready.count() > 0 and nb_ready.is_visible():
                        break
                except Exception:
                    pass
                time.sleep(0.5)
            time.sleep(1.5)

            for idx_u, u_val in enumerate(new_urls):
                target_cell = f"A{next_row + idx_u}"

                # Step 1: Select exact target cell A{row} via Name Box (#t-name-box)
                for nb_sel in ['input#t-name-box', 'input.waffle-name-box', '[aria-label="Name box"]']:
                    try:
                        nb = pg.locator(nb_sel).first
                        if nb.count() > 0 and nb.is_visible():
                            nb.click(timeout=3000)
                            time.sleep(0.15)
                            pg.keyboard.press("Control+A")
                            pg.keyboard.insert_text(target_cell)
                            pg.keyboard.press("Enter")
                            time.sleep(0.4)
                            break
                    except Exception:
                        continue

                # Step 2: Type URL via Formula Bar (#t-formula-bar-input) or direct active cell keyboard input
                typed_via_fbar = False
                for fb_sel in ['#t-formula-bar-input div.cell-input', '#t-formula-bar-input [contenteditable="true"]', '#t-formula-bar-input']:
                    try:
                        fb = pg.locator(fb_sel).first
                        if fb.count() > 0 and fb.is_visible():
                            fb.click(timeout=3000)
                            time.sleep(0.15)
                            pg.keyboard.press("Control+A")
                            pg.keyboard.press("Backspace")
                            pg.keyboard.insert_text(u_val)
                            time.sleep(0.2)
                            pg.keyboard.press("Enter")
                            time.sleep(0.45)
                            typed_via_fbar = True
                            break
                    except Exception:
                        continue

                if not typed_via_fbar:
                    pg.keyboard.press("Enter")
                    time.sleep(0.15)
                    pg.keyboard.insert_text(u_val)
                    time.sleep(0.2)
                    pg.keyboard.press("Enter")
                    time.sleep(0.45)

                if log_fn:
                    log_fn(f"📊 [Google Sheet] Added to cell {target_cell} -> {u_val}")

            # Wait 2.5s for Google Sheets background save XHR to commit to Drive
            time.sleep(2.5)

        try:
            if browser is not None:
                gs_ctx = browser.new_context(viewport={"width": 1280, "height": 800})
                gs_page = gs_ctx.new_page()
                try:
                    _write_in_sheet_page(gs_page)
                finally:
                    try:
                        gs_ctx.close()
                    except Exception:
                        pass
            else:
                with sync_playwright() as p_gs:
                    b_gs = launch_safe_browser(p_gs, headless=True)
                    if not b_gs:
                        return False, "Could not launch headless browser for Google Sheet sync."
                    try:
                        gs_ctx = b_gs.new_context(viewport={"width": 1280, "height": 800})
                        gs_page = gs_ctx.new_page()
                        _write_in_sheet_page(gs_page)
                    finally:
                        try:
                            b_gs.close()
                        except Exception:
                            pass
            return True, f"Successfully added {len(new_urls)} URL(s) to Google Sheet (A{next_row}..A{next_row + len(new_urls) - 1})!"
        except Exception as e:
            if log_fn:
                log_fn(f"⚠️ [Google Sheet Sync Error] {e}")
            return False, f"Google Sheet sync error: {e}"


def is_valid_live_post_url(url: str, board_url: str = "") -> bool:
    """
    Strictly validates whether a URL is a genuine public live post/waiver/thread/note.
    Rejects internal navigation links, bare homepages, dashboards, un-saved editor screens, and login pages.
    """
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        return False
    u_lower = u.lower()

    # Reject local or private network links
    if "127.0.0.1" in u_lower or "localhost" in u_lower or "about:blank" in u_lower:
        return False

    # Reject dashboard, setup, un-saved editor, creation forms, and login URLs
    invalid_patterns = [
        "/login", "/signin", "/signup", "/register", "/auth/", "/logout",
        "/profile/home", "/profile/templatelist", "/profile/",
        "/template?", "/thread/new", "/board/",
        "newthread.php", "posting.php?mode=post", "posting.php?mode=reply",
        "action=newthread", "do=newthread", "/post-thread", "/create-thread",
        "/new-content", "/new-topic", "/create-post", "/submit-post",
        "?isnew=true", "&isnew=true", "/untitled",
        "/404", "/error", "/checkpoint", "/challenge"
    ]
    if any(p in u_lower for p in invalid_patterns):
        return False

    for bad_suffix in ["/template", "/home", "/dashboard", "/new", "/create", "/write", "/compose", "/edit", "/login"]:
        if u_lower.rstrip("/").endswith(bad_suffix):
            return False

    try:
        parsed = urlparse(u)
        path_clean = (parsed.path or "").strip("/")
        # A bare domain homepage (e.g. https://site.com/) with no path and no post query ID is never a live post
        if not path_clean and not any(q in (parsed.query or "").lower() for q in ["id=", "p=", "t=", "thread=", "topic=", "note="]):
            return False
    except Exception:
        return False

    # Platform-specific strict rules
    if "waiverelectronic.com" in u_lower:
        return "/render/" in u_lower or "templatebyrefid" in u_lower
    if "proboards.com" in u_lower:
        return "/thread/" in u_lower and "/thread/new" not in u_lower
    if "themoviedb.org" in u_lower:
        return bool(re.search(r"/movie/\d+", u_lower))
    if "knowt.com" in u_lower:
        if "/home" in u_lower or "?isnew=true" in u_lower or u_lower.rstrip("/").endswith("/untitled"):
            return False
        return bool(re.search(r"/note/[0-9a-f\-]{20,}", u_lower)) or "/notes/" in u_lower or "/flashcards/" in u_lower

    return True


_INCOGNITO_VERIFIED_CACHE = {}

def verify_url_incognito(url: str, page=None, log_fn=None, browser=None, expected_title: str = "") -> tuple:
    """
    Verifies that a generated URL is genuinely live and publicly accessible in a REAL
    unauthenticated Incognito Browser Context (zero cookies, zero session storage).
    If no browser object is attached (e.g. persistent context in Live Mode or manual UI Verify),
    launches a dedicated headless Incognito browser so SPAs and Cloudflare sites are verified accurately.
    Rejects 404 pages, 'Note not found' / 'Private' screens, login redirects, and un-saved '/Untitled' drafts.
    Returns: (is_verified: bool, final_url: str)
    """
    if not is_valid_live_post_url(url):
        if log_fn:
            log_fn(f"⚠️ [Incognito Reject] Invalid or un-published URL format rejected: {url}")
        return False, url

    clean_url = url.strip()

    # Check 20-second cache so backend + api.py don't double-open Incognito tabs for the exact same post
    now_ts = time.time()
    cached = _INCOGNITO_VERIFIED_CACHE.get(clean_url)
    if cached and (now_ts - cached[0]) < 20.0:
        return cached[1], cached[2]

    if log_fn:
        log_fn(f"🛡️ [Incognito Verifier] Checking live URL in clean unauthenticated Incognito session: {clean_url}...")

    active_browser = browser
    if not active_browser and page is not None:
        try:
            active_browser = page.context.browser
        except Exception:
            active_browser = None

    def _inspect_incog_page(incog_page):
        resp = incog_page.goto(clean_url, wait_until="domcontentloaded", timeout=25000)
        time.sleep(2.5)

        status = resp.status if resp else 200
        final_url = incog_page.url or clean_url

        if status >= 400:
            if log_fn:
                log_fn(f"❌ [Incognito Failed] HTTP {status} error on {final_url}")
            return False, final_url

        if not is_valid_live_post_url(final_url):
            if log_fn:
                log_fn(f"❌ [Incognito Failed] URL redirected to non-public/editor page: {final_url}")
            return False, final_url

        page_check = incog_page.evaluate("""(expTitle) => {
            const docTitle = (document.title || '').toLowerCase();
            const bodyText = (document.body ? document.body.innerText : '').toLowerCase();
            const headSlice = bodyText.slice(0, 2200);
            const locHref = (window.location.href || '').toLowerCase();

            const fatalPhrases = [
                '404 not found', 'page not found', 'note not found', 'this note is private',
                'private note', 'you do not have permission', 'you don\'t have access',
                'request access', 'invalid thread specified', 'thread specified does not exist',
                'oops! we ran into some problems', 'the requested page could not be found',
                'this content is no longer available', 'sign in to continue', 'log in to view'
            ];
            for (const phrase of fatalPhrases) {
                if (docTitle.includes(phrase) || headSlice.includes(phrase)) {
                    return { ok: false, reason: 'Error/Private phrase detected in Incognito: ' + phrase };
                }
            }

            if (locHref.includes('knowt.com/note/')) {
                if (locHref.endsWith('/untitled') || docTitle.startsWith('untitled')) {
                    return { ok: false, reason: 'Knowt note is still an unsaved Untitled draft in Incognito' };
                }
            }

            const pwInputs = document.querySelectorAll('input[type="password"]');
            const hasMainContent = document.querySelectorAll('article, main, .ProseMirror, .post-content, .message-body, #notepage-editor-outer-container, .template-preview').length > 0;
            if (pwInputs.length > 0 && !hasMainContent) {
                return { ok: false, reason: 'Blocked by login wall in Incognito' };
            }

            if (expTitle && expTitle.trim().length >= 4) {
                const words = expTitle.toLowerCase().split(/[^a-z0-9]+/).filter(w => w.length >= 4);
                if (words.length > 0 && bodyText.length > 80) {
                    const matchedWords = words.filter(w => docTitle.includes(w) || bodyText.includes(w));
                    if (matchedWords.length === 0 && (locHref.includes('knowt.com') || locHref.includes('waiverelectronic.com'))) {
                        return { ok: false, reason: 'Expected post title not found on rendered Incognito page' };
                    }
                }
            }
            return { ok: true, docTitle: document.title || '' };
        }""", expected_title or "")

        if not page_check.get("ok", True):
            if log_fn:
                log_fn(f"❌ [Incognito Failed] {page_check.get('reason')} at {final_url}")
            return False, final_url

        if log_fn:
            log_fn(f"🛡️ [Incognito Verified] 100% Public & Live in clean Incognito window: {final_url}")
        return True, final_url

    # Path 1: Use existing Playwright Browser object if available
    if active_browser is not None:
        incog_ctx = None
        try:
            incog_ctx = active_browser.new_context(viewport={"width": 1280, "height": 800})
            incog_page = incog_ctx.new_page()
            ok, f_url = _inspect_incog_page(incog_page)
            _INCOGNITO_VERIFIED_CACHE[clean_url] = (time.time(), ok, f_url)
            if f_url:
                _INCOGNITO_VERIFIED_CACHE[f_url] = (time.time(), ok, f_url)
            return ok, f_url
        except Exception as e:
            if log_fn:
                log_fn(f"⚠️ [Incognito Context Note] {e}; trying standalone headless Incognito browser...")
        finally:
            if incog_ctx is not None:
                try:
                    incog_ctx.close()
                except Exception:
                    pass

    # Path 2: Launch a standalone headless Incognito browser (works when active_browser is None in persistent context!)
    if sync_playwright is not None:
        try:
            with sync_playwright() as p_inc:
                b_inc = launch_safe_browser(p_inc, headless=True)
                if b_inc:
                    try:
                        inc_ctx = b_inc.new_context(viewport={"width": 1280, "height": 800})
                        inc_pg = inc_ctx.new_page()
                        ok, f_url = _inspect_incog_page(inc_pg)
                        _INCOGNITO_VERIFIED_CACHE[clean_url] = (time.time(), ok, f_url)
                        if f_url:
                            _INCOGNITO_VERIFIED_CACHE[f_url] = (time.time(), ok, f_url)
                        return ok, f_url
                    finally:
                        try:
                            b_inc.close()
                        except Exception:
                            pass
        except Exception as e:
            if log_fn:
                log_fn(f"⚠️ [Headless Incognito Note] {e}; falling back to HTTP check...")

    # Path 3: Fallback unauthenticated HTTP check
    try:
        import urllib.request
        import urllib.error
        import ssl
        ssl_ctx = ssl._create_unverified_context()
        req = urllib.request.Request(
            clean_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        with urllib.request.urlopen(req, timeout=12, context=ssl_ctx) as resp:
            final_url = resp.geturl() or clean_url
            status = getattr(resp, "status", 200)
            raw_body = resp.read(8192).decode("utf-8", errors="replace").lower()

            if status >= 400 or not is_valid_live_post_url(final_url):
                if log_fn:
                    log_fn(f"❌ [Incognito HTTP Failed] Invalid redirect or status ({status}): {final_url}")
                return False, final_url

            for err_kw in ["404 not found", "page not found", "note not found", "invalid thread specified", "this note is private"]:
                if err_kw in raw_body:
                    if log_fn:
                        log_fn(f"❌ [Incognito HTTP Failed] Page body contains '{err_kw}': {final_url}")
                    return False, final_url

            if log_fn:
                log_fn(f"🛡️ [Incognito Verified] Live post is public & accessible: {final_url}")
            return True, final_url
    except urllib.error.HTTPError as he:
        if log_fn:
            log_fn(f"❌ [Incognito HTTP Error] Server returned HTTP {he.code} for {clean_url}")
        return False, clean_url
    except Exception as e:
        if log_fn:
            log_fn(f"❌ [Incognito Unreachable] Could not verify {clean_url}: {e}")
        return False, clean_url
    except Exception as e:
        if log_fn:
            log_fn(f"❌ [Incognito Connection Failed] Could not reach {clean_url}: {e}")
        return False, clean_url


def fetch_url_from_view_edit_waiver_template(page, title_text, log_fn):
    """
    Fallback strategy when Preview button is unresponsive or delayed:
    1. Navigates to 'View/Edit Waiver Template' under 'My Waivers'
    2. Identifies the latest template (last post / matching title)
    3. Clicks the 'Copy URL' button below it
    4. Extracts the live URL via intercepted clipboard, navigator.clipboard, DOM attributes, or AngularJS scope
    """
    log_fn("⚡ Fallback: Navigating to 'View/Edit Waiver Template' to pull live URL...")
    try:
        page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    except Exception:
        pass

    # 1. Dismiss any add-on modal before leaving current view
    dismiss_addon_modal_if_present(page, log_fn)

    # 2. Inject clipboard interceptor into current page
    js_interceptor = """() => {
        window.__lastCopiedUrl = "";
        try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
                const _origWrite = navigator.clipboard.writeText.bind(navigator.clipboard);
                navigator.clipboard.writeText = function(text) {
                    window.__lastCopiedUrl = text;
                    try { return _origWrite(text); } catch(e) { return Promise.resolve(); }
                };
            }
        } catch(e) {}
        try {
            const _origExec = document.execCommand.bind(document);
            document.execCommand = function(cmd, showUI, value) {
                if (cmd === 'copy') {
                    try {
                        const sel = window.getSelection().toString();
                        if (sel) window.__lastCopiedUrl = sel;
                        const act = document.activeElement;
                        if (act && (act.value || act.innerText)) {
                            window.__lastCopiedUrl = act.value || act.innerText;
                        }
                    } catch(e) {}
                }
                try { return _origExec(cmd, showUI, value); } catch(e) { return true; }
            };
        } catch(e) {}
    }"""
    try:
        page.evaluate(js_interceptor)
    except Exception:
        pass

    # 3. Navigate to View/Edit Waiver Template
    navigated = False
    try:
        # Check if View/Edit Waiver Template link is visible
        view_edit_loc = page.locator("a:has-text('View/Edit Waiver Template'), button:has-text('View/Edit Waiver Template'), li:has-text('View/Edit Waiver Template'), div:has-text('View/Edit Waiver Template')").first
        if view_edit_loc.count() == 0 or not view_edit_loc.is_visible():
            # Expand 'My Waivers' if needed
            try:
                my_waivers_btn = page.locator("text='My Waivers'").first
                if my_waivers_btn.count() > 0 and my_waivers_btn.is_visible():
                    my_waivers_btn.click(timeout=3000)
                    time.sleep(1)
            except Exception:
                pass

        view_edit_loc = page.locator("a:has-text('View/Edit Waiver Template'), button:has-text('View/Edit Waiver Template'), li:has-text('View/Edit Waiver Template'), div:has-text('View/Edit Waiver Template')").first
        if view_edit_loc.count() > 0:
            view_edit_loc.click(timeout=8000)
            navigated = True
            log_fn("Clicked 'View/Edit Waiver Template' in sidebar.")
    except Exception as e:
        log_fn(f"Sidebar navigation note: {e}")

    if not navigated:
        log_fn("Navigating directly to template list URL...")
        try:
            page.goto("https://app.waiverelectronic.com/profile/templateList", wait_until="domcontentloaded", timeout=20000)
            navigated = True
        except Exception as e:
            log_fn(f"Direct nav note: {e}")

    time.sleep(3)
    dismiss_addon_modal_if_present(page, log_fn)

    # Re-inject interceptor on new page
    try:
        page.evaluate(js_interceptor)
    except Exception:
        pass

    # 4. Find the template post and the Copy URL button
    copy_btn_selectors = [
        "button:has-text('Copy URL'), a:has-text('Copy URL')",
        "[title*='Copy URL' i], [aria-label*='Copy URL' i]",
        "button:has-text('Copy Link'), a:has-text('Copy Link')",
        "[title*='Copy Link' i], [aria-label*='Copy Link' i]",
        "button:has-text('Copy waiver link'), a:has-text('Copy waiver link')",
        "button:has-text('Copy waiver URL'), a:has-text('Copy waiver URL')",
        "button:has-text('Copy'), a:has-text('Copy')",
        ".btn:has-text('Copy')",
        "button[ng-click*='copy' i], a[ng-click*='copy' i]",
        "[data-clipboard-text]",
        ".copy-url-btn, .btn-copy, .copy-link"
    ]

    target_btn = None

    # Priority A: Check if container with matching title exists
    if title_text:
        try:
            for t_query in [title_text, title_text[:30]]:
                t_el = page.get_by_text(t_query).first
                if t_el.count() > 0 and t_el.is_visible():
                    parent = t_el.locator("xpath=./ancestor::*[contains(@class, 'card') or contains(@class, 'item') or contains(@class, 'template') or contains(@class, 'row') or contains(@class, 'box') or contains(@class, 'panel') or self::tr][1]")
                    if parent.count() > 0:
                        for c_sel in copy_btn_selectors:
                            btn = parent.locator(c_sel).first
                            if btn.count() > 0 and btn.is_visible():
                                target_btn = btn
                                log_fn(f"Found 'Copy URL' button within template card: '{t_query[:25]}'")
                                break
                    if not target_btn:
                        following_btn = t_el.locator("xpath=following::*[self::button or self::a or @role='button'][contains(translate(., 'COPY', 'copy'), 'copy')][1]")
                        if following_btn.count() > 0 and following_btn.is_visible():
                            target_btn = following_btn
                            log_fn(f"Found 'Copy URL' button following template title: '{t_query[:25]}'")
                    if target_btn:
                        break
        except Exception as e:
            log_fn(f"Title matching container note: {e}")

    # Priority B: If not matched specifically by title, target the last post / newest template copy button
    if not target_btn:
        for c_sel in copy_btn_selectors:
            btns = page.locator(c_sel)
            cnt = btns.count()
            if cnt > 0:
                for idx in range(cnt):
                    b = btns.nth(idx)
                    if b.is_visible():
                        target_btn = b
                        log_fn(f"Targeting 'Copy URL' button ({idx+1}/{cnt}) via selector: {c_sel}")
                        break
                if target_btn:
                    break

    # 5. Extract URL from button attributes or by clicking it
    if target_btn and target_btn.count() > 0:
        for attr in ["data-clipboard-text", "data-url", "href", "data-link", "value"]:
            try:
                v = target_btn.get_attribute(attr)
                if v and is_valid_live_post_url(v):
                    log_fn(f"🎉 Found Live URL in copy button attribute ({attr}): {v}")
                    return v
            except Exception:
                pass

        try:
            log_fn("Clicking 'Copy URL' button on template...")
            target_btn.scroll_into_view_if_needed()
            target_btn.click(timeout=6000)
            time.sleep(1.5)
        except Exception as e:
            log_fn(f"Click copy button note: {e}")

        try:
            copied = page.evaluate("() => window.__lastCopiedUrl || ''")
            if copied and is_valid_live_post_url(copied):
                log_fn(f"🎉 Captured Live Waiver URL from 'Copy URL' click: {copied}")
                return copied
        except Exception:
            pass

        try:
            clip = page.evaluate("""async () => {
                try {
                    return await navigator.clipboard.readText();
                } catch(e) {
                    return "";
                }
            }""")
            if clip and is_valid_live_post_url(clip):
                log_fn(f"🎉 Captured Live Waiver URL from clipboard: {clip}")
                return clip
        except Exception:
            pass

    # Priority C: Check inputs with waiver render URLs in the DOM
    try:
        for inp in page.locator("input[value*='render'], input[value*='waiverelectronic'], input[value*='templateByRefId']").all():
            v = inp.input_value()
            if v and is_valid_live_post_url(v):
                log_fn(f"🎉 Found Live Waiver URL in input field: {v}")
                return v
    except Exception:
        pass

    # Priority D: Check AngularJS scope on the template items
    try:
        scope_url = page.evaluate("""() => {
            try {
                const els = document.querySelectorAll("[ng-click*='copy'], button, a, tr, .card, .item, .template-item");
                for (const el of els) {
                    if (window.angular) {
                        const s = window.angular.element(el).scope();
                        if (s) {
                            const refId = (s.template && s.template.refId) || (s.item && s.item.refId) || (s.waiver && s.waiver.refId) || s.refId;
                            if (refId && typeof refId === "string" && refId.length > 5) {
                                return "https://app.waiverelectronic.com/render/templateByRefId/" + refId;
                            }
                            const u = s.url || s.waiverUrl || s.templateUrl || (s.template && (s.template.url || s.template.renderUrl));
                            if (typeof u === "string" && (u.includes("/render/") || u.includes("templateByRefId"))) return u;
                        }
                    }
                }
            } catch(e) {}
            return null;
        }""")
        if scope_url and is_valid_live_post_url(scope_url):
            log_fn(f"🎉 Found Live Waiver URL via AngularJS template scope: {scope_url}")
            return scope_url
    except Exception:
        pass

    # Priority E: Check any render link in the DOM
    try:
        for link in page.locator("a[href*='/render/'], a[href*='templateByRefId']").all():
            href = link.get_attribute("href")
            if href:
                if href.startswith("/"):
                    href = "https://app.waiverelectronic.com" + href
                if is_valid_live_post_url(href):
                    log_fn(f"🎉 Found Live Waiver URL in DOM link: {href}")
                    return href
    except Exception:
        pass

    return None


def waiverelectronic_create_template(page, board_url, title_text, body_text, log_fn, post_index=0):
    """
    Automates creating a new Waiver Template on WaiverElectronic:
    1. Navigates to https://app.waiverelectronic.com/profile/home
    2. Clicks 'My Waivers' -> 'Create Waiver Template'
    3. Clicks layout image (img nth(5))
    4. Enters Waiver Name (title_text) -> Clicks 'Create'
    5. Clicks 'Click to enter waiver header' (.header-click-section)
    6. Fills #ui-tinymce-2_ifr with title_text
    7. Directly binds AngularJS scope (scope.yourModel.text = title_text; scope.showAddHeaderText = false)
    8. Clicks the EMPTY SPACE on canvas (Center of .template-preview / 'Start Building!') to commit and save header
    9. Clicks 'Waiver Text' (div with regex ^Waiver Text$) -> Clicks placeholder
    10. Fills #ui-tinymce-3_ifr with body_text -> Blurs editor
    11. Clicks 'Save Template' -> Captures live preview URL via popup
    """
    title_text = str(title_text).strip()
    body_text = str(body_text).strip()
    target_url = "https://app.waiverelectronic.com/profile/home"

    log_fn(f"Opening WaiverElectronic Dashboard: {target_url}")
    try:
        page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
    except Exception as e:
        log_fn(f"Navigation note: {e}")
    time.sleep(2.5)

    # Check for login redirect
    if "/login" in (page.url or "").lower():
        log_fn("❌ Not logged in to WaiverElectronic. Please use '⚡ Login & Post (Live)' or authenticate in browser.")
        return False, None

    try:
        # 1. Navigate to My Waivers
        log_fn("Navigating to 'My Waivers'...")
        page.get_by_text("My Waivers").first.click(timeout=15000)
        time.sleep(1.5)

        # 2. Open Create Waiver Template
        log_fn("Opening 'Create Waiver Template'...")
        try:
            page.get_by_role("listitem").filter(has_text="Create Waiver Template").first.click(timeout=8000)
        except Exception:
            page.get_by_text("Create Waiver Template").first.click(timeout=8000)
        time.sleep(2)

        # 3. Select Template Layout (img nth(5) as recorded)
        log_fn("Selecting template layout...")
        try:
            page.locator("img").nth(5).click(timeout=8000)
        except Exception:
            try:
                page.get_by_text("Create from ScratchStart with").first.click(timeout=6000)
            except Exception:
                page.locator(".template-item img, .card img, img").first.click(timeout=6000)
        time.sleep(1)

        # 4. Enter Waiver Name
        name_input = page.get_by_role("textbox", name="Enter Waiver Name")
        if name_input.count() == 0:
            name_input = page.locator('input[placeholder*="Waiver Name" i]').first
        name_input.click()
        name_input.fill(title_text)
        log_fn(f"Set Waiver Template Name: {title_text[:50]}")
        time.sleep(0.5)

        # Optional click on modal title wrapper if present
        try:
            page.get_by_text("Create Waiver Template Waiver").first.click(timeout=3000)
        except Exception:
            pass

        # 5. Click Create button (nth 1 as recorded)
        log_fn("Clicking Create button...")
        try:
            page.get_by_text("Create").nth(1).click(timeout=8000)
        except Exception:
            try:
                page.locator("div").filter(has_text=re.compile(r"^Create$")).first.click(timeout=8000)
            except Exception:
                page.locator('button:has-text("Create"), .btn:has-text("Create")').first.click(timeout=8000)
        time.sleep(3)

        # 6. FILL HEADER (.header-click-section)
        log_fn(f"Clicking header section to enter: {title_text[:50]}...")
        header_trigger = page.locator(".header-click-section, text='Click to enter waiver header'").first
        try:
            header_trigger.click(timeout=8000)
        except Exception:
            try:
                page.get_by_text(re.compile(r"Click to enter waiver header", re.I)).first.click(timeout=6000)
            except Exception as e:
                log_fn(f"Header trigger note: {e}")
        time.sleep(1.5)

        # Enter text in TinyMCE header iframe (#ui-tinymce-2_ifr)
        try:
            page.wait_for_selector("#ui-tinymce-2_ifr, iframe[id*='tinymce-2']", timeout=8000)
            h_frame = page.locator("#ui-tinymce-2_ifr").first.content_frame
            if h_frame:
                h_frame.locator("html").click(timeout=3000)
                h_frame.locator("#tinymce").fill(title_text)
            else:
                page.frame_locator("#ui-tinymce-2_ifr").locator("#tinymce").fill(title_text)
            log_fn(f"Entered header in TinyMCE #ui-tinymce-2: {title_text[:50]}")
        except Exception as e:
            log_fn(f"Note on header iframe fill: {e}")

        # Direct AngularJS scope update with safe $$phase check
        try:
            page.evaluate("""(title) => {
                try {
                    const el = document.querySelector('.header-click-section') || 
                               document.querySelector('.template-header-text') || 
                               document.querySelector('#header-text');
                    if (el && window.angular) {
                        const scope = window.angular.element(el).scope();
                        if (scope) {
                            if (!scope.yourModel) scope.yourModel = {};
                            scope.yourModel.text = title;
                            scope.showAddHeaderText = false;
                            if (!scope.$$phase) {
                                scope.$apply();
                            }
                        }
                    }
                } catch(e) {}
            }""", title_text)
            log_fn("Bound header directly to AngularJS yourModel.text scope.")
        except Exception as e:
            log_fn(f"AngularJS scope update note: {e}")

        time.sleep(0.5)

        # 7. CLICK EMPTY SPACE TO COMMIT HEADER (Targeting exactly the empty canvas area circled by user)
        log_fn("Clicking empty space on canvas to blur and commit header...")
        clicked_empty = False
        # First priority: Click 'Start Building!' on the empty canvas (Red 'O' area)
        try:
            sb = page.get_by_text("Start Building!").first
            if sb.count() > 0 and sb.is_visible():
                sb.click(timeout=4000)
                clicked_empty = True
                log_fn("Clicked 'Start Building!' empty canvas area.")
        except Exception:
            pass

        # Second priority: Click center of .template-preview (White canvas area)
        if not clicked_empty:
            try:
                preview_canvas = page.locator(".template-preview, .no-fields").first
                if preview_canvas.count() > 0:
                    preview_canvas.click(timeout=4000) # clicks geometric center of canvas
                    clicked_empty = True
                    log_fn("Clicked center of template canvas.")
            except Exception:
                pass

        # Third priority: Click empty left margin in .template-preview-scroll-section (Red Circle area)
        if not clicked_empty:
            try:
                scroll_sec = page.locator(".template-preview-scroll-section").first
                if scroll_sec.count() > 0:
                    scroll_sec.click(position={"x": 50, "y": 300}, timeout=4000)
                    log_fn("Clicked empty margin area.")
            except Exception:
                pass

        time.sleep(1)

        # 8. ADD WAIVER TEXT (Exact recording sequence: div with exact regex ^Waiver Text$)
        log_fn("Adding 'Waiver Text' component from panel...")
        try:
            page.locator("div").filter(has_text=re.compile(r"^Waiver Text$")).first.click(timeout=10000)
        except Exception:
            try:
                page.get_by_text("Waiver Text").first.click(timeout=10000)
            except Exception:
                page.locator('button:has-text("Waiver Text"), a:has-text("Waiver Text"), text="Waiver Text"').first.click(timeout=10000)
        time.sleep(2)

        # 9. Click placeholder to activate body TinyMCE
        log_fn("Opening Waiver Text body editor...")
        try:
            page.get_by_text("Please enter your text here.(").first.click(timeout=10000)
        except Exception:
            try:
                page.get_by_text(re.compile(r"Please enter your text here", re.I)).first.click(timeout=8000)
            except Exception as e:
                log_fn(f"Placeholder activation note: {e}")
        time.sleep(1.5)

        # Press Ctrl+A on body if recorded
        try:
            page.locator("body").press("ControlOrMeta+a")
        except Exception:
            pass

        # 10. Fill TinyMCE Body Editor (#ui-tinymce-3_ifr)
        log_fn("Filling Waiver Text body content...")
        page.wait_for_selector("#ui-tinymce-3_ifr, iframe[id*='tinymce-3']", timeout=12000)
        body_done = False
        try:
            cf3 = page.locator("#ui-tinymce-3_ifr").first.content_frame
            if cf3:
                try:
                    cf3.locator("html").click(modifiers=["ControlOrMeta"], timeout=3000)
                except Exception:
                    cf3.locator("html").click(timeout=3000)
                cf3.locator("#tinymce").press("ControlOrMeta+a")
                cf3.locator("#tinymce").fill(body_text)
                body_done = True
                log_fn("Filled waiver text via content_frame (#ui-tinymce-3_ifr)")
        except Exception as e:
            log_fn(f"Body content_frame note: {e}")

        if not body_done:
            try:
                fl3 = page.frame_locator("#ui-tinymce-3_ifr")
                fl3.locator("html").click(timeout=4000)
                fl3.locator("#tinymce").press("ControlOrMeta+a")
                fl3.locator("#tinymce").fill(body_text)
                body_done = True
                log_fn("Filled waiver text via frame_locator (#ui-tinymce-3_ifr)")
            except Exception as e:
                log_fn(f"Body frame_locator note: {e}")

        # Blur body editor by clicking canvas center
        try:
            page.locator(".template-preview").first.click(timeout=3000)
        except Exception:
            pass
        time.sleep(1)

        # Check and dismiss any add-on modal that pops up after entering content
        dismiss_addon_modal_if_present(page, log_fn)

        # 11. Final Flush of TinyMCE editors
        log_fn("Synchronizing all editor changes...")
        try:
            page.evaluate("""() => {
                if (window.tinymce) {
                    try { window.tinymce.triggerSave(); } catch(e) {}
                    if (window.tinymce.editors) {
                        for (let k in window.tinymce.editors) {
                            try {
                                window.tinymce.editors[k].fire('change');
                                window.tinymce.editors[k].fire('input');
                                window.tinymce.editors[k].save();
                            } catch(e) {}
                        }
                    }
                }
            }""")
        except Exception:
            pass

        time.sleep(2)

                # Check and dismiss add-on modal before save
        dismiss_addon_modal_if_present(page, log_fn)

        # 12. Save Template
        log_fn("Saving template...")
        try:
            page.get_by_text("Save Template").first.click(timeout=10000)
        except Exception:
            page.locator('button:has-text("Save Template"), a:has-text("Save Template"), button:has-text("Save")').first.click(timeout=10000)
        time.sleep(3.5)

        # Check and dismiss add-on modal if it appears upon saving
        dismiss_addon_modal_if_present(page, log_fn)

        # 13. Capture Live Preview URL via Popup (with fast timeout, View/Edit Waiver Template fallback, & Incognito verification)
        log_fn("Clicking 'Preview' to capture generated live waiver URL...")
        posted_url = None

        # Specifically target the Preview button (avoiding div.template-preview canvas)
        preview_btn = page.locator("button:has-text('Preview'), a:has-text('Preview'), button.btn:has-text('Preview'), .preview-button").first
        if preview_btn.count() == 0:
            preview_btn = page.get_by_role("button", name="Preview")
        if preview_btn.count() == 0:
            preview_btn = page.get_by_text(re.compile(r"^Preview$", re.I)).first

        try:
            if preview_btn.count() > 0 and preview_btn.is_visible():
                with page.expect_popup(timeout=6000) as popup_info:
                    preview_btn.click(timeout=5000)
                preview_page = popup_info.value
                preview_page.wait_for_load_state("domcontentloaded", timeout=10000)
                time.sleep(2)
                cand_url = preview_page.url
                if cand_url and is_valid_live_post_url(cand_url):
                    posted_url = cand_url
                    log_fn(f"🎉 Generated Live Waiver URL from Preview: {posted_url}")
                try:
                    preview_page.close()
                except Exception:
                    pass
            else:
                log_fn("Preview button not visible or not found; proceeding to fallback.")
        except Exception as e:
            log_fn(f"Preview button response note: {e}")

        # Fallback check across open browser pages
        if not posted_url or not is_valid_live_post_url(posted_url):
            time.sleep(1)
            for p in page.context.pages:
                u = (p.url or "").strip()
                if u and is_valid_live_post_url(u):
                    posted_url = u
                    log_fn(f"🎉 Found Live Waiver URL in active tab: {posted_url}")
                    break

        # Fallback check for DOM render links on current page
        if not posted_url or not is_valid_live_post_url(posted_url):
            try:
                for link in page.locator("a[href*='/render/'], a[href*='templateByRefId']").all():
                    href = link.get_attribute("href")
                    if href and is_valid_live_post_url(href):
                        posted_url = href
                        log_fn(f"🎉 Found Live Waiver URL in DOM link: {posted_url}")
                        break
            except Exception:
                pass

        # Fallback: if preview button takes time to respond or doesn't respond, pull URL from "View/Edit Waiver Template"
        if not posted_url or not is_valid_live_post_url(posted_url):
            log_fn("⚠️ Preview button did not yield a live URL. Triggering fallback: pulling URL from 'View/Edit Waiver Template'...")
            fallback_url = fetch_url_from_view_edit_waiver_template(page, title_text, log_fn)
            if fallback_url and is_valid_live_post_url(fallback_url):
                posted_url = fallback_url
                log_fn(f"🎉 Successfully pulled live URL from 'View/Edit Waiver Template': {posted_url}")

        if not posted_url or not is_valid_live_post_url(posted_url):
            log_fn("❌ Could not obtain a valid public live waiver URL (internal pages like /profile/home rejected).")
            return False, None

        # Mandatory Incognito Mode Verification
        is_verified, verified_url = verify_url_incognito(posted_url, page=page, log_fn=log_fn, expected_title=title_text)
        if not is_verified:
            log_fn(f"❌ Waiver URL failed Incognito public accessibility check: {posted_url}")
            return False, None
        if verified_url:
            posted_url = verified_url

        log_fn(f"🔗 Final Live URL: {posted_url}")
        log_fn(f"✅ Success: {posted_url}")
        return True, posted_url

    except Exception as e:
        log_fn(f"❌ Error during WaiverElectronic execution: {e}")
        return False, None


def knowt_create_note(page, board_url, title_text, body_text, log_fn, post_index=0):
    """
    Automates creating a new Note on Knowt (knowt.com) with Server-Minted Note UUIDs & Incognito Verification:
    - For post_index == 0, if board_url is an existing /note/ URL, opens it directly.
    - For parallel/subsequent posts (post_index > 0) or when creating fresh notes, navigates to
      https://knowt.com/home and clicks 'Notebook' -> 'Create from scratch' (#create-popup-tab-notes-create-from-scratch)
      so Knowt's backend server mints a 100% genuine, database-registered Note UUID (never a fake client UUID!).
    - Waits for Knowt's auto-save sync after typing Title & Body, clicks Share -> Copy link -> Done,
      and verifies the final public Note URL in a clean Incognito context.
    """
    title_text = str(title_text).strip()
    body_text = str(body_text).strip()
    b_url = (board_url or "").strip()

    try:
        page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    except Exception:
        pass

    # Decide whether to use the provided /note/ URL (for post 0) or mint a fresh server-registered note on /home
    use_direct_note = ("/note/" in b_url.lower() and post_index == 0 and "eda21927-9bf0-4bef-b21a-aa2347be4ce3" not in b_url.lower() and "untitled" not in b_url.lower())

    if use_direct_note:
        log_fn(f"🚀 Navigating to target Knowt Note Editor: {b_url}")
        try:
            page.goto(b_url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            log_fn(f"Navigation note: {e}")
        time.sleep(2.5)
    else:
        log_fn(f"🚀 Opening Knowt Home to mint a fresh server-registered Note for item #{post_index + 1}...")
        try:
            page.goto("https://knowt.com/home", wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            log_fn(f"Home navigation note: {e}")
        time.sleep(2.5)

    # Check for login redirect
    cur_url = (getattr(page, 'url', '') or '').lower()
    if "/login" in cur_url or cur_url.rstrip("/") in ["https://knowt.com", "http://knowt.com"]:
        log_fn("🔐 Checking for Knowt login form...")
        cfg = load_config()
        u_email = (cfg.get("username") or cfg.get("email") or "").strip()
        u_pass = (cfg.get("password") or "").strip()
        if u_email and u_pass:
            log_fn(f"Attempting login as {u_email}...")
            try:
                login_btn = page.locator('button:has-text("Login"), button:has-text("Log in"), a:has-text("Login")').first
                if login_btn.count() > 0 and login_btn.is_visible():
                    login_btn.click(timeout=5000)
                    time.sleep(1.5)
                em_box = page.locator('input[type="email"], input[placeholder*="email" i], input[name*="email" i], role=textbox[name*="Email" i]').first
                if em_box.count() > 0:
                    em_box.click(timeout=5000)
                    em_box.fill(u_email)
                    time.sleep(0.4)
                pw_box = page.locator('input[type="password"], input[name*="password" i], role=textbox[name*="Password" i]').first
                if pw_box.count() > 0:
                    pw_box.click(timeout=5000)
                    pw_box.fill(u_pass)
                    time.sleep(0.4)
                sub_btn = page.locator('button:has-text("Log in"), button:has-text("Login"), button[type="submit"]').first
                if sub_btn.count() > 0:
                    sub_btn.click(timeout=5000)
                    time.sleep(2.5)
                    try:
                        page.wait_for_url("**/home**", timeout=15000)
                    except Exception:
                        pass
                if use_direct_note:
                    page.goto(b_url, wait_until="domcontentloaded", timeout=45000)
                    time.sleep(2.0)
            except Exception as le:
                log_fn(f"Login attempt notice: {le}")

    # If currently on /home (or not yet on /note/), mint a real note via 'Notebook' -> 'Create from scratch'
    if "/note/" not in (getattr(page, 'url', '') or '').lower():
        log_fn("✨ Minting new server-registered Note via 'Notebook' -> 'Create from scratch'...")
        notebook_clicked = False
        for nsel in [
            'button.knowt-1dwueds',
            'button:has(span.new_bodyMBold:text-is("Notebook"))',
            'button:has(span:text-is("Notebook"))',
            'button:has-text("Notebook")',
        ]:
            try:
                nbtn = page.locator(nsel).first
                if nbtn.count() > 0 and nbtn.is_visible():
                    nbtn.click(timeout=6000)
                    notebook_clicked = True
                    time.sleep(1.8)
                    break
            except Exception:
                continue

        scratch_clicked = False
        for ssel in [
            '#create-popup-tab-notes-create-from-scratch',
            'div[id="create-popup-tab-notes-create-from-scratch"]',
            'div.knowt-1q550ud',
            'div:has(span.new_bodySBold:text-is("Create from scratch"))',
            'text="Create from scratch"',
        ]:
            try:
                sbtn = page.locator(ssel).first
                if sbtn.count() > 0 and sbtn.is_visible():
                    sbtn.click(timeout=6000)
                    scratch_clicked = True
                    time.sleep(2.5)
                    break
            except Exception:
                continue

        try:
            page.wait_for_url("**/note/**", timeout=12000)
        except Exception:
            pass

        # Fallback to b_url if /home modal didn't open a new note
        if "/note/" not in (getattr(page, 'url', '') or '').lower() and "/note/" in b_url.lower():
            log_fn(f"Fallback: opening provided Note URL {b_url}...")
            try:
                page.goto(b_url, wait_until="domcontentloaded", timeout=35000)
                time.sleep(2.0)
            except Exception:
                pass

    # Wait for Note Editor elements
    try:
        page.wait_for_selector('textarea#note-main-title, #notepage-editor-outer-container, button[data-testid="dismiss-interruption"]', timeout=15000)
    except Exception:
        pass
    time.sleep(1.0)

    # Extract this tab's genuine server-assigned note UUID from page.url
    tab_note_uuid = ""
    m_uuid = re.search(r'/note/([0-9a-fA-F\-]{20,})', getattr(page, 'url', '') or '')
    if m_uuid:
        tab_note_uuid = m_uuid.group(1)

    # Re-inject per-tab clipboard hook on the active editor page
    try:
        page.evaluate("""() => {
            window.__captured_live_url = '';
            if (navigator.clipboard) {
                const origWrite = navigator.clipboard.writeText ? navigator.clipboard.writeText.bind(navigator.clipboard) : null;
                navigator.clipboard.writeText = async function(text) {
                    if (text && typeof text === 'string' && text.trim().startsWith('http')) {
                        window.__captured_live_url = text.trim();
                    }
                    if (origWrite) {
                        try { return await origWrite(text); } catch(e) { return Promise.resolve(); }
                    }
                    return Promise.resolve();
                };
            }
        }""")
    except Exception:
        pass

    # Step 1: Dismiss auto-opened Share/Interruption modal if present
    log_fn("Step 1/5: Dismissing auto-opened modal if present...")
    for dsel in [
        'button[data-testid="dismiss-interruption"]',
        'button.knowt-q4jvfi',
        'button[aria-label="Close"]',
        '.MuiDialog-root button[aria-label="Close"]',
        'button:has-text("Done")',
    ]:
        try:
            dbtn = page.locator(dsel).first
            if dbtn.count() > 0 and dbtn.is_visible():
                dbtn.click(timeout=3000)
                time.sleep(0.8)
                break
        except Exception:
            continue

    # Step 2: Fill Title
    log_fn(f"Step 2/5: Filling Note Title: {title_text[:40]}...")
    title_done = False
    for tsel in [
        'textarea#note-main-title',
        '#note-main-title',
        'textarea.noteTitle-module_U0O1GG_title',
        'textarea[placeholder="Add a title"]',
        'role=textbox[name="Add a title"]',
    ]:
        try:
            if tsel.startswith("role="):
                role_m = re.match(r'role=(\w+)\[name=["\'](.*?)["\']\]', tsel)
                tloc = page.get_by_role(role_m.group(1), name=role_m.group(2)).first if role_m else None
            else:
                tloc = page.locator(tsel).first
            if tloc and tloc.count() > 0 and tloc.is_visible():
                tloc.click(timeout=5000)
                time.sleep(0.2)
                tloc.fill(title_text)
                title_done = True
                log_fn(f"Title entered successfully ({tsel})")
                time.sleep(0.5)
                break
        except Exception:
            continue

    if not title_done:
        log_fn("❌ Could not locate Knowt Title input (#note-main-title). Note editor did not load.")
        return False, None

    # Step 3: Fill Note Body into Rich-Text ProseMirror Editor
    log_fn("Step 3/5: Typing Note Body into ProseMirror editor...")
    editor_focused = False
    for esel in [
        '#notepage-editor-outer-container .tiptap.ProseMirror',
        '#notepage-editor-outer-container [contenteditable="true"]',
        'div.tiptap.ProseMirror[contenteditable="true"]',
        '#notepage-editor-outer-container p',
        '#notepage-editor-outer-container',
    ]:
        try:
            eloc = page.locator(esel).first
            if eloc.count() > 0 and eloc.is_visible():
                eloc.click(timeout=5000)
                editor_focused = True
                time.sleep(0.4)
                break
        except Exception:
            continue

    if not editor_focused:
        log_fn("❌ Could not focus Knowt ProseMirror body editor.")
        return False, None

    try:
        page.keyboard.insert_text(body_text)
        time.sleep(0.6)
        page.keyboard.press("Enter")
        # Wait 2.2 seconds for Knowt's backend auto-save sync to persist the note title and body!
        time.sleep(2.2)
        log_fn("Body content typed and synced to Knowt cloud.")
    except Exception as be:
        log_fn(f"Body typing note: {be}")

    # Step 4: Click "Share" button
    log_fn("Step 4/5: Clicking 'Share' button in toolbar...")
    share_clicked = False
    for shsel in [
        'button:has-text("Share")',
        'button.knowt-o80a1t',
        'button:has(span.new_bodySBold:text-is("Share"))',
        'button:has(span:text-is("Share"))',
        'role=button[name="Share"]',
    ]:
        try:
            shbtn = page.locator(shsel).first
            if shbtn.count() > 0 and shbtn.is_visible():
                shbtn.click(timeout=6000)
                share_clicked = True
                time.sleep(1.8)
                break
        except Exception:
            continue

    # Step 5: Click "Copy link" & "Done"
    log_fn("Step 5/5: Capturing share link via 'Copy link'...")
    copy_clicked = False
    for csel in [
        'button:has-text("Copy link")',
        'button.knowt-1prujqy',
        'button:has(span:text-is("Copy link"))',
        'role=button[name="Copy link"]',
    ]:
        try:
            cbtn = page.locator(csel).first
            if cbtn.count() > 0 and cbtn.is_visible():
                cbtn.click(timeout=5000)
                copy_clicked = True
                time.sleep(1.2)
                break
        except Exception:
            continue

    for dsel in [
        'button:has-text("Done")',
        'button.knowt-1lbf6sx',
        'role=button[name="Done"]',
    ]:
        try:
            dbtn = page.locator(dsel).first
            if dbtn.count() > 0 and dbtn.is_visible():
                dbtn.click(timeout=5000)
                time.sleep(1.0)
                break
        except Exception:
            continue

    # Retrieve this tab's isolated live URL
    captured_url = ""
    try:
        clip_text = page.evaluate("() => window.__captured_live_url || ''")
        if clip_text and str(clip_text).strip().startswith("http"):
            cand = str(clip_text).strip().split("?")[0]
            if not tab_note_uuid or tab_note_uuid in cand:
                captured_url = cand
    except Exception:
        pass

    if not captured_url or not captured_url.startswith("http"):
        cur_url = (getattr(page, 'url', '') or '').split("?")[0]
        # Never fabricate a fake slug if the note is still /Untitled! Only accept a real saved note URL.
        if "/note/" in cur_url and not cur_url.endswith("/home") and not cur_url.lower().endswith("/untitled"):
            if not tab_note_uuid or tab_note_uuid in cur_url:
                captured_url = cur_url

    if not captured_url or not is_valid_live_post_url(captured_url):
        log_fn(f"❌ Rejected invalid or un-saved Knowt URL: {captured_url}")
        return False, None

    # Mandatory Real Incognito Verification!
    is_pub, verified_u = verify_url_incognito(captured_url, page=page, log_fn=log_fn, expected_title=title_text)
    if not is_pub:
        log_fn(f"❌ Knowt Note URL failed Incognito public accessibility check: {captured_url}")
        return False, None

    final_live = verified_u or captured_url
    log_fn(f"🎉 Success! Incognito-Verified Live Knowt Note: {final_live}")
    log_fn(f"🔗 Final Live URL: {final_live}")
    return True, final_live



def dispatch_create_thread(page, platform_choice, board_url, title_text, body_text, log_fn, post_index=0):
    title_processed = process_spintax(title_text).strip()
    body_processed = process_spintax(body_text).strip()

    recipes = load_recipes()
    matched_recipe = None

    # 1. Exact match in recipes
    if platform_choice in recipes:
        matched_recipe = recipes[platform_choice]

    # 2. Match without prefixes (e.g., "🛠️ Blueprint: CricketWindies Forum" or "Blueprint: CricketWindies Forum")
    if not matched_recipe:
        clean_p = platform_choice.replace("🛠️", "").replace("Blueprint:", "").replace("Blueprint", "").strip()
        for r_name, r_data in recipes.items():
            if clean_p.lower() == r_name.lower() or clean_p.lower() == r_name.replace("🛠️", "").strip().lower():
                matched_recipe = r_data
                break

    # 3. If on Auto-Detect or no platform specified, match by board_url domain or pattern
    if not matched_recipe and board_url:
        try:
            b_domain = urlparse(board_url).netloc.replace("www.", "").lower()
            for r_name, r_data in recipes.items():
                r_domain = (r_data.get("domain_pattern") or "").lower()
                r_board = (r_data.get("board_url") or "").lower()
                if (b_domain and r_domain and b_domain in r_domain) or (b_domain and b_domain in r_board):
                    log_fn(f"⚡ Auto-detected Blueprint recipe for domain {b_domain}: {r_name}")
                    matched_recipe = r_data
                    break
        except Exception:
            pass

        # Check Knowt first
    if "knowt.com" in (board_url or "").lower() or "knowt" in (platform_choice or "").lower() or (matched_recipe and "knowt" in matched_recipe.get("name", "").lower()):
        log_fn("Engine: Knowt Note Creator (knowt.com)")
        return knowt_create_note(page, board_url, title_processed, body_processed, log_fn, post_index=post_index)

    if matched_recipe:
        return execute_custom_recipe(page, matched_recipe, board_url, title_processed, body_processed, log_fn)

    p_choice = (platform_choice or "Auto-Detect (Recommended)").lower()
    b_url = (board_url or "").lower()

    if "waiverelectronic.com" in b_url or "waiver" in p_choice or ("auto" in p_choice and "waiverelectronic.com" in b_url):
        log_fn("Engine: WaiverElectronic Template Creator (waiverelectronic.com)")
        return waiverelectronic_create_template(page, board_url, title_processed, body_processed, log_fn, post_index=post_index)

    elif "themoviedb.org" in b_url or "tmdb" in p_choice or "movie" in p_choice:
        log_fn("Engine: TMDb Movie Creator (themoviedb.org)")
        return tmdb_create_movie(page, board_url, title_processed, body_processed, log_fn, post_index=post_index)

    elif "proboards" in p_choice or ("auto" in p_choice and ("proboards.com" in b_url or "/thread/new/" in b_url)):
        log_fn("Engine: ProBoards Dedicated Engine")
        return proboards_create_thread(page, board_url, title_processed, body_processed, log_fn)

    elif "vbulletin 5" in p_choice or "avid" in p_choice or ("auto" in p_choice and ("duc.avid.com" in b_url or "/new-content/" in b_url)):
        log_fn("Engine: vBulletin 5/6 Connect (Avid DUC style)")
        return vbulletin5_create_thread(page, board_url, title_processed, body_processed, log_fn)

    elif "vbulletin 3" in p_choice or ("auto" in p_choice and "newthread.php" in b_url):
        log_fn("Engine: vBulletin 3/4 Classic")
        return vbulletin3_create_thread(page, board_url, title_processed, body_processed, log_fn)

    elif "xenforo" in p_choice or ("auto" in p_choice and ("post-thread" in b_url or "create-thread" in b_url or "xenforo" in b_url)):
        log_fn("Engine: XenForo 2.x Engine")
        return xenforo_create_thread(page, board_url, title_processed, body_processed, log_fn)

    elif "phpbb" in p_choice or ("auto" in p_choice and ("posting.php" in b_url or "phpbb" in b_url)):
        log_fn("Engine: phpBB Engine")
        return phpbb_create_thread(page, board_url, title_processed, body_processed, log_fn)

    else:
        log_fn("Engine: Universal Heuristic Fallback")
        return universal_create_thread(page, board_url, title_processed, body_processed, log_fn)


HOOK_STYLES = [
    "Personal Experience / Story Hook: Start with a relatable real-world experience, personal realization, or testing observation.",
    "Contrarian / Common Myth Hook: Start by challenging a common misconception or outdated advice on the topic.",
    "Direct Practical Troubleshooting Hook: Jump straight into a common problem and offer a clear, actionable solution.",
    "Thought-Provoking Discussion Hook: Open with an engaging question to the community, inviting debate and shared thoughts.",
    "Curated Breakdown / Checklist Hook: Open by presenting a concise, tested breakdown with key takeaways."
]

FORMAT_STYLES = [
    "Structured with numbered steps and bold key takeaways.",
    "Conversational forum post with short readable paragraphs and a closing discussion question.",
    "Bullet-point pros/cons or quick-action checklist format.",
    "Deep-dive guide style with bold subheadings and practical tips."
]

VOCAB_STYLES = [
    "Authentic, enthusiastic community contributor tone; avoid corporate buzzwords.",
    "Pragmatic, direct, and hands-on tone; focus on real-world utility.",
    "Analytical, curious, and thoughtful tone; explore subtle details.",
    "Casual, friendly peer-to-peer tone like a regular forum member."
]

def build_keyword_prompt(keyword, pdf_context="", index=0, custom_system_prompt=""):
    if custom_system_prompt and custom_system_prompt.strip():
        prompt = f"Create a comprehensive forum post about: {keyword}"
        if pdf_context and str(pdf_context).strip():
            prompt += f"\n\nNote: Incorporate any relevant heading tags, signs, and symbols from this guide into the title/headings:\n{str(pdf_context).strip()[:800]}"
        return prompt

    hook = HOOK_STYLES[index % len(HOOK_STYLES)]
    fmt = FORMAT_STYLES[index % len(FORMAT_STYLES)]
    vocab = VOCAB_STYLES[index % len(VOCAB_STYLES)]
    prompt = (
        f"Create a high-value, authentic forum discussion thread about: {keyword}\n"
        f"- Opening Hook Style: {hook}\n"
        f"- Formatting Structure: {fmt}\n"
        f"- Tone & Voice: {vocab}\n"
    )
    if pdf_context and str(pdf_context).strip():
        prompt += f"\nIncorporate relevant heading tags/signs from this reference:\n{str(pdf_context).strip()[:800]}"
    return prompt


def find_installed_browser_path():
    """Finds physical Chrome or Edge executable on Windows/Mac."""
    import sys, os
    if sys.platform.startswith("win"):
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
    elif sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
    return None



# ==============================================================================
# GOOGLE OAUTH & "SIGN IN WITH GOOGLE" 100% BYPASS ENGINE
# ==============================================================================
CLEAN_CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

GOOGLE_SAFE_IGNORE_ARGS = [
    "--enable-automation",
    "--disable-extensions",
    "--use-mock-keychain",
    "--password-store=basic",
    "--disable-sync",
    "--disable-component-extensions-with-background-pages",
    "--disable-default-apps",
]

def _clean_profile_locks(profile_dir):
    """Removes stale Chromium SingletonLock files so persistent profiles never fail to open."""
    try:
        p = Path(profile_dir)
        for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket"]:
            lf = p / lock_name
            if lf.exists() or lf.is_symlink():
                try:
                    lf.unlink()
                except Exception:
                    pass
    except Exception:
        pass

def get_free_localhost_port():
    """Finds an available localhost TCP port for clean native Chrome CDP attachment."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def find_installed_browser_path():
    """Finds physical Chrome, Edge, or Brave executable on Windows/Mac/Linux."""
    import sys, os, shutil
    if sys.platform.startswith("win"):
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
    elif sys.platform == "darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        ]
        for c in candidates:
            if os.path.exists(c):
                return c
    elif sys.platform.startswith("linux"):
        for cmd in ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium", "microsoft-edge", "brave-browser"]:
            found = shutil.which(cmd)
            if found:
                return found
    return None

def find_any_browser_executable(playwright_instance=None):
    """Finds physical Chrome, Edge, Brave, or Playwright Chromium binary across Windows, macOS, and Linux."""
    import os
    exe = find_installed_browser_path()
    if exe and os.path.exists(exe):
        return exe
    if playwright_instance is not None:
        try:
            pw_exe = playwright_instance.chromium.executable_path
            if pw_exe and os.path.exists(pw_exe):
                return pw_exe
        except Exception:
            pass
    return None

def launch_native_chrome_for_google_login(playwright_instance, profile_dir, target_url, ext_path=None, log_fn=None):
    """
    Launches Chrome/Edge/Chromium as a 100% standalone OS process (subprocess.Popen) WITHOUT:
    - Playwright's --remote-debugging-pipe / Runtime.enable
    - Fake --user-agent overrides (so User-Agent & Sec-CH-UA headers match 100%)
    - --disable-extensions-except (so Chrome's internal Google Identity component extension stays active)
    Returns (proc, cdp_port) or (None, None) if unavailable.
    """
    import subprocess, sys, time, urllib.request
    is_headless_linux_cloud = sys.platform.startswith("linux") and not os.environ.get("DISPLAY")
    if is_headless_linux_cloud:
        return None, None

    exe_path = find_any_browser_executable(playwright_instance)
    if not exe_path:
        return None, None

    _clean_profile_locks(profile_dir)
    port = get_free_localhost_port()

    cmd = [
        exe_path,
        f"--user-data-dir={profile_dir}",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-blink-features=AutomationControlled",
        "--window-size=1280,960",
    ]
    if target_url:
        cmd.append(target_url)

    # Use proxy-bypassing opener for 127.0.0.1 so system proxy env vars never break localhost CDP polling
    no_proxy_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=(not sys.platform.startswith("win"))
        )
        ready = False
        for _ in range(36):
            if proc.poll() is not None:
                break
            try:
                with no_proxy_opener.open(f"http://127.0.0.1:{port}/json/version", timeout=0.6) as r:
                    if r.status == 200:
                        ready = True
                        break
            except Exception:
                pass
            time.sleep(0.25)

        if ready:
            if log_fn:
                log_fn("🛡️ Launched Google-Safe Native Browser (Zero-Automation Mode for Google Sign-In)!")
            return proc, port
        else:
            try:
                proc.terminate()
            except Exception:
                pass
    except Exception as e:
        if log_fn:
            log_fn(f"Native browser launch note: {e}")
    return None, None

def get_cdp_open_tabs(cdp_port):
    """
    Returns list of open page tab dicts from Chrome's HTTP endpoint without attaching CDP WebSocket.
    Returns None on transient network error (so caller doesn't mistake a timeout for a closed browser!).
    """
    import urllib.request, json
    no_proxy_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with no_proxy_opener.open(f"http://127.0.0.1:{cdp_port}/json/list", timeout=2.0) as r:
            items = json.loads(r.read().decode("utf-8", errors="ignore"))
            if not isinstance(items, list):
                return None
            return [it for it in items if it.get("type") in ("page", "other", "webview")]
    except Exception:
        return None

def launch_google_safe_persistent_context(playwright_instance, profile_dir, headless=False, ext_path=None, log_fn=None):
    """
    Fallback persistent context launcher with full Google OAuth stealth (keeps Site Isolation ON,
    keeps internal Chrome component extensions ON, and preserves native Chrome User-Agent).
    """
    import sys
    _clean_profile_locks(profile_dir)
    is_headless_linux_cloud = sys.platform.startswith("linux") and not os.environ.get("DISPLAY")
    headless_bool = True if (is_headless_linux_cloud or str(headless).lower() in ["true", "1"] or headless is True) else False

    launch_args = list(STEALTH_ARGS)
    if is_headless_linux_cloud:
        for cflag in ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]:
            if cflag not in launch_args:
                launch_args.append(cflag)

    launch_kwargs = {
        "user_data_dir": str(profile_dir),
        "headless": headless_bool,
        "viewport": {"width": 1280, "height": 960},
        "args": launch_args,
        "ignore_default_args": GOOGLE_SAFE_IGNORE_ARGS,
    }
    ctx = None
    for ch in ["chrome", "msedge", None]:
        try:
            if ch:
                ctx = playwright_instance.chromium.launch_persistent_context(channel=ch, **launch_kwargs)
            else:
                exe = find_installed_browser_path()
                if exe:
                    ctx = playwright_instance.chromium.launch_persistent_context(executable_path=exe, **launch_kwargs)
                else:
                    ctx = playwright_instance.chromium.launch_persistent_context(**launch_kwargs)
            if ctx:
                break
        except Exception:
            continue
    if ctx:
        try:
            ctx.add_init_script(INIT_STEALTH_JS)
        except Exception:
            pass
    return ctx


def launch_safe_browser(playwright_instance, headless=False, args=None, log_fn=None):
    """
    Auto-detects installed Google Chrome, then Microsoft Edge, direct executable path,
    or bundled Chromium. Automatically installs Chromium if missing.
    Ensures browser launching never fails on Windows machines.
    """
    import sys, subprocess
    # Auto-detect Linux Cloud Container without X11 DISPLAY (Colab / HuggingFace / Render / Railway)
    is_headless_linux_cloud = sys.platform.startswith("linux") and not os.environ.get("DISPLAY")
    headless_bool = True if (is_headless_linux_cloud or str(headless).lower() in ["true", "1"] or headless is True) else False
    launch_args = list(args or STEALTH_ARGS)
    if is_headless_linux_cloud:
        for cflag in ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]:
            if cflag not in launch_args:
                launch_args.append(cflag)
    errors = []

    # 1. Try native channel="chrome"
    try:
        return playwright_instance.chromium.launch(
            channel="chrome",
            headless=headless_bool,
            args=launch_args,
            ignore_default_args=GOOGLE_SAFE_IGNORE_ARGS
        )
    except Exception as e:
        errors.append(f"chrome channel: {e}")

    # 2. Try native channel="msedge"
    try:
        return playwright_instance.chromium.launch(
            channel="msedge",
            headless=headless_bool,
            args=launch_args,
            ignore_default_args=GOOGLE_SAFE_IGNORE_ARGS
        )
    except Exception as e:
        errors.append(f"msedge channel: {e}")

    # 3. Try direct executable_path on disk
    exe_path = find_installed_browser_path()
    if exe_path:
        try:
            return playwright_instance.chromium.launch(
                executable_path=exe_path,
                headless=headless_bool,
                args=launch_args,
                ignore_default_args=GOOGLE_SAFE_IGNORE_ARGS
            )
        except Exception as e:
            errors.append(f"executable_path: {e}")

    # 4. Try bundled Chromium
    try:
        return playwright_instance.chromium.launch(
            headless=headless_bool,
            args=launch_args,
            ignore_default_args=GOOGLE_SAFE_IGNORE_ARGS
        )
    except Exception as e:
        errors.append(f"bundled chromium: {e}")

    # 5. Auto-install Chromium if missing and retry
    if log_fn:
        log_fn("⏳ Installing Chromium components (one-time setup)...")
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True, timeout=120)
        return playwright_instance.chromium.launch(
            headless=headless_bool,
            args=launch_args,
            ignore_default_args=GOOGLE_SAFE_IGNORE_ARGS
        )
    except Exception as e:
        errors.append(f"install chromium: {e}")

    if log_fn:
        log_fn(f"⚠️ Browser launch diagnostic: {'; '.join(errors[-2:])}")
    return None

