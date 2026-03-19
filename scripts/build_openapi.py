from __future__ import annotations

from pathlib import Path

from app.main import create_app
from app.openapi import write_static_openapi_site


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    output_dir = project_root / "docs"
    app = create_app()
    write_static_openapi_site(app=app, output_dir=output_dir)


if __name__ == "__main__":
    main()
