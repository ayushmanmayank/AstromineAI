"""One-off verification script (frontend redesign, final/frontend-redesign
branch), not part of the app itself: drives the already-running frontend
dev server with a real browser to confirm each real UI state actually
renders -- not just that the HTTP contract is correct.

Modes:
  empty   -- initial page load, no file chosen yet.
  result  -- a real crop uploaded, a real backend prediction rendered.
  error   -- a request that gets a real backend error response rendered
             (role="alert" panel) -- run this against a backend started
             with ASTROMINE_CHECKPOINT pointing at a path that does not
             exist, so the real, existing 503 "no checkpoint found" path
             fires (not an incidental image-decode crash).
  mobile  -- same as `result`, at a 390px viewport width.

Usage: python scripts/screenshot_frontend_predict.py <mode>
"""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

IMAGE_PATH = str(Path("datasets/processed/0007112__VIR_VIS_1B_1_370617178.png").resolve())
BAD_IMAGE_PATH = str(Path("datasets/processed/0007112__VIR_VIS_1B_1_370617178.png").resolve())
OUT_DIR = Path("docs/handoff/artifacts")
OUT_DIR.mkdir(parents=True, exist_ok=True)

FRONTEND_URL = "http://localhost:5173"


def run(mode: str) -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        if mode == "mobile":
            page.set_viewport_size({"width": 390, "height": 844})
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(FRONTEND_URL, wait_until="networkidle")

        if mode == "empty":
            page.wait_for_selector("text=Choose a Dawn FC image crop on the left")
            page.screenshot(path=str(OUT_DIR / "frontend_redesign_empty.png"), full_page=True)
            print("Saved empty-state screenshot.")

        elif mode in ("result", "mobile"):
            page.set_input_files('input[type="file"]', IMAGE_PATH)
            page.click('button:has-text("Analyze crop")')
            page.wait_for_selector("text=PREDICTION · SYNTHETIC LABEL", timeout=30000)
            out_name = "frontend_redesign_result_390px.png" if mode == "mobile" else "frontend_redesign_result.png"
            page.screenshot(path=str(OUT_DIR / out_name), full_page=True)
            prediction = page.locator(".result-prediction").inner_text()
            print(f"Saved {mode}-state screenshot. Rendered prediction: {prediction!r}")

        elif mode == "error":
            page.set_input_files('input[type="file"]', BAD_IMAGE_PATH)
            page.click('button:has-text("Analyze crop")')
            page.wait_for_selector('[role="alert"]', timeout=30000)
            page.screenshot(path=str(OUT_DIR / "frontend_redesign_error.png"), full_page=True)
            body = page.locator(".error-body").inner_text()
            print(f"Saved error-state screenshot. Rendered error body: {body!r}")

        else:
            raise ValueError(f"Unknown mode: {mode!r}")

        print("Console errors:", console_errors if console_errors else "none")
        browser.close()
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/screenshot_frontend_predict.py <empty|result|error|mobile>")
        sys.exit(1)
    sys.exit(run(sys.argv[1]))
