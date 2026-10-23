#!/usr/bin/env python3
"""PDF Uploader v6.0 — Universal Multi-Strategy Uploader & Desktop App.
pip install requests customtkinter playwright

Key upgrades in v6.0 (Fixing uploads on unknown sites):
1. True Frame-Aware Engine:
   - Searches main page AND all nested `<iframe>` elements for `<input type="file">`,
     dropzones, required fields, and submit buttons.
2. Hidden & Dynamic File Chooser Support:
   - Attaches directly to hidden inputs (`display:none` / `opacity:0` used by Dropzone,
     WPForms, Elementor, Gravity Forms, Contact Form 7, FilePond, Uppy).
   - Falls back to `page.expect_file_chooser()` when clicking custom upload dropzones
     that create `<input type="file">` dynamically on click.
   - Dispatches synthetic `input`, `change`, and `blur` DOM events so React/Vue/jQuery
     upload handlers recognize the attached file immediately.
3. Smart Universal Form Filler (`_fill_required_fields`):
   - Inspects `<label>`, `type`, `name`, `id`, `placeholder`, and `aria-label`.
   - Properly fills emails, US phone numbers, URLs, numbers, dates, zip codes,
     `<select>` dropdowns, radio buttons, and mandatory consent/GDPR checkboxes.
   - Handles Multi-Step Wizard forms: fills Step 1 fields and clicks "Next"/"Continue"
     to reach the file upload step.
4. Dual-Phase Upload Execution (AJAX + Automatic Form Submit Fallback):
   - Phase A: Attaches PDF, clicks per-field AJAX "Upload" button if present (Drupal/Webform),
     and waits up to 10s for immediate AJAX upload URLs.
   - Phase B: If the site only uploads files when the form is submitted (Elementor,
     CF7, Everest, WPForms, standard multipart POST forms), it automatically submits
     the form and captures the resulting file URL!
5. Deep URL Extraction & Fingerprint Probing:
   - Unescapes JSON slashes (`\\/`) before regex matching.
   - Captures both full `https://...` and relative `/wp-content/uploads/...` or
     `/sites/default/files/...` paths from network responses, headers, and DOM.
   - Probes known fingerprint directories / standard WordPress `/wp-content/uploads/YYYY/MM/`
     paths when forms succeed silently without echoing the file URL in the response.
"""

import json
import os
import queue
import re
import threading
import time
from datetime import datetime
from tkinter import filedialog, messagebox
from urllib.parse import urljoin, urlparse

import customtkinter as ctk
import requests
import urllib3
from requests.exceptions import ConnectTimeout as _ConnectTimeout, SSLError as _SSLError

from find_form import (
    PLUGIN_SIGNATURES,
    find_forms,
    find_forms_js,
    find_forms_keyword,
    fingerprint_from_file_url,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- SSL + timeout fallback patch ---
_orig_session_request = requests.Session.request


def _session_request_with_fallback(self, method, url, **kwargs):
    try:
        return _orig_session_request(self, method, url, **kwargs)
    except _SSLError:
        kwargs["verify"] = False
        return _orig_session_request(self, method, url, **kwargs)
    except _ConnectTimeout:
        old = kwargs.get("timeout", 30)
        kwargs["timeout"] = max(120, (old if isinstance(old, (int, float)) else 30) * 3)
        return _orig_session_request(self, method, url, **kwargs)


requests.Session.request = _session_request_with_fallback
# --- end patch ---

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-sandbox",
    "--disable-infobars",
    "--disable-dev-shm-usage",
]

INIT_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});
"""

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

REVEAL_BUTTONS = [
    "Upload", "Upload file", "Upload File", "Upload resume", "Upload CV",
    "Attach", "Attach file", "Choose file", "Choose File", "Select file",
    "Add attachment", "Browse", "Apply", "Apply Now", "Apply Online",
    "Next", "Continue", "Step 2",
]

DROPZONE_SELECTORS = [
    ".dropzone", ".dz-clickable", ".dz-message",
    ".wpforms-uploader", ".gform_drop_area", ".dnd-upload-handler",
    ".filepond--root", ".uppy-Dashboard-AddFiles", ".qq-upload-button",
    ".frm_dropzone", ".ff_file_upload", "[data-dropzone]",
]


def load_config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ============================================================ URL extraction helpers

# Matches full http(s) URLs pointing to uploaded documents
FULL_FILE_URL_RE = re.compile(
    r"""https?://[^\s"'<>\\]+?\.(?:pdf|docx?|zip)(?:\?[^\s"'<>\\]*)?""",
    re.I,
)

# Matches relative paths pointing to uploaded documents in common CMS folders
REL_FILE_URL_RE = re.compile(
    r"""(?P<path>/(?:wp-content/uploads|sites/default/files|uploads|files|storage|media|assets)/[^\s"'<>\\]+?\.(?:pdf|docx?|zip))""",
    re.I,
)


