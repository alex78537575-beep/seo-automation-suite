# 📄 PDF Uploader & Concurrent Form Crawler v6.0

Universal Multi-Strategy File Uploader & Priority BFS Form Discovery Engine:
- **High-Speed Concurrent Form Crawler (`find_form.py`)**: Priority BFS queue with `ThreadPoolExecutor`, gzipped `.xml.gz` sitemap parsing, root-domain matching, and deep iframe inspection across 15+ form plugins (`Dropzone`, `FilePond`, `Uppy`, `WPForms`, `Elementor`, `Gravity Forms`, `Contact Form 7`, `HubSpot`, `Jotform`, `Drupal Webform`).
- **Frame-Aware Multi-Strategy Uploader (`pdf_uploader.py`)**: Attaches files to hidden `<input type="file">` elements and dynamic `expect_file_chooser()` dropzones across nested iframes, auto-fills required fields, and captures live uploaded PDF URLs.
- **Cloud Access Control Gate**: Protected by real-time Google Sheet credential verification.

## Run
```bash
pip install -r requirements.txt
playwright install chromium
python pdf_uploader.py
```
