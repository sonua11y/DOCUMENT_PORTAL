import json
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLISH_DIR = ROOT / "public"
API_BASE_MARKER = 'const API_BASE = "";'


def main() -> None:
    api_base_url = os.getenv("API_BASE_URL", "").strip().rstrip("/")
    if not api_base_url.startswith("https://"):
        raise ValueError("Set API_BASE_URL to the public HTTPS URL of the FastAPI service.")

    template_path = ROOT / "templates" / "index.html"
    html = template_path.read_text(encoding="utf-8")
    if API_BASE_MARKER not in html:
        raise RuntimeError("Could not find the API base URL setting in templates/index.html.")

    html = html.replace(
        API_BASE_MARKER,
        f"const API_BASE = {json.dumps(api_base_url)};",
        1,
    )
    PUBLISH_DIR.mkdir(parents=True, exist_ok=True)
    (PUBLISH_DIR / "index.html").write_text(html, encoding="utf-8")
    shutil.copytree(ROOT / "static", PUBLISH_DIR / "static", dirs_exist_ok=True)


if __name__ == "__main__":
    main()
