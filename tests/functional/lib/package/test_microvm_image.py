"""Exercise MicrovmImage packaging with real archives/hashes and mocked S3 I/O."""

import copy
import io
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError

from samcli.commands._utils.template import get_template_artifacts_format, move_template
from samcli.commands.package.exceptions import ExportFailedError
from samcli.lib.package.artifact_exporter import Template
from samcli.lib.package.s3_uploader import S3Uploader
from samcli.lib.package.uploaders import Uploaders
from samcli.lib.utils.packagetype import ZIP
from samcli.yamlhelper import yaml_parse


@pytest.fixture
def package(tmp_path):
    objects = {}
    client = Mock()
    client.meta.endpoint_url = "https://s3.example.com"
    transfer = Mock()

    def head_object(Bucket, Key):
        if Key not in objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {}

    def upload(filename, bucket, key, extra_args):
        objects[key] = Path(filename).read_bytes()
        assert extra_args == {"ServerSideEncryption": "AES256"}
        return Mock()

    client.head_object.side_effect = head_object
    transfer.upload.side_effect = upload
    with patch("samcli.lib.package.s3_uploader.transfer.create_transfer_manager", return_value=transfer):
        uploader = S3Uploader(client, "test-bucket", prefix="artifacts", no_progressbar=True)
    signer = Mock()
    signer.should_sign_package.return_value = False

    def export(template, template_path=None):
        return Template(
            str(template_path or tmp_path / "template.yaml"),
            str(tmp_path),
            Uploaders(uploader, Mock()),
            signer,
            template_dict=copy.deepcopy(template),
        ).export()

    return export, objects, transfer


def template(code_uri):
    return {
        "Transform": "AWS::Serverless-2016-10-31",
        "Resources": {
            "Image": {
                "Type": "AWS::Serverless::MicrovmImage",
                "Properties": {"Name": "test-image", "CodeUri": code_uri, "BaseImageVersion": "0"},
            }
        },
    }


@pytest.mark.parametrize("absolute", [False, True])
def test_local_directory_uses_template_directory_and_content_hash(package, tmp_path, monkeypatch, absolute):
    export, objects, transfer = package
    source = tmp_path / "source"
    source.mkdir()
    (source / "Dockerfile").write_text("FROM scratch\nCOPY app.py /app.py\n", encoding="utf-8")
    app = source / "app.py"
    app.write_text("print('first')\n", encoding="utf-8")
    unrelated = tmp_path / "unrelated"
    unrelated.mkdir()
    monkeypatch.chdir(unrelated)
    original = template(str(source) if absolute else "source")

    first = export(original)["Resources"]["Image"]["Properties"]["CodeUri"]
    assert first.startswith("s3://test-bucket/artifacts/")
    key = first.removeprefix("s3://test-bucket/")
    with zipfile.ZipFile(io.BytesIO(objects[key])) as archive:
        assert set(archive.namelist()) == {"Dockerfile", "app.py"}
        assert archive.read("app.py") == b"print('first')\n"
    assert export(original)["Resources"]["Image"]["Properties"]["CodeUri"] == first
    assert transfer.upload.call_count == 1

    app.write_text("print('changed')\n", encoding="utf-8")
    changed = export(original)["Resources"]["Image"]["Properties"]["CodeUri"]
    assert changed != first
    assert transfer.upload.call_args.args[2] == changed.removeprefix("s3://test-bucket/")


def test_existing_local_zip_is_uploaded_without_rezipping(package, tmp_path):
    export, objects, _ = package
    artifact = tmp_path / "app.zip"
    with zipfile.ZipFile(artifact, "w") as archive:
        archive.writestr("Dockerfile", "FROM scratch\n")
    result = export(template("app.zip"))["Resources"]["Image"]["Properties"]["CodeUri"]
    assert objects[result.removeprefix("s3://test-bucket/")] == artifact.read_bytes()


@pytest.mark.parametrize(
    "code_uri", ["s3://existing/code.zip", {"Ref": "ArtifactUri"}, {"Fn::Sub": "s3://${Bucket}/code.zip"}]
)
def test_remote_and_intrinsic_references_are_unchanged(package, code_uri):
    export, objects, transfer = package
    assert export(template(code_uri))["Resources"]["Image"]["Properties"]["CodeUri"] == code_uri
    assert not objects
    transfer.upload.assert_not_called()


@pytest.mark.parametrize("code_uri", [None, ""])
def test_missing_required_code_uri_does_not_upload_template_directory(package, code_uri):
    export, objects, transfer = package
    document = template(code_uri)
    if code_uri is None:
        del document["Resources"]["Image"]["Properties"]["CodeUri"]
    assert export(document) == document
    assert not objects
    transfer.upload.assert_not_called()


def test_nonexistent_local_path_reports_resource_and_property(package):
    export, _, _ = package
    with pytest.raises(ExportFailedError, match="CodeUri.*Image"):
        export(template("does-not-exist"))


def test_build_template_relocation_preserves_local_code_uri(package, tmp_path):
    export, objects, _ = package
    source = tmp_path / "source"
    source.mkdir()
    (source / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    destination = tmp_path / ".aws-sam" / "build" / "template.yaml"
    destination.parent.mkdir(parents=True)
    # This is the relocation path used by sam build for resources without a
    # Lambda build artifact. The AWS service builds the MicroVM image itself.
    move_template(str(tmp_path / "template.yaml"), str(destination), template("source"))
    built = yaml_parse(destination.read_text(encoding="utf-8"))
    assert get_template_artifacts_format(str(destination)) == [ZIP]
    uri = built["Resources"]["Image"]["Properties"]["CodeUri"]
    assert (destination.parent / uri).resolve() == source
    packaged = export(built, destination)
    assert packaged["Resources"]["Image"]["Properties"]["CodeUri"].startswith("s3://test-bucket/")
    assert objects


def test_nested_stack_packages_microvm_source(package, tmp_path):
    export, objects, _ = package
    child_dir = tmp_path / "child"
    source = child_dir / "source"
    source.mkdir(parents=True)
    (source / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    from samcli.yamlhelper import yaml_dump

    (child_dir / "template.yaml").write_text(yaml_dump(template("source")), encoding="utf-8")
    parent = {
        "Resources": {
            "Child": {"Type": "AWS::CloudFormation::Stack", "Properties": {"TemplateURL": "child/template.yaml"}}
        }
    }
    packaged = export(parent)
    uploaded_child = packaged["Resources"]["Child"]["Properties"]["TemplateURL"]
    # Nested templates use an HTTPS S3 URL; inspect the uploaded template bytes.
    child_key = next(key for key, data in objects.items() if not zipfile.is_zipfile(io.BytesIO(data)))
    assert uploaded_child.endswith(child_key)
    child = yaml_parse(objects[child_key].decode("utf-8"))
    uri = child["Resources"]["Image"]["Properties"]["CodeUri"]
    assert uri.removeprefix("s3://test-bucket/") in objects
