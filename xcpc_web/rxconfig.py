from pathlib import Path

import reflex as rx

_repo_root = Path(__file__).resolve().parent.parent
_db_path = _repo_root / "data" / "db" / "xcpc_web.db"
_db_path.parent.mkdir(parents=True, exist_ok=True)

config = rx.Config(
    app_name="xcpc_web",
    db_url=f"sqlite:///{_db_path}",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.RadixThemesPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)