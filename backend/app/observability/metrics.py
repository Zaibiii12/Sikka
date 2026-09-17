from __future__ import annotations

from time import perf_counter

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)


HTTP_REQUESTS = Counter(
    "blocksikka_http_requests_total",
    "Total HTTP requests handled by BlockSikka FastAPI.",
    [
        "method",
        "path",
        "status",
    ],
)


HTTP_REQUEST_DURATION = Histogram(
    "blocksikka_http_request_duration_seconds",
    "BlockSikka FastAPI request duration in seconds.",
    [
        "method",
        "path",
    ],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
    ),
)


HTTP_REQUESTS_IN_PROGRESS = Gauge(
    "blocksikka_http_requests_in_progress",
    "Current BlockSikka FastAPI requests in progress.",
    [
        "method",
    ],
)


def _route_path(
    request: Request,
) -> str:
    route = request.scope.get(
        "route",
    )

    path = getattr(
        route,
        "path",
        None,
    )

    if isinstance(
        path,
        str,
    ):
        return path

    return request.url.path


def install_metrics(
    app: FastAPI,
) -> None:

    @app.middleware(
        "http",
    )
    async def prometheus_middleware(
        request: Request,
        call_next,
    ):
        if (
            request.url.path
            == "/metrics"
        ):
            return await call_next(
                request,
            )

        method = request.method

        HTTP_REQUESTS_IN_PROGRESS.labels(
            method=method,
        ).inc()

        started = perf_counter()

        status_code = 500

        try:
            response = await call_next(
                request,
            )

            status_code = (
                response.status_code
            )

            return response

        finally:
            path = _route_path(
                request,
            )

            elapsed = (
                perf_counter()
                - started
            )

            HTTP_REQUESTS.labels(
                method=method,
                path=path,
                status=str(
                    status_code,
                ),
            ).inc()

            HTTP_REQUEST_DURATION.labels(
                method=method,
                path=path,
            ).observe(
                elapsed,
            )

            HTTP_REQUESTS_IN_PROGRESS.labels(
                method=method,
            ).dec()


    @app.get(
        "/metrics",
        include_in_schema=False,
    )
    async def prometheus_metrics():
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )
