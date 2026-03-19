from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI


OPENAPI_TITLE = "Czech Audiobookshelf Metadata Provider"
OPENAPI_DESCRIPTION = (
    "Custom metadata provider API for Audiobookshelf. "
    "It exposes a global search endpoint across enabled sources and source-specific "
    "search endpoints for individual storefronts."
)
OPENAPI_SERVERS = [
    {"url": "http://localhost:8000", "description": "Local development"},
    {"url": "http://provider:8000", "description": "Docker network service name"},
]
OPENAPI_TAGS = [
    {"name": "global", "description": "Combined search across globally enabled sources."},
    {"name": "alza", "description": "Alza audiobook provider endpoints."},
    {"name": "albatrosmedia", "description": "Albatros Media audiobook provider endpoints."},
    {"name": "audiolibrix", "description": "Audiolibrix audiobook provider endpoints."},
    {"name": "audioteka", "description": "Audioteka audiobook provider endpoints."},
    {
        "name": "databazeknih",
        "description": "Databaze knih book-metadata fallback endpoints for custom audiobooks.",
    },
    {"name": "kanopa", "description": "Kanopa audiobook provider endpoints."},
    {"name": "knihydobrovsky", "description": "Knihy Dobrovsky audiobook provider endpoints."},
    {"name": "kosmas", "description": "Kosmas audiobook provider endpoints."},
    {"name": "luxor", "description": "Luxor audiobook provider endpoints."},
    {"name": "megaknihy", "description": "Megaknihy audiobook provider endpoints."},
    {"name": "naposlech", "description": "Naposlech audiobook provider endpoints."},
    {"name": "onehotbook", "description": "OneHotBook audiobook provider endpoints."},
    {"name": "o2knihovna", "description": "O2 Knihovna audiobook provider endpoints."},
    {"name": "palmknihy", "description": "Palmknihy audiobook provider endpoints."},
    {"name": "progresguru", "description": "ProgresGuru audiobook provider endpoints."},
    {"name": "radioteka", "description": "Radioteka audiobook provider endpoints."},
    {"name": "rozhlas", "description": "Rozhlas audio and radio-drama provider endpoints."},
]

SWAGGER_UI_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <link
      rel="stylesheet"
      href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css"
    />
    <style>
      html {{
        box-sizing: border-box;
        overflow-y: scroll;
      }}

      *,
      *::before,
      *::after {{
        box-sizing: inherit;
      }}

      body {{
        margin: 0;
        background: #f6f8fb;
      }}
    </style>
  </head>
  <body>
    <div id="swagger-ui"></div>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
    <script>
      window.ui = SwaggerUIBundle({{
        url: "./openapi.json",
        dom_id: "#swagger-ui",
        deepLinking: true,
        displayRequestDuration: true,
        docExpansion: "list",
        persistAuthorization: true,
        presets: [
          SwaggerUIBundle.presets.apis,
          SwaggerUIStandalonePreset
        ],
        layout: "StandaloneLayout"
      }});
    </script>
  </body>
</html>
"""


def render_swagger_ui_html(*, title: str = OPENAPI_TITLE) -> str:
    return SWAGGER_UI_HTML.format(title=title)


def build_openapi_document(app: FastAPI) -> dict[str, object]:
    return app.openapi()


def write_static_openapi_site(*, app: FastAPI, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    openapi_document = build_openapi_document(app)
    (output_dir / "openapi.json").write_text(
        json.dumps(openapi_document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "index.html").write_text(
        render_swagger_ui_html(title=str(openapi_document["info"]["title"])),
        encoding="utf-8",
    )
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
