from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.main import create_app
from app.openapi import render_swagger_ui_html, write_static_openapi_site


def test_openapi_includes_auth_security_and_source_routes() -> None:
    app = create_app()

    schema = app.openapi()

    assert schema["info"]["title"] == "Czech Audiobookshelf Metadata Provider"
    assert schema["paths"]["/search"]["get"]["tags"] == ["global"]
    assert schema["paths"]["/databazeknih/search"]["get"]["tags"] == ["databazeknih"]
    assert {"AuthorizationHeader": []} in schema["paths"]["/search"]["get"]["security"]
    assert "AuthorizationHeader" in schema["components"]["securitySchemes"]


def test_write_static_openapi_site_creates_github_pages_artifacts() -> None:
    app = create_app()
    output_dir = Path("memory/.tmp_openapi_docs_test")
    if output_dir.exists():
        shutil.rmtree(output_dir)

    try:
        write_static_openapi_site(app=app, output_dir=output_dir)

        openapi_path = output_dir / "openapi.json"
        index_path = output_dir / "index.html"
        nojekyll_path = output_dir / ".nojekyll"

        assert openapi_path.exists()
        assert index_path.exists()
        assert nojekyll_path.exists()

        schema = json.loads(openapi_path.read_text(encoding="utf-8"))
        assert schema["paths"]["/health"]["get"]["tags"] == ["global"]
        assert "./openapi.json" in index_path.read_text(encoding="utf-8")
    finally:
        if output_dir.exists():
            shutil.rmtree(output_dir)


def test_render_swagger_ui_html_points_to_relative_openapi_json() -> None:
    html = render_swagger_ui_html()

    assert "swagger-ui" in html
    assert "./openapi.json" in html
