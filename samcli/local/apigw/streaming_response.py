"""
Helpers for forwarding Lambda response streaming to the local API Gateway
client.

When a Lambda function uses response streaming (e.g. via the Node.js
``awslambda.streamifyResponse``) the runtime POSTs its response body to the
Runtime API with the ``Lambda-Runtime-Function-Response-Mode: streaming``
header. The streaming-enabled fork of the Runtime Interface Emulator
forwards this header to the invoke caller (SAM CLI) and emits the body
chunks straight through. This module turns that wire format into a
:class:`flask.Response` that streams chunks to the browser as they arrive,
parsing the optional Lambda HTTP-integration prelude (used by Function
URLs and API Gateway HTTP API) when present.
"""

from __future__ import annotations

import json
import logging
from typing import Callable, Dict, Iterable, Iterator, Optional, Tuple

from flask import Response

LOG = logging.getLogger(__name__)

# HTTP header set by the runtime / RIE on streaming responses.
RESPONSE_MODE_HEADER = "Lambda-Runtime-Function-Response-Mode"
RESPONSE_MODE_STREAMING = "streaming"

# Content type used by Lambda Function URLs / API Gateway HTTP API for
# streamed responses. The body starts with a JSON prelude describing the
# desired HTTP response status, headers and cookies, followed by 8 NUL
# bytes, followed by the raw body bytes.
HTTP_INTEGRATION_CONTENT_TYPE = "application/vnd.awslambda.http-integration-response"
_PRELUDE_DELIMITER = b"\x00" * 8
# Cap the size of the JSON prelude we are willing to scan for. AWS's
# documented limit is much smaller than this, but we keep some headroom
# for unusual header sets.
_PRELUDE_MAX_BYTES = 64 * 1024

# How many bytes we ask urllib3 for on each read. Smaller values give
# slightly lower latency for tiny SSE frames at the cost of more syscalls;
# 4 KiB is a reasonable compromise that still lets a single TCP segment
# carrying multiple SSE events be delivered in one yield.
_STREAM_READ_SIZE = 4096


def is_streaming_response(resp) -> bool:
    """Return ``True`` if ``resp`` (a ``requests.Response``) carries the
    streaming response-mode header."""
    return resp.headers.get(RESPONSE_MODE_HEADER, "").lower() == RESPONSE_MODE_STREAMING


def _read_streaming_chunks(resp) -> Iterator[bytes]:
    """Yield raw bytes from a streaming response with minimal buffering.

    We bypass ``iter_content`` and pull from ``raw.read1`` (when
    available) because we want each TCP segment to surface as soon as the
    network delivers it; ``iter_content`` would otherwise wait until
    ``chunk_size`` bytes have accumulated.
    """
    raw = getattr(resp, "raw", None)
    read1 = getattr(raw, "read1", None) if raw is not None else None

    if callable(read1):
        while True:
            try:
                chunk = read1(_STREAM_READ_SIZE)
            except Exception:  # pragma: no cover - network noise
                LOG.debug("Streaming read failed", exc_info=True)
                break
            if not chunk:
                break
            yield chunk
    else:
        for chunk in resp.iter_content(chunk_size=_STREAM_READ_SIZE):
            if chunk:
                yield chunk


def _peek_prelude(byte_iter: Iterator[bytes]) -> Tuple[Optional[bytes], Iterator[bytes]]:
    """
    Pull bytes from ``byte_iter`` until we see the 8-NUL prelude
    delimiter or hit ``_PRELUDE_MAX_BYTES`` without finding it.

    Returns a tuple ``(prelude, rest_iter)`` where:

    * ``prelude`` is the JSON-encoded prelude bytes (excluding the
      delimiter), or ``None`` if no delimiter was found within the cap
      (in which case the bytes already consumed are re-emitted at the
      start of ``rest_iter``).
    * ``rest_iter`` is an iterator that yields any leftover bytes
      followed by the rest of the original iterator.
    """
    buffered = bytearray()
    for chunk in byte_iter:
        buffered.extend(chunk)
        idx = bytes(buffered).find(_PRELUDE_DELIMITER)
        if idx != -1:
            prelude = bytes(buffered[:idx])
            tail = bytes(buffered[idx + len(_PRELUDE_DELIMITER):])

            def _rest_with_tail():
                if tail:
                    yield tail
                yield from byte_iter

            return prelude, _rest_with_tail()
        if len(buffered) >= _PRELUDE_MAX_BYTES:
            break

    leftover = bytes(buffered)

    def _rest_with_leftover():
        if leftover:
            yield leftover
        yield from byte_iter

    return None, _rest_with_leftover()


