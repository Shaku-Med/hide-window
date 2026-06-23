from pathlib import Path

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def logo_png() -> str | None:
    path = ASSETS_DIR / "logo.png"
    return str(path) if path.exists() else None


def logo_ico() -> str | None:
    path = ASSETS_DIR / "logo.ico"
    return str(path) if path.exists() else None