def _extract_pdf_urls_from_text(body, base_url, uploaded_filename=None):
    """Extract all candidate uploaded file URLs from raw HTTP response text or DOM."""
    if not body:
        return []
    # Unescape JSON-escaped forward slashes and unicode escapes
    cleaned = body.replace("\\/", "/").replace("\\u002f", "/").replace("\\u002F", "/")
    candidates = []

    for m in FULL_FILE_URL_RE.finditer(cleaned):
        u = m.group(0).rstrip(".,;)]}")
        if u not in candidates:
            candidates.append(u)

    for m in REL_FILE_URL_RE.finditer(cleaned):
        rel = m.group("path").rstrip(".,;)]}")
        absu = urljoin(base_url, rel)
        if absu not in candidates:
            candidates.append(absu)

    if not candidates:
        return []

    # Prioritize URLs that match the uploaded filename stem if present
    if uploaded_filename:
        stem = os.path.splitext(uploaded_filename)[0].lower()
        clean_stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
        prioritized = [
            u for u in candidates
            if (stem and stem in u.lower()) or (clean_stem and clean_stem in u.lower())
        ]
        if prioritized:
            return prioritized

    return candidates


def _probe_predicted_upload_urls(page_url, fname, fingerprint_url=None, log=None):
    """If a form succeeds silently without echoing the file URL in its response,
    probe likely upload directories (from fingerprint URL or standard WP structure)."""
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    parsed = urlparse(page_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    name_variants = [fname]
    sanitized = re.sub(r"\s+", "-", fname)
    if sanitized not in name_variants:
        name_variants.append(sanitized)
    sanitized_under = re.sub(r"\s+", "_", fname)
    if sanitized_under not in name_variants:
        name_variants.append(sanitized_under)

    dirs_to_check = []
    if fingerprint_url and fingerprint_url.startswith("http"):
        fp_dir = fingerprint_url.rsplit("/", 1)[0] + "/"
        dirs_to_check.append(fp_dir)

    now = datetime.now()
    ym = f"{now.year}/{now.month:02d}"
    dirs_to_check.extend([
        f"{origin}/wp-content/uploads/{ym}/",
        f"{origin}/wp-content/uploads/elementor/forms/",
        f"{origin}/wp-content/uploads/wpforms/",
        f"{origin}/wp-content/uploads/everest_forms_uploads/",
        f"{origin}/wp-content/uploads/wpcf7_uploads/",
        f"{origin}/sites/default/files/webform/",
        f"{origin}/uploads/",
    ])

    seen_dirs = set()
    for d in dirs_to_check:
        if d in seen_dirs:
            continue
        seen_dirs.add(d)
        for nv in name_variants:
            candidate = urljoin(d, nv)
            try:
                r = s.head(candidate, timeout=6, allow_redirects=True, verify=False)
                ct = r.headers.get("content-type", "").lower()
                if r.status_code == 200 and ("pdf" in ct or "octet-stream" in ct or "application/" in ct):
                    if log:
                        log(f"[probe] verified uploaded file at {candidate}")
                    return candidate
            except Exception:
                continue
    return None


# ============================================================ Smart Form & Frame Engine

def _fill_required_fields_in_frame(frame, email, log, label="gen"):
    """Fill visible empty inputs, textareas, selects, radios, and consent checkboxes
    in the given frame so form validation succeeds on unknown sites."""
    # 1. Text, Email, Tel, URL, Number, Date, Textarea
    try:
        els = frame.query_selector_all(
            "input:not([type=hidden]):not([type=file]):not([type=submit])"
            ":not([type=button]):not([type=reset]):not([type=checkbox]):not([type=radio]):not([type=image]), "
            "textarea"
        )
        for el in els:
            try:
                if not el.is_visible() or el.get_attribute("disabled") is not None or el.get_attribute("readonly") is not None:
                    continue
                cur = (el.input_value() or "").strip()
                if cur:
                    continue

                inp_type = (el.get_attribute("type") or "text").lower()
                label_text = el.evaluate(
                    """el => {
                        if (el.labels && el.labels.length) return Array.from(el.labels).map(l => l.innerText).join(' ');
                        const wrap = el.closest('label, .form-group, .gfield, .wpforms-field, .elementor-field-group, .evf-field, .ff-el-group');
                        return wrap ? wrap.innerText : '';
                    }"""
                ) or ""
                hint = " ".join(filter(None, [
                    el.get_attribute("name"),
                    el.get_attribute("id"),
                    el.get_attribute("placeholder"),
                    el.get_attribute("aria-label"),
                    label_text,
                ])).lower()

                if inp_type == "email" or "email" in hint or "e-mail" in hint:
                    val = email
                elif inp_type == "tel" or any(k in hint for k in ("phone", "tel", "mobile", "cell", "contact no")):
                    val = "202-555-0147"
                elif inp_type == "url" or any(k in hint for k in ("website", "url", "http", "link")):
                    val = "https://example.com"
                elif inp_type == "number" or any(k in hint for k in ("zip", "postal", "pin code")):
                    val = "90210"
                elif inp_type == "date" or "date" in hint or "dob" in hint:
                    val = "2026-10-15"
                elif "first" in hint and "name" in hint:
                    val = "Alex"
                elif ("last" in hint and "name" in hint) or "surname" in hint:
                    val = "Miller"
                elif "name" in hint:
                    val = "Alex Miller"
                elif any(k in hint for k in ("city", "town")):
                    val = "Austin"
                elif "state" in hint or "province" in hint:
                    val = "TX"
                elif any(k in hint for k in ("address", "street")):
                    val = "742 Evergreen Terrace"
                elif any(k in hint for k in ("company", "organization", "employer")):
                    val = "Apex Solutions"
                elif any(k in hint for k in ("subject", "topic", "title", "position")):
                    val = "General Application"
                else:
                    val = "Submitted document attached."

                el.fill(val, timeout=2000)
                el.evaluate("el => { el.dispatchEvent(new Event('input', {bubbles:true})); el.dispatchEvent(new Event('change', {bubbles:true})); }")
            except Exception:
                continue
    except Exception:
        pass

    # 2. Dropdowns (<select>)
    try:
        for sel in frame.query_selector_all("select"):
            try:
                if not sel.is_visible() or sel.get_attribute("disabled") is not None:
                    continue
                val = sel.evaluate(
                    """s => {
                        if (s.selectedIndex > 0 && s.value) return null;
                        for (let i = 0; i < s.options.length; i++) {
                            const o = s.options[i];
                            if (o.value && !o.disabled && !/select|choose|--/i.test(o.text)) {
                                s.selectedIndex = i;
                                s.dispatchEvent(new Event('change', {bubbles: true}));
                                return o.text;
                            }
                        }
                        return null;
                    }"""
                )
                if val:
                    log(f"[{label}] selected dropdown option '{val[:30]}'")
            except Exception:
                continue
    except Exception:
        pass

    # 3. Radio buttons (pick first option per unchecked group)
    try:
        frame.evaluate(
            """() => {
                const groups = {};
                document.querySelectorAll('input[type=radio]:not([disabled])').forEach(r => {
                    const name = r.name || '__unnamed__';
                    if (!groups[name]) groups[name] = [];
                    groups[name].push(r);
                });
                Object.values(groups).forEach(radios => {
                    if (!radios.some(r => r.checked) && radios.length > 0) {
                        const yesRadio = radios.find(r => /yes|true|1/i.test(r.value || ''));
                        const target = yesRadio || radios[0];
                        target.checked = true;
                        target.dispatchEvent(new Event('change', {bubbles: true}));
                    }
                });
            }"""
        )
    except Exception:
        pass

    # 4. Required / Consent / GDPR / Terms Checkboxes
    try:
        for cb in frame.query_selector_all("input[type=checkbox]:not([disabled])"):
            try:
                if cb.is_checked():
                    continue
                is_req = cb.get_attribute("required") is not None or cb.get_attribute("aria-required") == "true"
                wrap_txt = (cb.evaluate("el => (el.closest('label, .form-item, .gfield, .wpforms-field, .wpcf7-list-item, div') || el).innerText") or "").lower()
                if is_req or any(k in wrap_txt for k in ("agree", "consent", "terms", "privacy", "accept", "gdpr", "acknowledge", "confirm")):
                    cb.check(force=True, timeout=2000)
            except Exception:
                continue
    except Exception:
        pass


def _find_file_input_across_frames(pg, email, log, label="gen"):
    """Search main page and all iframes for `<input type="file">`.
    If not found, fill Step-1 fields and click reveal/next buttons to expose it.
    Returns (frame, element_handle_or_None, used_dropzone_selector_or_None).
    """
    # Pass 1: Direct lookup across all frames (includes hidden file inputs)
    for frame in pg.frames:
        try:
            inp = frame.query_selector('input[type="file"]')
            if inp:
                return frame, inp, None
        except Exception:
            continue

    # Pass 2: Check for Dropzone / custom upload containers across frames
    for frame in pg.frames:
        for dz_sel in DROPZONE_SELECTORS:
            try:
                dz = frame.query_selector(dz_sel)
                if dz and dz.is_visible():
                    inp = frame.query_selector('input[type="file"]')
                    if inp:
                        return frame, inp, None
                    return frame, None, dz_sel
            except Exception:
                continue

    # Pass 3: Fill visible Step-1 fields first (for multi-step wizards) and click Reveal/Next buttons
    for frame in pg.frames:
        _fill_required_fields_in_frame(frame, email, log, label)

    for b in REVEAL_BUTTONS:
        for frame in pg.frames:
            try:
                btn = frame.query_selector(
                    f'button:has-text("{b}"), a:has-text("{b}"), '
                    f'[role="button"]:has-text("{b}"), input[type=button][value*="{b}" i]'
                )
                if btn and btn.is_visible():
                    log(f"[{label}] clicking '{b}' to reveal file upload field")
                    btn.click(timeout=3500)
                    pg.wait_for_timeout(1800)
                    for f2 in pg.frames:
                        inp = f2.query_selector('input[type="file"]')
                        if inp:
                            return f2, inp, None
            except Exception:
                continue

    return pg.main_frame, None, None


def _attach_file_robust(pg, frame, inp, dz_sel, path, log, label="gen"):
    """Attach `path` to `inp` (even if hidden) or via `expect_file_chooser` on `dz_sel`,
    and fire synthetic DOM change events."""
    if inp is not None:
        try:
            inp.set_input_files(path)
        except Exception:
            # Make hidden file input briefly visible if browser blocks setting files
            frame.evaluate(
                """el => {
                    el.style.display = 'block';
                    el.style.visibility = 'visible';
                    el.style.opacity = '1';
                    el.removeAttribute('hidden');
                }""",
                inp,
            )
            inp.set_input_files(path)

        # Dispatch input/change events so JS frameworks (Dropzone, WPForms, CF7, React) react
        try:
            frame.evaluate(
                """el => {
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                    el.dispatchEvent(new Event('change', { bubbles: true }));
                }""",
                inp,
            )
        except Exception:
            pass
        return True

    if dz_sel:
        try:
            log(f"[{label}] triggering file chooser via dropzone ({dz_sel})")
            with pg.expect_file_chooser(timeout=5000) as fc_info:
                frame.click(dz_sel, timeout=3000)
            fc = fc_info.value
            fc.set_files(path)
            return True
        except Exception as e:
            log(f"[{label}] dropzone file chooser failed: {e}")

    return False


def _click_field_upload_button(frame, log, label="gen"):
    """Drupal/webform style: a file field with its own 'Upload' button that fires AJAX."""
    selectors = [
        'form:has(input[type=file]) input[type=submit][name*="upload" i]',
        'form:has(input[type=file]) button[name*="upload" i]',
        'form:has(input[type=file]) input[type=button][name*="upload" i]',
        'form:has(input[type=file]) input[type=submit][value*="upload" i]',
        'form:has(input[type=file]) input[type=button][value*="upload" i]',
        'form:has(input[type=file]) button:has-text("Upload")',
        'form:has(input[type=file]) .form-submit[value*="upload" i]',
        'input[type=submit][value="Upload" i]',
        'input[type=button][value="Upload" i]',
    ]
    for sel in selectors:
        try:
            for btn in frame.query_selector_all(sel):
                try:
                    # Avoid clicking the main final form submit if it says "Submit" or "Send"
                    txt = ((btn.inner_text() if btn.evaluate("el => el.tagName") == "BUTTON" else btn.get_attribute("value")) or "").strip().lower()
                    if any(skip in txt for skip in ("submit", "send", "apply", "register")):
                        continue
                    if btn.is_visible() and not btn.get_attribute("disabled"):
                        log(f"[{label}] clicking per-field Upload button ({sel[:45]})")
                        btn.click(timeout=4000)
                        return True
                except Exception:
                    continue
        except Exception:
            continue
    return False


def _click_form_submit_button(frame, log, label="gen"):
    """Click the form's primary Submit / Send / Apply button."""
    selectors = [
        'form:has(input[type=file]) button[type=submit]',
        'form:has(input[type=file]) input[type=submit]',
        'form button[type=submit]',
        'form input[type=submit]',
        'button.wpforms-submit',
        'button.elementor-button[type=submit]',
        'input.wpcf7-submit',
        'input.gform_button[type=submit]',
        'button.evf-submit',
        'button.ff-btn-submit',
        'button[type=submit]',
        'input[type=submit]',
        'button:has-text("Submit")',
        'button:has-text("Send")',
        'button:has-text("Apply")',
    ]
    for sel in selectors:
        try:
            for btn in frame.query_selector_all(sel):
                try:
                    val = (btn.get_attribute("value") or "").lower()
                    name = (btn.get_attribute("name") or "").lower()
                    if "remove" in val or "remove" in name or "cancel" in val:
                        continue
                    if btn.is_visible() and not btn.get_attribute("disabled"):
                        log(f"[{label}] clicking form Submit button ({sel[:45]})")
                        btn.click(timeout=5000)
                        return True
                except Exception:
                    continue
        except Exception:
            continue
    return False


def _scan_frames_for_uploaded_link(pg, page_url, fname):
    """Scan all frames' DOMs for newly injected links or values pointing to the uploaded PDF."""
    for frame in pg.frames:
        try:
            # 1. Check <a href="...">
            for a in frame.query_selector_all("a[href]"):
                href = (a.get_attribute("href") or "").strip()
                if not href:
                    continue
                absu = urljoin(page_url, href)
                if re.search(r"\.(pdf|docx?|zip)(\?|$)", absu, re.I) and absu != page_url:
                    return absu

            # 2. Check hidden inputs where Dropzone/WPForms/Elementor store uploaded file URLs
            for h in frame.query_selector_all('input[type="hidden"], input[data-file], [data-url]'):
                val = (h.get_attribute("value") or h.get_attribute("data-url") or "").strip()
                if val:
                    urls = _extract_pdf_urls_from_text(val, page_url, uploaded_filename=fname)
                    if urls:
                        return urls[-1]

            # 3. Full frame HTML regex scan
            urls = _extract_pdf_urls_from_text(frame.content(), page_url, uploaded_filename=fname)
            if urls:
                return urls[-1]
        except Exception:
            continue
    return None


def generic_upload(
    page_url,
    pdfs,
    email,
    log,
    submit_after=False,
    label="upload",
    on_progress=None,
    headless=True,
    fingerprint_url=None,
):
    """Universal multi-strategy PDF uploader across unknown sites."""
    from playwright.sync_api import sync_playwright

    results = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=headless, args=STEALTH_ARGS)
        ctx = b.new_context(user_agent=UA, ignore_https_errors=True)
        ctx.add_init_script(INIT_STEALTH_JS)
        pg = ctx.new_page()

        for idx, path in enumerate(pdfs, 1):
            fname = os.path.basename(path)
            if on_progress:
                on_progress(idx, len(pdfs), fname)
            captured = []

            def onresp(r):
                try:
                    # Check Location header on redirects
                    loc_hdr = r.headers.get("location", "")
                    if loc_hdr:
                        for u in _extract_pdf_urls_from_text(loc_hdr, page_url, fname):
                            if u not in captured:
                                captured.append(u)

                    # Inspect POST/PUT responses and JSON/HTML GET responses after upload
                    ct = r.headers.get("content-type", "").lower()
                    if r.request.method in ("POST", "PUT") or "json" in ct or "html" in ct or "xml" in ct:
                        body = r.text()[:300000]
                        for u in _extract_pdf_urls_from_text(body, page_url, fname):
                            if u not in captured:
                                captured.append(u)
                except Exception:
                    pass

            try:
                log(f"[{label}] ({idx}/{len(pdfs)}) Uploading {fname}…")
                pg.on("response", onresp)
                pg.goto(page_url, timeout=90000, wait_until="domcontentloaded")
                pg.wait_for_timeout(2500)

                target_frame, inp, dz_sel = _find_file_input_across_frames(pg, email, log, label)
                if inp is None and dz_sel is None:
                    raise RuntimeError("no file input or dropzone found on page or inside iframes")

                _fill_required_fields_in_frame(target_frame, email, log, label)
                if target_frame != pg.main_frame:
                    _fill_required_fields_in_frame(pg.main_frame, email, log, label)

                attached = _attach_file_robust(pg, target_frame, inp, dz_sel, path, log, label)
                if not attached:
                    raise RuntimeError("failed to attach file to input/dropzone")

                pg.wait_for_timeout(1500)

                # Phase A: Click per-field AJAX Upload button if present (Drupal/Webform style)
                clicked_ajax_btn = _click_field_upload_button(target_frame, log, label)

                # Poll briefly (up to 12s if AJAX button clicked, 6s otherwise) for immediate AJAX upload
                poll_cycles = 8 if clicked_ajax_btn else 4
                for _ in range(poll_cycles):
                    pg.wait_for_timeout(1500)
                    if captured:
                        break
                    dom_u = _scan_frames_for_uploaded_link(pg, page_url, fname)
                    if dom_u:
                        captured.append(dom_u)
                        break

                url = captured[-1] if captured else None

                # Phase B: If no URL captured yet (standard multipart/CF7/Elementor/Everest forms
                # only upload when the form is submitted!) OR if user requested submit_after:
                submitted = False
                if not url or submit_after:
                    if not url:
                        log(f"[{label}] no pre-submit AJAX URL — filling fields & submitting form to trigger upload…")
                    _fill_required_fields_in_frame(target_frame, email, log, label)
                    if _click_form_submit_button(target_frame, log, label) or (
                        target_frame != pg.main_frame and _click_form_submit_button(pg.main_frame, log, label)
                    ):
                        submitted = True
                        # Poll up to 20s for form submission response
                        for _ in range(10):
                            pg.wait_for_timeout(2000)
                            if captured:
                                break
                            dom_u = _scan_frames_for_uploaded_link(pg, page_url, fname)
                            if dom_u:
                                captured.append(dom_u)
                                break

                if not url and captured:
                    url = captured[-1]
                if not url:
                    url = _scan_frames_for_uploaded_link(pg, page_url, fname)
                if not url and submitted:
                    # Fallback: Probe known fingerprint or standard CMS upload directories
                    url = _probe_predicted_upload_urls(page_url, fname, fingerprint_url=fingerprint_url, log=log)

                if not url:
                    raise RuntimeError("file attached/submitted, but site did not expose a public file URL")

                url = url.replace("\\/", "/")
                results.append(url)
                log(f"[{label}] SUCCESS {fname} -> {url}")

            except Exception as e:
                log(f"[{label}] FAILED {fname}: {e}")
            finally:
                try:
                    pg.remove_listener("response", onresp)
                except Exception:
                    pass
        b.close()
    return results


