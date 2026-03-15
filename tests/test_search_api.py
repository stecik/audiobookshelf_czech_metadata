from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import AudiobookshelfMatch, SearchResponse
from app.routers.search import get_provider_service


class StubProviderService:
    async def search(self, *, query: str, author: str | None = None) -> SearchResponse:
        return SearchResponse(
            matches=[
                AudiobookshelfMatch(
                    title="1984",
                    author="George Orwell",
                    narrator="David Novotný",
                )
            ]
        )


def test_health_endpoint_returns_ok() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_endpoint_returns_matches_with_dependency_override() -> None:
    app = create_app()
    app.dependency_overrides[get_provider_service] = lambda: StubProviderService()

    with TestClient(app) as client:
        response = client.get("/search", params={"query": "1984", "author": "George Orwell"})

    assert response.status_code == 200
    assert response.json() == {
        "matches": [
            {
                "title": "1984",
                "author": "George Orwell",
                "narrator": "David Novotný",
            }
        ]
    }


def test_search_endpoint_requires_authorization_when_token_is_configured(monkeypatch) -> None:
    monkeypatch.setenv("AUDIOBOOKSHELF_AUTH_TOKEN", "shared-secret")

    app = create_app()
    app.dependency_overrides[get_provider_service] = lambda: StubProviderService()

    with TestClient(app) as client:
        unauthorized = client.get("/search", params={"query": "1984"})
        authorized = client.get(
            "/search",
            params={"query": "1984"},
            headers={"Authorization": "shared-secret"},
        )

    assert unauthorized.status_code == 401
    assert unauthorized.json() == {"error": "unauthorized"}
    assert authorized.status_code == 200
