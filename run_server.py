import importlib.util
from pathlib import Path
import sys
import uvicorn

# Load local api.main by file path to avoid name-collision with other projects
ROOT = Path(__file__).resolve().parent
API_MAIN = ROOT / "api" / "main.py"

if not API_MAIN.exists():
    raise FileNotFoundError(f"Cannot find {API_MAIN}")

spec = importlib.util.spec_from_file_location("api.main", str(API_MAIN))
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
app = getattr(module, "app")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
