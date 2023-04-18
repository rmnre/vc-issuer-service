from pathlib import Path

BASE_DIR = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / "templates"
IMAGES_DIR = BASE_DIR / "images"

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 4567
DEFAULT_LOG_LEVEL = "info"
AUTO_REMOVE_CONN_RECORD = True