# ============================================================ site analyzer

def analyze_site(page_url):
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    r = s.get(page_url, timeout=60, verify=False)
    body = r.text
    low = body.lower()
    info = {
        "url": page_url,
        "status": r.status_code,
        "type": "unknown",
        "plugins": [],
        "captcha": False,
        "detail": "",
    }
    if ("cloudflare" in low and "challenge" in low) or "just a moment" in low:
        info["type"] = "Bot-protected (Cloudflare challenge)"
        info["detail"] = "Enable 'Show browser' and try Generic upload."
        return info
    if any(k in low for k in ("recaptcha", "g-recaptcha", "hcaptcha", "cf-turnstile")):
        info["captcha"] = True
    has_file = bool(re.search(r"""<input\b[^>]*?\btype\s*=\s*['"]?file['"]?""", body, re.I))
    for label, html_markers, file_markers, _ in PLUGIN_SIGNATURES:
        if any(m.lower() in low for m in html_markers):
            has_upload = has_file or any(m.lower() in low for m in file_markers)
            info["plugins"].append(label + (" (upload field)" if has_upload else ""))
    if 'name="form_build_id"' in body or "drupal-settings-json" in low:
        info["plugins"].append("Drupal webform" + (" (upload field)" if has_file else ""))
    if "episerverforms" in low or "epi.episerver.forms" in low:
        info["plugins"].append("Episerver Forms")
    if info["plugins"]:
        info["type"] = ", ".join(info["plugins"])
    elif has_file:
        info["type"] = "Generic HTML form with file input"
    elif "<iframe" in low:
        info["type"] = "Page with embedded iframe(s) — Generic upload will scan inside iframes"
    elif "<form" in low:
        info["type"] = "Form without static file input — JS render / Dropzone may reveal one"
    else:
        info["type"] = "No static form detected"
    parts = []
    if info["captcha"]:
        parts.append("CAPTCHA detected — enable 'Show browser' if manual solve is needed")
    parts.append(
        "File input in static HTML"
        if has_file
        else "No static file input (Generic upload will check iframes, dropzones & click-reveal)"
    )
    info["detail"] = "; ".join(parts)
    return info


