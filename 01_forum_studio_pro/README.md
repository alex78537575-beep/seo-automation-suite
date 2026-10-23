# Forum Studio Pro — Autonomous Web Automation & Verification Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Automation-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/)
[![FastAPI%20/%20REST](https://img.shields.io/badge/Architecture-Async%20REST%20Bridge-9cf)](https://github.com/)
[![Google%20Sheets%20API](https://img.shields.io/badge/Google%20Sheets-Real--Time%20Sync-0F9D58?logo=googlesheets&logoColor=white)](https://developers.google.com/sheets/api)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An enterprise-grade, concurrent browser automation and content publishing platform built in Python. Designed for high-throughput multi-site publication across diverse forum software, Web 2.0 properties, and CMS engines, featuring an **Autonomous 6-Stage Heuristic DOM Analyzer**, zero-latency **Google Sheets Auto-Sync (A1+)**, **Unauthenticated Incognito URL Verification**, and **Anti-Bot CDP Stealth**.

---

## 🌟 Key Engineering Features

### 1. Multi-Worker Concurrent Browser Pipeline
- Runs **1 to 4 parallel Playwright browser tab workers** with per-tab clipboard isolation and thread-safe queue locking.
- Employs dedicated `user_data_dir` profile persistence and automated session serialization (`storage_state`), allowing seamless session handoff from an interactive login into parallel headless posting workers.

### 2. Autonomous Unknown-Site Agent v3.0 (6-Stage State Machine)
- Dynamically discovers and interacts with arbitrary web editors across **18+ CMS platforms** (WordPress, Gutenberg, Classic Admin, XenForo, vBulletin, phpBB, MyBB, SMF, Discourse, Flarum, Telegraph, and custom apps) without pre-configured selectors:
  - **Stage 0 (Pre-Flight HTML Probe)**: Lightweight HTTP request carrying session cookies to analyze `<form>`, CSRF tokens, and generator tags prior to DOM rendering.
  - **Stage 1 (Opener State Machine)**: Multi-step click progression traversing "+ / New Thread / Write / Blank Scratch" buttons.
  - **Stage 2 (Deep DOM & Shadow-DOM Geometry)**: Evaluates bounding boxes, label proximities, and contenteditable tags to isolate Title and Body inputs.
  - **Stage 3 (4-Method Injection Cascade)**: Robust fallback hierarchy (Native Playwright $\to$ React/Vue prototype value setters $\to$ Synthetic Paste $\to$ WYSIWYG APIs).
  - **Stage 4 (Required Field Satisfier)**: Automatically handles required category dropdowns, terms checkboxes, and multi-step wizard buttons.
  - **Stage 5 (Share Permission Unlocker)**: Detects modal dialogs and toggles "Anyone with the link / Public" visibility prior to link capture.
  - **Stage 6 (6-Source URL Extraction)**: Multi-source capture using Readonly Share Inputs, Clipboard hooks, Network JSON API sniffers, URL redirect diffs, and DOM title permalinks.

### 3. Real-Time Incognito URL Verification Engine
- Tests generated URLs inside a **genuine zero-cookie, unauthenticated Incognito browser context** (`verify_url_incognito`).
- Validates real rendering, rejecting HTTP 404/403 errors, private/un-saved notes, login walls, and empty untitled shells.
- Implements an adaptive 20-second verification cache to prevent duplicate validation latency across worker threads.

### 4. Real-Time Google Sheet Auto-Sync Engine (`Column A1+`)
- Directly streams verified URLs into Google Sheets starting sequentially from cell **`A1`** downward (`A1`, `A2`, `A3`...).
- **Hybrid Execution Engine**:
  - **⚡ 0.2s Google Apps Script Webhook**: Zero-RAM, zero-browser atomic append utilizing server-side `LockService` for instant execution.
  - **Zero-Setup Headless Playwright Fallback**: Deterministically enters `A{row}` into Google Sheets' Name Box (`#t-name-box`) and injects URLs via the Formula Bar (`#t-formula-bar-input`).
  - Serialized through `_GSHEET_SYNC_LOCK` to ensure multi-tab workers never collide or overwrite existing rows.

### 5. Auto-Retry & Failed Queue Healer
- Automatically detects transient failures (slow page loads, network hiccups) and initiates configurable **Healer Passes (1x–3x)**.
- Spawns fresh, clean browser contexts with extended stabilization timeouts (`+2.5s`) to heal and post rescued items.

### 6. Anti-Bot Stealth & Native Chrome OAuth Bridge
- Bypasses Cloudflare Turnstile, reCAPTCHA v2/v3, and hCaptcha bot detection using runtime `Navigator.prototype.webdriver` patching and dynamic `navigator.userAgentData` Google Chrome v131 Client Hints.
- Launches a native OS-level Chrome subprocess (`launch_native_chrome_for_google_login`) with delayed CDP attachment to enable zero-block **Google OAuth / Sign in with Google** (`accounts.google.com`).

---

## 🏗️ System Architecture

```text
┌────────────────────────────────────────────────────────────────────────┐
│               Modern Desktop Web UI (Apple Liquid Glass)               │
│               HTML5 • Tailwind CSS • Web Audio • REST Bridge           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / WebSocket (Port 8765)
┌───────────────────────────────────▼────────────────────────────────────┐
│                  ModernBridgeApi Coordinator (api.py)                   │
│        Queue Dispatcher • Thread Pool Manager • State Observer         │
└───────┬───────────────────────────┬────────────────────────────┬───────┘
        │                           │                            │
┌───────▼──────────────┐   ┌────────▼─────────────┐   ┌──────────▼───────┐
│ Worker #1 (Tab 1)    │   │ Worker #2 (Tab 2)    │   │ Worker #N (Tab N)│
│ Playwright Chromium  │   │ Playwright Chromium  │   │ Playwright Chrom.│
└───────┬──────────────┘   └────────┬─────────────┘   └──────────┬───────┘
        └───────────────────────────┼────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                    Autonomous Engine Core (backend.py)                 │
│  Pre-Flight HTML • 6-Stage DOM Analyzer • Input Injection Cascade     │
└───────┬────────────────────────────────────────────────────────┬───────┘
        │                                                        │
┌───────▼────────────────────────┐      ┌────────────────────────▼───────┐
│ Real Incognito URL Verifier    │      │ Google Sheet Column A1+ Stream │
│ Zero-Cookie Headless Context   │      │ 0.2s Webhook / Name Box Writer │
└────────────────────────────────┘      └────────────────────────────────┘
```

---

## 📁 Repository Structure

```text
├── api.py               # REST API bridge & multi-threaded queue coordinator
├── backend.py           # Core automation engine, 6-stage DOM agent & sheet sync
├── index.html           # Single-page desktop UI (Apple Liquid Glass design)
├── main.py              # Zero-dependency local HTTP server & window launcher
├── recipes.json         # Learned site blueprints and selector recipes
├── requirements.txt     # Python dependencies
├── run.bat              # One-click Windows launcher
├── .gitignore           # Security filters protecting session cookies and configs
└── LICENSE              # MIT License
```

---

## 🚀 Quickstart & Installation

### Prerequisites
- Python 3.10 or higher
- Google Chrome or Microsoft Edge installed on your system

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/forum-studio-pro.git
cd forum-studio-pro
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Launch the Application
- **On Windows (Double-click or run via terminal)**:
  ```bash
  run.bat
  ```
- **On macOS / Linux**:
  ```bash
  python3 main.py
  ```
The dashboard will launch automatically in a dedicated native window at `http://127.0.0.1:8765`.

---

## 📊 Google Sheets Auto-Sync Setup (`Column A1+`)

1. Open your target Google Sheet.
2. In the dashboard's **Google Sheet Auto-Sync** bar, paste your Google Sheet URL.
3. *(Optional for 0.2s instant speed)*: Click **`⚡ Copy 0.2s Script`** in the UI, open your Google Sheet $\to$ **Extensions** $\to$ **Apps Script**, paste the code, and click **Deploy $\to$ New deployment $\to$ Web app** (*Who has access: Anyone*). Paste the `/exec` URL into the Webhook box.

---

## 🔒 Security & Privacy Notice
All login credentials, persistent profiles, and authentication cookies are stored exclusively on your local machine (`.forum_profile*`, `session*.json`). The repository includes a strict `.gitignore` to prevent any inadvertent commitment of sensitive tokens.

---

## 📄 License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
