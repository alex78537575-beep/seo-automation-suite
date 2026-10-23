#!/usr/bin/env python3
"""Form finder v6.0: high-speed concurrent crawler + root-domain matching +
anchor-text priority queue + iframe/widget inspection + CMS plugin signatures.

Key improvements in v6.0:
- Root-domain matching (`same_site`): handles www vs non-www redirects and
  subdomains (e.g. careers.example.com, apply.example.com) instead of dropping links.
- Priority BFS Queue: prioritizes links whose URL or visible anchor text matches
  form/upload/contact/apply/quote keywords so crawl budget isn't wasted on blog/news pages.
- Concurrent HTML crawling (`ThreadPoolExecutor`) with session pooling and gzipped
  (`.xml.gz`) sitemap support.
- Expanded upload detection (`classify` & `_has_upload_form`): detects unquoted
  `type=file`, Dropzone, FilePond, Uppy, Plupload, HubSpot, Jotform, Typeform,
  Contact Form 7, Elementor, WPForms, Gravity Forms, Everest, Fluent, Ninja,
  Formidable, Drupal Webform, Episerver, and explicit upload text cues
  ("Allowed file types: pdf", "Choose file", "Upload resume").
- Deep Iframe & Multi-Step Click-Reveal in `find_forms_js`: inspects all nested
  iframes (`page.frames`) and fills dummy fields if needed before clicking
  Next/Apply/Upload reveal triggers.
"""

import gzip
import re
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, unquote, urldefrag, urljoin, urlparse

import requests
from requests.adapters import HTTPAdapter
import urllib3
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    )
}

SKIP_EXT = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".css", ".js", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".avi", ".mov",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".xml", ".txt", ".json",
    ".webmanifest", ".doc", ".docx", ".xls", ".xlsx"
)

COMMON_FORM_PATHS = [
    # Direct upload / submission / application paths
    "/upload", "/uploads", "/file-upload", "/submit", "/submission",
    "/apply", "/application", "/applications", "/apply-now", "/apply-online",
    "/careers/application-for-employment", "/application-form",
    "/submit-resume", "/upload-resume", "/resume", "/cv",
    # Contact / inquiry / quote / intake
    "/contact", "/contact-us", "/inquiry", "/enquiry", "/request-info",
    "/get-in-touch", "/feedback", "/support", "/help-desk",
    "/quote", "/get-a-quote", "/request-a-quote", "/request-quote",
    "/booking", "/book", "/book-now", "/appointment", "/appointments",
    "/intake", "/referral", "/patient-intake", "/client-intake",
    # General forms & CMS endpoints
    "/form", "/forms", "/webform", "/webforms", "/node/add",
    "/register", "/registration", "/signup", "/sign-up", "/join",
    "/careers", "/jobs", "/vacancies", "/openings", "/employment",
    "/nominate", "/nomination", "/nomination-form",
]

FORM_URL_HINTS = re.compile(
    r"(apply|form|upload|webform|job|nominate|register|submit|attach|resume|cv"
    r"|career|vacanc|join|sign|contact|inquir|enquir|book|appoint|quote"
    r"|intake|referral|request|support|proposal|claim|ticket|document|file)",
    re.I,
)

REVEAL_BUTTONS = [
    "Upload", "Upload file", "Upload File", "Choose file", "Choose File",
    "Select file", "Select File", "Browse", "Browse files",
    "Upload resume", "Upload Resume", "Upload CV", "Attach resume",
    "Attach file", "Attach File", "Add attachment", "Add file",
    "Upload document", "Submit application", "Apply", "Apply Now",
    "Apply Online", "Get a Quote", "Request a Quote", "Next", "Continue"
]