# ============================================================ GUI

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI PDF Uploader v6.0 — Universal Engine")
        self.geometry("1080x760")
        self.q = queue.Queue()
        self.pdf_paths = []
        self.uploaded_urls = []
        self._find_first_url = None

        # --- top row: target URL + email
        top = ctk.CTkFrame(self)
        top.pack(fill="x", padx=12, pady=(12, 4))
        ctk.CTkLabel(top, text="Target URL:").pack(side="left", padx=(8, 4))
        self.url_entry = ctk.CTkEntry(top, width=420, placeholder_text="https://example.com/form-page")
        self.url_entry.pack(side="left", padx=4)
        ctk.CTkLabel(top, text="Email (optional):").pack(side="left", padx=(12, 4))
        self.email_entry = ctk.CTkEntry(top, width=200, placeholder_text="for forms that ask")
        self.email_entry.pack(side="left", padx=4)

        # --- second row: actions + options
        row2 = ctk.CTkFrame(self)
        row2.pack(fill="x", padx=12, pady=4)
        ctk.CTkButton(row2, text="Analyze…", command=self.open_learn).pack(side="left", padx=8)
        ctk.CTkButton(row2, text="Find form…", command=self.open_find).pack(side="left", padx=4)
        self.submit_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(row2, text="Submit form after upload", variable=self.submit_var).pack(
            side="left", padx=(16, 4)
        )
        self.show_browser_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(row2, text="Show browser (debug / CAPTCHA)", variable=self.show_browser_var).pack(
            side="left", padx=(12, 4)
        )

        # --- fingerprint row
        row3 = ctk.CTkFrame(self)
        row3.pack(fill="x", padx=12, pady=2)
        ctk.CTkLabel(row3, text="Known file URL (fingerprint):").pack(side="left", padx=(8, 4))
        self.fp_entry = ctk.CTkEntry(
            row3, width=420, placeholder_text="…/uploads/elementor/forms/uploads/xxx.pdf (optional)"
        )
        self.fp_entry.pack(side="left", padx=4)
        self.fp_lbl = ctk.CTkLabel(row3, text="")
        self.fp_lbl.pack(side="left", padx=8)
        self.fp_entry.bind("<FocusOut>", lambda _e: self._update_fp())
        self.fp_entry.bind("<Return>", lambda _e: self._update_fp())

        # --- file list buttons
        mid = ctk.CTkFrame(self)
        mid.pack(fill="x", padx=12, pady=4)
        ctk.CTkButton(mid, text="Add PDFs…", command=self.add_pdfs).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(mid, text="Add folder…", command=self.add_folder).pack(side="left", padx=4, pady=8)
        ctk.CTkButton(mid, text="Clear list", command=self.clear_pdfs).pack(side="left", padx=4, pady=8)
        self.count_lbl = ctk.CTkLabel(mid, text="0 files")
        self.count_lbl.pack(side="left", padx=16)
        ctk.CTkButton(mid, text="📋 Copy Extracted URLs", command=self.copy_urls).pack(
            side="right", padx=8, pady=8
        )

        # --- panes
        paned = ctk.CTkFrame(self)
        paned.pack(fill="both", expand=True, padx=12, pady=4)
        paned.columnconfigure(0, weight=1)
        paned.columnconfigure(1, weight=1)
        paned.rowconfigure(1, weight=1)
        ctk.CTkLabel(paned, text="PDF queue").grid(row=0, column=0, sticky="w", padx=8)
        ctk.CTkLabel(paned, text="Progress / extracted URLs").grid(row=0, column=1, sticky="w", padx=8)
        self.file_box = ctk.CTkTextbox(paned, state="disabled")
        self.file_box.grid(row=1, column=0, sticky="nsew", padx=(8, 4), pady=(0, 8))
        self.log_box = ctk.CTkTextbox(paned, state="disabled")
        self.log_box.grid(row=1, column=1, sticky="nsew", padx=(4, 8), pady=(0, 8))

        # --- bottom
        bot = ctk.CTkFrame(self)
        bot.pack(fill="x", padx=12, pady=(4, 12))
        self.go_btn = ctk.CTkButton(
            bot, text="GO — Upload", height=40, font=("", 16, "bold"), command=self.start
        )
        self.go_btn.pack(side="left", padx=8, pady=8)
        self.status_lbl = ctk.CTkLabel(bot, text="Ready")
        self.status_lbl.pack(side="left", padx=16)

        self.after(100, self._poll)

    # ---------- helpers ----------
    def _update_fp(self):
        fp = self.fp_entry.get().strip()
        if not fp:
            self.fp_lbl.configure(text="")
            return
        label = fingerprint_from_file_url(fp)
        self.fp_lbl.configure(
            text=f"detected: {label}" if label else "custom upload path active",
            text_color=("green" if label else "orange"),
        )

    def _fingerprint(self):
        fp = self.fp_entry.get().strip()
        return fingerprint_from_file_url(fp) if fp else None

    def copy_urls(self):
        if not self.uploaded_urls:
            messagebox.showinfo("No URLs", "No uploaded file URLs captured yet.")
            return
        self.clipboard_clear()
        self.clipboard_append("\n".join(self.uploaded_urls))
        self.status_lbl.configure(text=f"Copied {len(self.uploaded_urls)} URL(s) to clipboard!")

    # ---------- find form dialog ----------
    def open_find(self):
        win = ctk.CTkToplevel(self)
        win.title("Find upload form")
        win.geometry("780x560")
        win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="Paste the site's base URL (e.g. https://www.example.com/)").pack(
            padx=12, pady=(12, 4), anchor="w"
        )
        row = ctk.CTkFrame(win)
        row.pack(fill="x", padx=12, pady=4)
        entry = ctk.CTkEntry(row, width=460, placeholder_text="https://example.com/")
        entry.pack(side="left", padx=4)
        if self.url_entry.get().strip():
            entry.insert(0, self.url_entry.get().strip())
        out = ctk.CTkTextbox(win, state="disabled", height=300)
        out.pack(fill="both", expand=True, padx=12, pady=8)
        self._find_out = out

        mode = ctk.StringVar(value="js")
        moderow = ctk.CTkFrame(win)
        moderow.pack(fill="x", padx=12, pady=2)
        ctk.CTkRadioButton(
            moderow, text="Crawl + JS render (recommended)", variable=mode, value="js"
        ).pack(side="left", padx=4)
        ctk.CTkRadioButton(
            moderow, text="Concurrent HTML Crawl (fast)", variable=mode, value="crawl"
        ).pack(side="left", padx=4)
        ctk.CTkRadioButton(
            moderow, text="Keyword search", variable=mode, value="kw"
        ).pack(side="left", padx=4)

        fp_note = ctk.CTkLabel(win, text="")
        fp_note.pack(padx=12, anchor="w")
        fp = self._fingerprint()
        if fp:
            fp_note.configure(text=f"Fingerprint active: prioritizing {fp} signatures")

        def do_find():
            base = entry.get().strip()
            if not base.startswith("http"):
                base = "https://" + base
            self._write(out, f"Searching {base}…\n")
            prio = self._fingerprint()

            def work():
                try:
                    def log(m):
                        self.q.put(("__FIND__", m + "\n"))

                    m = mode.get()
                    if m == "kw":
                        results = find_forms_keyword(base, log=log, prioritize=prio)
                    elif m == "js":
                        results = find_forms_js(base, log=log, prioritize=prio)
                    else:
                        results = find_forms(base, log=log, prioritize=prio)
                    if not results:
                        self.q.put(
                            ("__FIND__", "\nNo upload forms found with this mode — try JS mode if you used crawl.\n")
                        )
                    else:
                        self.q.put(("__FIND__", f"\n=== {len(results)} form page(s) ===\n"))
                        for u, mk, sc in results:
                            self.q.put(("__FIND__", f"[score {sc}] {u}  ({', '.join(mk)})\n"))
                        self.q.put(("__FINDURL__", results[0][0]))
                except Exception as e:
                    self.q.put(("__FIND__", f"Error: {e}\n"))

            threading.Thread(target=work, daemon=True).start()

        def use_url():
            if self._find_first_url:
                self.url_entry.delete(0, "end")
                self.url_entry.insert(0, self._find_first_url)
                win.destroy()

        btnrow = ctk.CTkFrame(win)
        btnrow.pack(fill="x", padx=12, pady=(0, 12))
        ctk.CTkButton(btnrow, text="Find forms", command=do_find).pack(side="left", padx=4)
        ctk.CTkButton(btnrow, text="Use top result as Target URL", command=use_url).pack(side="left", padx=12)

    # ---------- analyze dialog ----------
    def open_learn(self):
        win = ctk.CTkToplevel(self)
        win.title("Analyze site")
        win.geometry("660x420")
        win.attributes("-topmost", True)
        ctk.CTkLabel(win, text="Paste the form page URL, click Analyze.").pack(padx=12, pady=(12, 4), anchor="w")
        row = ctk.CTkFrame(win)
        row.pack(fill="x", padx=12, pady=4)
        entry = ctk.CTkEntry(row, width=460, placeholder_text="https://example.com/form-page")
        entry.pack(side="left", padx=4)
        if self.url_entry.get().strip():
            entry.insert(0, self.url_entry.get().strip())
        out = ctk.CTkTextbox(win, state="disabled", height=240)
        out.pack(fill="both", expand=True, padx=12, pady=8)
        self._learn_out = out

        def do_analyze():
            url = entry.get().strip()
            if not url.startswith("http"):
                url = "https://" + url
            self._write(out, "Analyzing…")

            def work():
                try:
                    info = analyze_site(url)
                    lines = [
                        f"HTTP status : {info['status']}",
                        f"Detected    : {info['type']}",
                        f"CAPTCHA     : {'YES — submission may be blocked' if info['captcha'] else 'no'}",
                        "",
                        info["detail"],
                        "",
                        "Paste this URL as Target URL and click GO.",
                    ]
                    txt = "\n".join(lines)
                except Exception as e:
                    txt = f"Analysis failed: {e}"
                self.q.put(("__LEARN__", txt))

            threading.Thread(target=work, daemon=True).start()

        ctk.CTkButton(win, text="Analyze Page", command=do_analyze).pack(padx=12, pady=(0, 12), anchor="w")

    # ---------- file list ----------
    def add_pdfs(self):
        self.pdf_paths.extend(filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")]))
        self._refresh_files()

    def add_folder(self):
        d = filedialog.askdirectory()
        if d:
            self.pdf_paths.extend(
                os.path.join(d, f) for f in sorted(os.listdir(d)) if f.lower().endswith(".pdf")
            )
            self._refresh_files()

    def clear_pdfs(self):
        self.pdf_paths = []
        self.uploaded_urls = []
        self._refresh_files()
        self._write(self.log_box, "")
        self.status_lbl.configure(text="Ready")

    def _refresh_files(self):
        self.count_lbl.configure(text=f"{len(self.pdf_paths)} files")
        self._write(self.file_box, "\n".join(os.path.basename(p) for p in self.pdf_paths))

    def _write(self, box, text):
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def _append(self, box, text):
        box.configure(state="normal")
        box.insert("end", text)
        box.see("end")
        box.configure(state="disabled")

    def _log(self, msg):
        self.q.put(msg)

    def _poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                if isinstance(item, tuple):
                    kind, val = item
                    if kind == "__STATUS__":
                        self.status_lbl.configure(text=val)
                    elif kind == "__GO__":
                        self.go_btn.configure(state="normal")
                    elif kind == "__LEARN__":
                        out = getattr(self, "_learn_out", None)
                        if out is not None:
                            self._write(out, val)
                    elif kind == "__FIND__":
                        out = getattr(self, "_find_out", None)
                        if out is not None:
                            self._append(out, val)
                    elif kind == "__FINDURL__":
                        self._find_first_url = val
                else:
                    self._append(self.log_box, str(item) + "\n")
        except queue.Empty:
            pass
        self.after(100, self._poll)

    # ---------- run ----------
    def start(self):
        url = self.url_entry.get().strip()
        if not url.startswith("http"):
            messagebox.showwarning("Missing URL", "Enter the form page URL in the Target URL field.")
            return
        if not self.pdf_paths:
            messagebox.showwarning("No PDFs", "Add at least one PDF first.")
            return
        email = self.email_entry.get().strip() or "alex.miller@example.com"
        do_submit = self.submit_var.get()
        headless = not self.show_browser_var.get()
        fp_url = self.fp_entry.get().strip() or None
        pdfs = list(self.pdf_paths)
        self.uploaded_urls = []
        self.go_btn.configure(state="disabled")
        self._write(self.log_box, "")
        self.status_lbl.configure(text="Running…")

        def work():
            try:
                results = generic_upload(
                    url,
                    pdfs,
                    email,
                    self._log,
                    submit_after=do_submit,
                    label="generic",
                    headless=headless,
                    fingerprint_url=fp_url,
                )
                self.uploaded_urls = results
                self._log(f"\n=== DONE: {len(results)}/{len(pdfs)} uploaded ===")
                for u in results:
                    self._log(u)
                self.q.put(("__STATUS__", f"Done: {len(results)}/{len(pdfs)}"))
            except Exception as e:
                self._log(f"\nERROR: {e}")
                self.q.put(("__STATUS__", "Failed"))
            finally:
                self.q.put(("__GO__", None))

        threading.Thread(target=work, daemon=True).start()



# ==============================================================================
# CLOUD ACCESS CONTROL CONFIGURATION (GOOGLE SHEET PERMISSION GATE)
# ==============================================================================
AUTH_SHEET_ID = "1TcPjoKOT4jfH9n0xhxjnKVgCCqV7Y-pgKeGFCXbPmnY"

class CloudLoginWindow:
    def __init__(self, on_success):
        self.on_success = on_success
        self.root = ctk.CTk()
        self.root.title("PDF Uploader v6.0 - Access Verification")
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
        ctk.CTkLabel(card, text="Enter your access credentials to unlock PDF Uploader v6.0.",
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
        import csv, io, urllib.request
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
                    self.root.after(0, self._on_success_login)
                elif status_msg:
                    self._show_err(status_msg)
                else:
                    self._show_err("Invalid username or password.")
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
    CloudLoginWindow(on_success=lambda: App().mainloop()).run()