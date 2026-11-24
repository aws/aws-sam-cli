"""Media ranges retain the existing encoding flag and missing-match behavior."""

from typing import Optional
from unittest.mock import Mock

import pytest
from werkzeug.datastructures import Headers

from samcli.local.apigw.local_apigw_service import LocalApigwService


@pytest.mark.parametrize(
    "binary_types,mimetype,encoded,expected",
    [
        (["image/*"], "image/png", True, True),
        (["application/*"], "application/pdf", True, True),
        (["image/*"], "application/pdf", True, False),
        (["image/*"], "image/png", False, False),
        ([], "image/png", True, False),
        (["*/*"], None, True, None),
    ],
)
def test_binary_response_media_pattern(
    binary_types: list[str], mimetype: Optional[str], encoded: bool, expected: Optional[bool]
) -> None:
    request = Mock()
    request.accept_mimetypes.best_match.return_value = mimetype
    headers = Headers({"Content-Type": mimetype or "application/octet-stream"})
    assert LocalApigwService._should_base64_decode_body(binary_types, request, headers, encoded) is expected