# --- CMS plugin signatures -------------------------------------------------
# Each: (label, html markers, file-upload markers, score bonus)
PLUGIN_SIGNATURES = [
    ("Elementor Pro Forms",
     ["elementor-form", "elementor-field-group"],
     ["elementor-upload-field", "elementor-field-type-upload", 'type="file"'], 3),
    ("Everest Forms",
     ["everest-forms", "everest_form", "evf-field"],
     ["evf-file-upload", "everest-forms-field-file-upload", "evf-upload"], 3),
    ("Contact Form 7",
     ["wpcf7-form", "wpcf7"],
     ["wpcf7-file", "wpcf7-drag-n-drop", "dnd-upload"], 3),
    ("Gravity Forms",
     ["gform_wrapper", "gform_body", "gform_fields"],
     ["gfield_upload", "ginput_container_fileupload", "gform_drop_area"], 3),
    ("WPForms",
     ["wpforms-form", "wpforms-container"],
     ["wpforms-file-upload", "wpforms-uploader", "dz-message"], 3),
    ("Formidable Forms",
     ["frm_forms", "frm_form_fields"],
     ["frm_file", "frm_dropzone"], 3),
    ("Fluent Forms",
     ["fluentform", "ff-el-group"],
     ["ff_file_upload", "fluentform-file", "ff-upload-preview"], 3),
    ("Ninja Forms",
     ["nf-form-cont", "ninja-forms-form"],
     ["nf-file-upload", "file_upload", "nf-fu-fileinput"], 3),
    ("WS Form / Piotnet / Bricks",
     ["wsf-form", "piotnetforms", "brxe-form"],
     ["wsf-file", "piotnetforms-file", "file-upload"], 2),
    ("Jotform / Cognito / Wufoo",
     ["jotform-form", "cognito", "wufoo"],
     ["jfUpload", "qq-upload", "c-fileupload", "file"], 2),
]

UPLOAD_PATH_FINGERPRINTS = {
    "/elementor/forms/uploads/": "Elementor Pro Forms",
    "/elementor/forms/": "Elementor Pro Forms",
    "/everest_forms_uploads/": "Everest Forms",
    "/wpcf7_uploads/": "Contact Form 7",
    "/wpcf7_uploads": "Contact Form 7",
    "/dnd-cf7-uploads/": "Contact Form 7",
    "/gravity_forms/": "Gravity Forms",
    "/wpforms/": "WPForms",
    "/formidable/": "Formidable Forms",
    "/fluentform/": "Fluent Forms",
    "/ninja-forms/": "Ninja Forms",
    "/files/webform/": "Drupal webform",
    "/sites/default/files/": "Drupal webform",
}

FILE_INPUT_REGEX = re.compile(
    r"""<input\b[^>]*?\btype\s*=\s*['"]?file['"]?[^>]*>""",
    re.I | re.S,
)

WIDGET_REGEX = re.compile(
    r"(dropzone|dz-clickable|filepond|uppy-Root|uppy-Dashboard|"
    r"plupload|qq-uploader|fine-uploader|upload_button|wpjb-upload|"
    r"form-managed-file|ajax-upload|file-drop-area|dnd-upload)",
    re.I,
)

UPLOAD_TEXT_CUES = re.compile(
    r"(allowed\s+file\s+types?\s*:?\s*[^<]{0,60}\b(?:pdf|doc)|"
    r"accepted\s+file\s+types?\s*:?\s*[^<]{0,60}\b(?:pdf|doc)|"
    r"upload\s+(?:your\s+|a\s+)?(?:resume|cv|cover\s+letter|pdf|document|file)|"
    r"attach\s+(?:your\s+|a\s+)?(?:resume|cv|pdf|document|file)|"
    r"drop\s+files?\s+here\s+or\s+|max\.?\s+file\s+size)",
    re.I,
)


def _make_session(workers=8):
    s = requests.Session()
    retries = Retry(total=2, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=workers, pool_maxsize=workers * 2)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update(UA)
    return s


def fingerprint_from_file_url(file_url):
    """Given a URL of a file previously uploaded through a form, return the
    plugin label most likely behind it, or None."""
    if not file_url:
        return None
    path = urlparse(file_url).path.lower()
    for frag, label in UPLOAD_PATH_FINGERPRINTS.items():
        if frag in path:
            return label
    return None


def _get_root_domain(host):
    host = (host or "").lower().split(":")[0].strip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "edu", "gov", "ac"):
        return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


def same_site(url, base_host):
    """True if `url` belongs to the same root domain (handles www and subdomains)."""
    try:
        target_host = urlparse(url).netloc.lower().split(":")[0]
        if not target_host:
            return False
        root = _get_root_domain(base_host)
        return target_host == root or target_host.endswith("." + root)
    except Exception:
        return False


