"""One-off script (Month 2 engineering pipeline verification, not part of
the app itself): drives the already-running frontend dev server with a
real browser to confirm the /predict response actually renders in the
DOM (prediction, confidence, heatmap image, disclaimer) -- not just that
the HTTP contract is correct (already verified separately via curl)."""

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

IMAGE_PATH = str(Path("datasets/processed/0007112__VIR_VIS_1B_1_370617178.png").resolve())
OUT_DIR = Path("docs/handoff/artifacts")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> int:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto("http://127.0.0.1:5173", wait_until="networkidle")
        page.screenshot(path=str(OUT_DIR / "engineering_frontend_before.png"))

        page.set_input_files('input[type="file"]', IMAGE_PATH)
        page.click('button:has-text("Predict")')
        page.wait_for_selector("text=Prediction:", timeout=30000)
        page.wait_for_selector('img[alt="Grad-CAM heatmap"]')

        page.screenshot(path=str(OUT_DIR / "engineering_frontend_after_predict.png"), full_page=True)

        prediction_text = page.locator("p:has-text('Prediction:')").inner_text()
        disclaimer_text = page.locator('p:has-text("This prediction is")').inner_text()
        print("Rendered prediction paragraph:", prediction_text)
        print("Rendered disclaimer:", disclaimer_text[:120], "...")
        print("Console errors:", console_errors if console_errors else "none")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
