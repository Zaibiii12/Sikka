import pytest

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@pytest.mark.parametrize(
    "method",
    [
        "post",
        "put",
        "patch",
        "delete",
    ],
)
def test_public_demo_blocks_api_writes(
    monkeypatch,
    method,
):
    monkeypatch.setenv(
        "BLOCKSIKKA_PUBLIC_READ_ONLY",
        "true",
    )

    response = getattr(
        client,
        method,
    )(
        "/api/v1/"
        "__portfolio_write_probe__"
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail":
            "This deployment is read-only."
    }


def test_public_demo_does_not_block_get(
    monkeypatch,
):
    monkeypatch.setenv(
        "BLOCKSIKKA_PUBLIC_READ_ONLY",
        "true",
    )

    response = client.get(
        "/api/v1/"
        "__portfolio_read_probe__"
    )

    # The route does not exist, so GET should
    # reach normal FastAPI routing rather than
    # being blocked by read-only middleware.
    assert response.status_code == 404