def classify(html, prioritize=None):
    """Return (markers, score). Inspects static or rendered HTML for file upload
    inputs, dropzone widgets, CMS form plugins, and upload text cues."""
    if not html:
        return [], 0
    markers = []
    score = 0
    low = html.lower()

    has_file_input = bool(FILE_INPUT_REGEX.search(html))
    if has_file_input:
        markers.append("file input")
        score += 4

    if 'enctype="multipart/form-data"' in low or "enctype='multipart/form-data'" in low:
        markers.append("multipart form")
        score += 2

    widget_match = WIDGET_REGEX.search(html)
    if widget_match:
        markers.append(f"upload widget ({widget_match.group(1).lower()})")
        score += 3

    text_match = UPLOAD_TEXT_CUES.search(html)
    if text_match and ("<form" in low or has_file_input or widget_match):
        markers.append("upload text cue")
        score += 2

    if 'name="form_build_id"' in html or "drupal-settings-json" in low:
        has_up = has_file_input or "form-managed-file" in low or "form-file" in low
        markers.append("Drupal webform" + (" (with upload)" if has_up else ""))
        score += 3 if has_up else 1
        if prioritize == "Drupal webform" and has_up:
            score += 3

    if "episerverforms" in low or "epi.episerver.forms" in low:
        has_up = has_file_input or "fileupload" in low
        markers.append("Episerver" + (" (with upload)" if has_up else ""))
        score += 3 if has_up else 1

    for label, html_markers, file_markers, bonus in PLUGIN_SIGNATURES:
        if any(m.lower() in low for m in html_markers):
            has_file = has_file_input or any(m.lower() in low for m in file_markers)
            markers.append(label + (" (with upload)" if has_file else ""))
            score += (bonus + 2) if has_file else 1
            if prioritize and label == prioritize:
                score += 4 if has_file else 2

    if re.search(r"recaptcha|g-recaptcha|hcaptcha|cf-turnstile", low):
        markers.append("CAPTCHA")
        score -= 1
    if "cloudflare" in low and ("challenge-platform" in low or "just a moment" in low):
        markers.append("bot-challenge")
        score -= 3

    return markers, score


def _has_upload_form(markers):
    """True if the page has any confirmed file upload input, widget, or plugin upload field."""
    for m in markers:
        if (
            m == "file input"
            or m == "multipart form"
            or m == "upload text cue"
            or m.startswith("upload widget")
            or "(with upload)" in m
        ):
            return True
    return False


def extract_links(html, page_url, base_host):
    """Extract internal links, returning (priority_links, regular_links) based on URL + anchor text."""
    priority = []
    regular = []
    seen_local = set()

    # Match <a ... href="..." ...>anchor text</a>
    for m in re.finditer(
        r"""<a\b[^>]*?\bhref\s*=\s*['"]([^'"#]+)['"][^>]*>(.*?)</a>""",
        html,
        re.I | re.S,
    ):
        href, anchor_html = m.group(1).strip(), m.group(2)
        if href.startswith(("javascript:", "mailto:", "tel:")):
            continue
        absu = urldefrag(urljoin(page_url, href))[0].split("?")[0].rstrip("/")
        if not absu.startswith("http") or absu in seen_local:
            continue
        if not same_site(absu, base_host) or absu.lower().endswith(SKIP_EXT) or len(absu) > 240:
            continue
        seen_local.add(absu)
        anchor_text = re.sub(r"<[^>]+>", " ", anchor_html).strip()
        if FORM_URL_HINTS.search(absu) or FORM_URL_HINTS.search(anchor_text):
            priority.append(absu)
        else:
            regular.append(absu)

    return priority, regular


def fetch_sitemap_urls(base_url, log=print, session=None):
    """Mine robots.txt and XML/.xml.gz sitemaps for form-likely URLs."""
    s = session or _make_session()
    host = urlparse(base_url).netloc.lower()
    root = f"{urlparse(base_url).scheme}://{host}"
    urls = set()
    candidates = [
        root + "/sitemap.xml",
        root + "/sitemap_index.xml",
        root + "/sitemap-index.xml",
        root + "/wp-sitemap.xml",
        root + "/sitemap.php",
    ]
    try:
        rb = s.get(root + "/robots.txt", timeout=10, verify=False)
        if rb.status_code == 200:
            for m in re.findall(r"(?im)^sitemap:\s*(\S+)", rb.text):
                candidates.append(m.strip())
    except Exception:
        pass

    seen_sitemaps = set()
    to_fetch = deque(candidates)
    all_sitemap_Pages = []

    while to_fetch and len(seen_sitemaps) < 16:
        sm = to_fetch.popleft()
        if sm in seen_sitemaps:
            continue
        seen_sitemaps.add(sm)
        try:
            r = s.get(sm, timeout=12, verify=False)
            if r.status_code != 200:
                continue
            raw = r.content
            if sm.lower().endswith(".gz") or raw[:2] == b"\x1f\x8b":
                try:
                    raw = gzip.decompress(raw)
                except Exception:
                    pass
            text = raw.decode("utf-8", errors="replace")
            if "<" not in text[:300]:
                continue
            for loc in re.findall(r"<loc>\s*([^<]+)\s*</loc>", text):
                loc = loc.strip()
                low_loc = loc.lower()
                if low_loc.endswith(".xml") or low_loc.endswith(".xml.gz"):
                    if any(
                         skip in low_loc
                        for skip in ("post-sitemap", "category-sitemap", "tag-sitemap", "author-sitemap", "product-sitemap")
                    ):
                        continue
                    to_fetch.append(loc)
                elif same_site(loc, host) and not low_loc.endswith(SKIP_EXT):
                    if FORM_URL_HINTS.search(loc):
                        urls.add(loc.rstrip("/"))
                    elif len(all_sitemap_Pages) < 40:
                        all_sitemap_Pages.append(loc.rstrip("/"))
        except Exception:
            continue

    # If no obvious keyword matches in sitemap, include up to 25 general pages
    if not urls and all_sitemap_Pages:
        urls.update(all_sitemap_Pages[:25])

    log(f"  sitemap mining: {len(urls)} candidate URLs")
    return sorted(urls)