def _parse_prelude(prelude_bytes: bytes) -> Tuple[int, Dict[str, str], list]:
    """Parse the JSON prelude. Falls back to defaults for missing fields."""
    try:
        decoded = json.loads(prelude_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        LOG.warning("Failed to parse Lambda HTTP-integration prelude: %s", exc)
        return 200, {}, []

    if not isinstance(decoded, dict):
        return 200, {}, []

    status_code = int(decoded.get("statusCode", 200))
    headers = decoded.get("headers") or {}
    if not isinstance(headers, dict):
        headers = {}
    cookies = decoded.get("cookies") or []
    if not isinstance(cookies, list):
        cookies = []
    # Normalize header values to strings (Lambda allows numbers too).
    headers = {str(k): str(v) for k, v in headers.items()}
    return status_code, headers, cookies


def build_streaming_flask_response(
    resp,
    on_complete: Callable[[], None],
    extra_headers: Optional[Dict[str, str]] = None,
) -> Response:
    """
    Build a Flask :class:`~flask.Response` that forwards a streaming
    Lambda response body to the HTTP client as it arrives.

    Parameters
    ----------
    resp : requests.Response
        The streaming response returned by the local RIE invoke. Must
        have been opened with ``stream=True``.
    on_complete : Callable
        Called exactly once after the response generator is fully
        consumed (or aborted). Used to release container resources.
    extra_headers : Optional[Dict[str, str]]
        Additional headers (e.g. CORS) to add to the outgoing response.

    Returns
    -------
    flask.Response
        A response whose body is a generator producing the Lambda
        function's streamed bytes.
    """
    extra_headers = extra_headers or {}
    upstream_content_type = resp.headers.get("Content-Type", "")
    is_http_integration = HTTP_INTEGRATION_CONTENT_TYPE in upstream_content_type

    chunk_iter = _read_streaming_chunks(resp)

    status_code = 200
    response_headers: Dict[str, str] = {}
    cookies: list = []
    body_iter: Iterable[bytes] = chunk_iter

    if is_http_integration:
        prelude, rest_iter = _peek_prelude(chunk_iter)
        if prelude is not None:
            status_code, response_headers, cookies = _parse_prelude(prelude)
        else:
            LOG.warning(
                "Streaming response declared http-integration content type but did not "
                "contain the 8-NUL prelude delimiter within %d bytes; passing body through verbatim",
                _PRELUDE_MAX_BYTES,
            )
        body_iter = rest_iter
    else:
        # Non-integration streaming: pass content-type and other useful
        # headers through unchanged.
        if upstream_content_type:
            response_headers["Content-Type"] = upstream_content_type

    # Make sure intermediaries do not buffer the response. Without this
    # some reverse proxies hold the bytes back until the connection
    # closes.
    response_headers.setdefault("Cache-Control", "no-cache")
    response_headers.setdefault("X-Accel-Buffering", "no")
    response_headers.update(extra_headers)

    completion_called = {"done": False}

    def _safe_complete() -> None:
        if completion_called["done"]:
            return
        completion_called["done"] = True
        try:
            on_complete()
        except Exception:  # pragma: no cover - best effort
            LOG.debug("on_complete callback raised", exc_info=True)

    def _wrapped_body() -> Iterator[bytes]:
        try:
            for chunk in body_iter:
                if chunk:
                    yield chunk
        finally:
            _safe_complete()

    flask_response = Response(_wrapped_body(), status=status_code)
    for key, value in response_headers.items():
        flask_response.headers[key] = value
    for cookie in cookies:
        if isinstance(cookie, str):
            flask_response.headers.add("Set-Cookie", cookie)

    # Hook werkzeug's "response close" lifecycle in case the consumer
    # disconnects before the body generator finishes naturally.
    flask_response.call_on_close(_safe_complete)
    return flask_response
