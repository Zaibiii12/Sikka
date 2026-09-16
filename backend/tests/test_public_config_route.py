from app.main import app


def test_public_config_route_registered() -> None:
    paths = set(
        app.openapi()["paths"]
    )

    assert (
        "/api/v1/config/public"
        in paths
    )