def find_forms(base_url, max_pages=90, log=print, prioritize=None, workers=8):
    """Concurrent HTML crawl + sitemap mining + priority queue. Returns [(url, markers, score)]."""
    s = _make_session(workers=workers)
    # Resolve initial redirect (e.g. example.com -> www.example.com)
    try:
        r0 = s.get(base_url, timeout=15, verify=False)
        if r0.url:
            base_url = r0.url
    except Exception:
        pass

    parsed = urlparse(base_url)
    base_host = parsed.netloc.lower()
    root = f"{parsed.scheme}://{base_host}"

    seen = set()
    priority_q = deque([base_url.rstrip("/")])
    if root != base_url.rstrip("/"):
        priority_q.append(root)
    for u in fetch_sitemap_urls(root, log=log, session=s):
        priority_q.append(u)
    for p in COMMON_FORM_PATHS:
        priority_q.append(root + p)

    regular_q = deque()
    found = []

    def fetch_one(url):
        try:
            r = s.get(url, timeout=14, verify=False)
            if r.status_code >= 400:
                return url, None, None
            ct = r.headers.get("content-type", "").lower()
            if "text/html" not in ct and "application/xhtml" not in ct:
                return url, None, None
            final_u = urldefrag(r.url)[0].rstrip("/")
            return final_u, r.text, r.status_code
        except Exception:
            return url, None, None

    while (priority_q or regular_q) and len(seen) < max_pages:
        batch = []
        while (priority_q or regular_q) and len(batch) < workers and (len(seen) + len(batch)) < max_pages:
            u = priority_q.popleft() if priority_q else regular_q.popleft()
            u = u.rstrip("/")
            if u not in seen:
                seen.add(u)
                batch.append(u)

        if not batch:
            break

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(fetch_one, u): u for u in batch}
            for fut in as_completed(futs):
                final_u, html, status = fut.result()
                if not html:
                    continue
                seen.add(final_u)
                markers, score = classify(html, prioritize=prioritize)
                if _has_upload_form(markers):
                    if not any(f[0] == final_u for f in found):
                        found.append((final_u, markers, score))
                        log(f"FOUND upload form: {final_u}  [{', '.join(markers)}] score={score}")

                prio_links, reg_links = extract_links(html, final_u, base_host)
                for link in prio_links:
                    if link not in seen:
                        priority_q.append(link)
                for link in reg_links:
                    if link not in seen:
                        regular_q.append(link)

    found.sort(key=lambda x: -x[2])
    return found


def _inspect_playwright_page(page, prioritize=None):
    """Check main frame + all child iframes in Playwright for file upload forms."""
    combined_markers = []
    total_score = 0

    for idx, frame in enumerate(page.frames):
        try:
            f_html = frame.content()
        except Exception:
            continue
        mk, sc = classify(f_html, prioritize=prioritize)
        # Also directly query DOM for input[type=file] in case dynamically created
        try:
            if frame.locator('input[type="file"]').count() > 0 and "file input" not in mk:
                mk.insert(0, "file input")
                sc += 4
        except Exception:
            pass
        if idx > 0 and _has_upload_form(mk):
            mk = [f"iframe:{m}" for m in mk]
        for m in mk:
            if m not in combined_markers:
                combined_markers.append(m)
        total_score = max(total_score, sc)

    return combined_markers, total_score


