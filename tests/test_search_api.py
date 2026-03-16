from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import AudiobookshelfMatch, SearchResponse
from app.routers.search import get_provider_service, provider_service_dependencies


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


def test_source_specific_search_endpoint_returns_matches_with_dependency_override() -> None:
    app = create_app()
    app.dependency_overrides[provider_service_dependencies["audioteka"]] = lambda: StubProviderService()

    with TestClient(app) as client:
        response = client.get("/audioteka/search", params={"query": "1984"})

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


def test_alza_source_specific_search_endpoint_returns_matches_with_dependency_override() -> None:
    app = create_app()
    app.dependency_overrides[provider_service_dependencies["alza"]] = lambda: StubProviderService()

    with TestClient(app) as client:
        response = client.get("/alza/search", params={"query": "1984"})

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


def test_kanopa_source_specific_search_endpoint_returns_matches_with_dependency_override() -> None:
    app = create_app()
    app.dependency_overrides[provider_service_dependencies["kanopa"]] = lambda: StubProviderService()

    with TestClient(app) as client:
        response = client.get("/kanopa/search", params={"query": "1984"})

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


def test_knihydobrovsky_source_specific_search_endpoint_returns_matches_with_dependency_override() -> None:
    app = create_app()
    app.dependency_overrides[provider_service_dependencies["knihydobrovsky"]] = lambda: StubProviderService()

    with TestClient(app) as client:
        response = client.get("/knihydobrovsky/search", params={"query": "1984"})

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


def test_luxor_source_specific_search_endpoint_returns_matches_with_dependency_override() -> None:
    app = create_app()
    app.dependency_overrides[provider_service_dependencies["luxor"]] = lambda: StubProviderService()

    with TestClient(app) as client:
        response = client.get("/luxor/search", params={"query": "1984"})

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


def test_megaknihy_source_specific_search_endpoint_returns_matches_with_dependency_override() -> None:
    app = create_app()
    app.dependency_overrides[provider_service_dependencies["megaknihy"]] = lambda: StubProviderService()

    with TestClient(app) as client:
        response = client.get("/megaknihy/search", params={"query": "1984"})

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


def test_naposlech_source_specific_search_endpoint_returns_matches_with_dependency_override() -> None:
    app = create_app()
    app.dependency_overrides[provider_service_dependencies["naposlech"]] = lambda: StubProviderService()

    with TestClient(app) as client:
        response = client.get("/naposlech/search", params={"query": "1984"})

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


def test_palmknihy_source_specific_search_endpoint_returns_matches_with_dependency_override() -> None:
    app = create_app()
    app.dependency_overrides[provider_service_dependencies["palmknihy"]] = lambda: StubProviderService()

    with TestClient(app) as client:
        response = client.get("/palmknihy/search", params={"query": "1984"})

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


def test_o2knihovna_source_specific_search_endpoint_returns_matches_with_dependency_override() -> None:
    app = create_app()
    app.dependency_overrides[provider_service_dependencies["o2knihovna"]] = lambda: StubProviderService()

    with TestClient(app) as client:
        response = client.get("/o2knihovna/search", params={"query": "1984"})

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


def test_radioteka_source_specific_search_endpoint_returns_matches_with_dependency_override() -> None:
    app = create_app()
    app.dependency_overrides[provider_service_dependencies["radioteka"]] = lambda: StubProviderService()

    with TestClient(app) as client:
        response = client.get("/radioteka/search", params={"query": "1984"})

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


def test_rozhlas_source_specific_search_endpoint_returns_matches_with_dependency_override() -> None:
    app = create_app()
    app.dependency_overrides[provider_service_dependencies["rozhlas"]] = lambda: StubProviderService()

    with TestClient(app) as client:
        response = client.get("/rozhlas/search", params={"query": "Skořápka"})

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


def test_source_specific_health_endpoint_returns_ok() -> None:
    app = create_app()

    with TestClient(app) as client:
        response = client.get("/onehotbook/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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


def test_disabled_source_endpoint_is_not_registered(monkeypatch) -> None:
    monkeypatch.setenv("ENABLE_ONEHOTBOOK", "false")

    app = create_app()

    with TestClient(app) as client:
        response = client.get("/onehotbook/search", params={"query": "1984"})

    assert response.status_code == 404
