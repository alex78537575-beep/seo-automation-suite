# 🚀 Autonomous Web Automation, Indexing & Content Verification Suite

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Browser%20Automation-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/)
[![Architecture](https://img.shields.io/badge/Architecture-Multi--Worker%20%26%20REST-9cf)](https://github.com/)
[![Google%20Sheets](https://img.shields.io/badge/Google%20Sheets-Cloud%20Auth%20%26%20Live%20Sync-0F9D58?logo=googlesheets&logoColor=white)](https://docs.google.com/spreadsheets/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A full-stack collection of **3 production-grade Python & Playwright automation platforms** engineered for autonomous web publishing, high-speed concurrent form discovery, multi-API indexing, and unauthenticated Incognito URL verification.

> 🔒 **Cloud Access Control (`CloudLoginWindow`)**: All 3 applications are protected by a centralized Google Sheet Cloud Authorization Gate. To request a temporary evaluation login (`Username` / `Access Key`) for live testing or technical interviews, please contact the repository author.

---

## 📦 Included Platforms (3-in-1 Engineering Suite)

| # | Platform Directory | Core Architecture & Highlights | Tech Stack |
|---|---|---|---|
| **1** | **[`01_forum_studio_pro/`](./01_forum_studio_pro)** | **Forum Studio Pro (Apple Liquid Glass Edition)** — 1–4 concurrent Playwright tab workers, 6-Stage Autonomous Unknown-Site DOM Agent v3.0 (18+ CMS engines), Real Incognito URL Verifier, Auto-Healer Retry Engine, and 0.2s Google Sheet Column `A1+` Auto-Sync. | Python, Playwright CDP, REST Bridge, Tailwind UI, Google Apps Script, Local LLMs (Ollama/Gemma) |
| **2** | **[`02_unified_backlink_suite/`](./02_unified_backlink_suite)** | **Unified SEO Backlink & Indexing Suite** — Dual-engine architecture combining a 2-second 10-site REST API publisher (`CentOS DA 91`, `Graph.org DA 88`, `Rentry`, `dpaste`), XML-RPC search crawler pinger, single-Chrome bookmarking (`Diigo`, `Hatena`, `Pastelink`), and an 8s Google Sheet live watcher. | Python, CustomTkinter, Playwright, XML-RPC, REST APIs, Multithreading |
| **3** | **[`03_pdf_form_uploader/`](./03_pdf_form_uploader)** | **PDF Uploader & Concurrent Form Crawler v6.0** — Priority BFS multi-threaded web crawler (`ThreadPoolExecutor`) with `.xml.gz` sitemap parsing and deep iframe/dropzone inspection (`Dropzone`, `FilePond`, `WPForms`, `Gravity Forms`, `Drupal Webform`) paired with a dual-phase AJAX/Form PDF uploader. | Python, Playwright, Requests, CustomTkinter, Concurrent Futures |

---

## 🛠️ Quickstart & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/seo-automation-suite.git
cd seo-automation-suite
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Launch Any of the 3 Platforms
```bash
# 1. Launch Forum Studio Pro (Apple Liquid Glass Web UI)
python 01_forum_studio_pro/main.py

# 2. Launch Unified SEO Backlink & Indexing Suite
python 02_unified_backlink_suite/unified_backlink_suite.py

# 3. Launch PDF Uploader & Form Crawler v6.0
python 03_pdf_form_uploader/pdf_uploader.py
```

---

## 🔒 Security & Privacy Architecture
- **Cloud Permission Gate**: Startup execution is verified in real time against an encrypted cloud authorization sheet (`active` / `revoked` user status).
- **Zero Credential Leaks**: All local session cookies (`.forum_session*.json`), OAuth tokens (`token.json`), and browser profiles are excluded via `.gitignore`.