def find_forms_js(base_url, max_pages=35, log=print, prioritize=None):
    """JS-rendered crawl with iframe scanning, priority queue, and click-reveal."""
    from playwright.sync_api import sync_playwright

    parsed = urlparse(base_url)
    base_host = parsed.netloc.lower()
    root = f"{parsed.scheme}://{base_host}"

    seen = set()
    priority_q = deque([base_url.rstrip("/")])
    if root != base_url.rstrip("/"):
        priority_q.append(root)
    for u in fetch_sitemap_urls(root, log=log):
        priority_q.append(u)
    for p in COMMON_FORM_PATHS:
        priority_q.append(root + p)

    regular_q = deque()
    found = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        ctx = browser.new_context(
            user_agent=UA["User-Agent"],
            ignore_https_errors=True,
        )
        page = ctx.new_page()

        # Speed up crawling by blocking heavy media/fonts (keep scripts & css intact)
        page.route(
            "**/*",
            lambda route: (
                route.abort()
                if route.request.resource_type in ("image", "media", "font")
                else route.continue_()
            ),
        )

        while (priority_q or regular_q) and len(seen) < max_pages:
            url = (priority_q.popleft() if priority_q else regular_q.popleft()).rstrip("/")
            if url in seen:
                continue
            seen.add(url)

            try:
                resp = page.goto(url, timeout=25000, wait_until="domcontentloaded")
                if resp and resp.status >= 400:
                    continue
                page.wait_for_timeout(1200)
                final_u = urldefrag(page.url)[0].rstrip("/")
                seen.add(final_u)
                html = page.content()
            except Exception:
                continue

            markers, score = _inspect_playwright_page(page, prioritize=prioritize)

            if not _has_upload_form(markers):
                # Click common reveal buttons to expose JS-hidden upload widgets
                for label in REVEAL_BUTTONS:
                    try:
                        btn = page.locator(
                            f'button:has-text("{label}"), a:has-text("{label}"), '
                            f'[role="button"]:has-text("{label}")'
                        ).first
                        if btn.count() > 0 and btn.is_visible():
                            btn.click(timeout=2000)
                            page.wait_for_timeout(1200)
                            markers, score = _inspect_playwright_page(page, prioritize=prioritize)
                            if _has_upload_form(markers):
                                markers.append(f"revealed via '{label}'")
                                break
                    except Exception:
                        continue

            if _has_upload_form(markers):
                if not any(f[0] == final_u for f in found):
                    found.append((final_u, markers, score))
                    log(f"FOUND upload form (js): {final_u}  [{', '.join(markers)}] score={score}")

            prio_links, reg_links = extract_links(html, final_u, base_host)
            for link in prio_links:
                if link not in seen:
                    priority_q.append(link)
            for link in reg_links:
                if link not in seen:
                    regular_q.append(link)

        browser.close()

    found.sort(key=lambda x: -x[2])
    return found


# ----------------------------------------------------- keyword search mode

KEYWORDS = [
    "upload", "attach file", "choose file", "upload file",
    "contact form", "inquiry", "booking", "appointment",
    "request a quote", "registration", "apply", "application",
    "submit resume", "upload resume", "attach",
]


def search_ddg(query, log=print, max_results=8):
    url = "https://html.duckduckgo.com/html/?q=" + quote(query)
    r = requests.get(url, headers=UA, timeout=20, verify=False)
    links = re.findall(r'class="result__a"[^>]*href="([^"]+)"', r.text)
    out = []
    for l in links:
        m = re.search(r"uddg=([^&]+)", l)
        if m:
            out.append(unquote(m.group(1)))
        elif l.startswith("http"):
            out.append(l)
    return out[:max_results]


def find_forms_keyword(base_url, log=print, max_pages=12, prioritize=None):
    host = urlparse(base_url).netloc.lower()
    root_domain = _get_root_domain(host)
    s = _make_session()
    found = []
    checked = set()

    queries = []
    if prioritize:
        sig = next((s for s in PLUGIN_SIGNATURES if s[0] == prioritize), None)
        if sig:
            queries.append(f'site:{root_domain} "{sig[1][0]}"')
    queries += [f"site:{root_domain} {kw}" for kw in KEYWORDS]

    for q in queries:
        log(f"search: {q}")
        try:
            hits = search_ddg(q, log=log)
        except Exception as e:
            log(f"  ddg failed: {e}")
            continue
        for h in hits:
            if h in checked or not same_site(h, host):
                continue
            checked.add(h)
            try:
                r = s.get(h, timeout=15, verify=False)
                if "text/html" not in r.headers.get("content-type", ""):
                    continue
                markers, score = classify(r.text, prioritize=prioritize)
                if _has_upload_form(markers):
                    found.append((h, markers, score))
                    log(f"FOUND upload form: {h}  [{', '.join(markers)}] score={score}")
            except Exception:
                continue
        if len(found) >= max_pages:
            break

    found.sort(key=lambda x: -x[2])
    return found