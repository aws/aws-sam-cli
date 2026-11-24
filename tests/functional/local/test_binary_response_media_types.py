"""Binary media subtype ranges through the local REST API response path."""

import base64
import json
from http import HTTPStatus
from typing import Optional
from unittest.mock import Mock

import pytest

from samcli.lib.providers.provider import Api
from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.apigw.local_apigw_service import LocalApigwService
from samcli.local.apigw.route import Route


@pytest.mark.parametrize(
    "content_type,binary_media_type,payload",
    [
        ("image/png", "image/*", b"\x89PNG\r\n\x1a\n"),
        ("image/jpeg", "image/*", b"\xff\xd8\xff\xe0"),
        ("application/pdf", "application/*", b"%PDF-\xff"),
        ("image/png", "image/png", b"\x89PNG\r\n\x1a\n"),
        ("image/png", "*/*", b"\x89PNG\r\n\x1a\n"),
    ],
)
def test_binary_response_media_type_wildcard(content_type: str, binary_media_type: str, payload: bytes) -> None:
    def invoke(
        name: str,
        event_str: str,
        stdout: Optional[StreamWriter] = None,
        stderr: Optional[StreamWriter] = None,
        tenant_id: Optional[str] = None,
    ) -> None:
        assert stdout is not None
        stdout.write_str(
            json.dumps(
                {
                    "statusCode": 200,
                    "headers": {"Content-Type": content_type},
                    "body": base64.b64encode(payload).decode("ascii"),
                    "isBase64Encoded": True,
                }
            )
        )

    runner = Mock()
    runner.is_debugging.return_value = False
    runner.invoke.side_effect = invoke
    api = Api(routes=[Route(function_name="Function", path="/image", methods=["GET"])])
    api.binary_media_types_set.add(binary_media_type)
    service = LocalApigwService(api=api, lambda_runner=runner)
    service.create()
    response = service._app.test_client().get("/image", headers={"Accept": content_type})
    assert response.status_code == HTTPStatus.OK
    runner.invoke.assert_called_once()
    assert response.data == payload
