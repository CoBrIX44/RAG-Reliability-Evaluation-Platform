from collections.abc import Iterator

from fastapi.testclient import TestClient
from rag_api.main import create_app
from rag_core.settings import Settings


def test_request_body_limit_rejects_before_database_access() -> None:
    with TestClient(create_app(Settings(_env_file=None, max_upload_bytes=10))) as client:
        response = client.post("/api/v1/corpora", content=b"x" * 1_048_587)
        assert response.status_code == 413
        assert response.json()["code"] == "upload_too_large"


def test_invalid_corpus_name_is_rejected_before_database_access() -> None:
    with TestClient(create_app(Settings(_env_file=None))) as client:
        assert client.post("/api/v1/corpora", json={"name": "   "}).status_code == 422


def test_chunked_body_limit_cannot_be_bypassed_without_content_length() -> None:
    def chunks() -> Iterator[bytes]:
        for _ in range(3):
            yield b"x" * 600_000

    with TestClient(create_app(Settings(_env_file=None, max_upload_bytes=10))) as client:
        response = client.post(
            "/api/v1/corpora", content=chunks(), headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 413
