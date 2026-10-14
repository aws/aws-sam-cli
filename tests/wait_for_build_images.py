"""
Script for waiting until the build images of the latest SAM CLI release are published to Public ECR.

Usage: python3.11 tests/wait_for_build_images.py [--sam-cli-version <x.y.z>]

The build image publishing pipeline starts when a SAM CLI release is published, at the same time as the release
integration tests. `sam build --use-container` pulls public.ecr.aws/sam/build-<runtime>:latest-<arch>, so without
waiting, the tests of a release run against the build images of the previous release.

Behavior:
  - Waits until, for every runtime and architecture whose image was published for the previous release,
    the <version>-<arch> tag exists and latest-<arch> points to the same image
  - Fails if the images are not published within --timeout-minutes
"""

import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from http import HTTPStatus
from typing import Dict, List, Optional, Tuple, cast

from setup_testing_resources import get_ecr_public_password  # type: ignore[import-not-found]  # noqa: E402

from samcli.lib.utils.architecture import SUPPORTED_RUNTIMES

REGISTRY = "public.ecr.aws"
REPOSITORY_PREFIX = "sam/build-"
GITHUB_RELEASES_URL = "https://api.github.com/repos/aws/aws-sam-cli/releases"
MANIFEST_MEDIA_TYPES = ", ".join(
    [
        "application/vnd.docker.distribution.manifest.v2+json",
        "application/vnd.docker.distribution.manifest.list.v2+json",
        "application/vnd.oci.image.manifest.v1+json",
        "application/vnd.oci.image.index.v1+json",
    ]
)
# Delay between registry requests, to stay under the Public ECR request rate
REQUEST_DELAY_SECONDS = 0.2


class PublicEcrRegistry:
    """Reads image digests from Public ECR, authenticated with the same password used for `docker login`."""

    def __init__(self, password: str, retries: int = 3):
        self._basic_auth = base64.b64encode(f"AWS:{password}".encode()).decode()
        self._retries = retries
        self._tokens: Dict[str, str] = {}

    def _token(self, repository: str, refresh: bool = False) -> str:
        if refresh or repository not in self._tokens:
            request = urllib.request.Request(
                f"https://{REGISTRY}/token/?service={REGISTRY}&scope=repository:{repository}:pull",
                headers={"Authorization": f"Basic {self._basic_auth}"},
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                self._tokens[repository] = cast(str, json.load(response)["token"])
        return self._tokens[repository]

    def _head_manifest(self, repository: str, tag: str, token: str) -> Optional[str]:
        request = urllib.request.Request(
            f"https://{REGISTRY}/v2/{repository}/manifests/{tag}",
            method="HEAD",
            headers={"Authorization": f"Bearer {token}", "Accept": MANIFEST_MEDIA_TYPES},
        )
        time.sleep(REQUEST_DELAY_SECONDS)
        with urllib.request.urlopen(request, timeout=30) as response:
            return cast(Optional[str], response.headers.get("Docker-Content-Digest"))

    def digest(self, repository: str, tag: str) -> Optional[str]:
        """Return the digest of repository:tag, or None if the tag does not exist."""
        for attempt in range(1, self._retries + 1):
            try:
                return self._head_manifest(repository, tag, self._token(repository, refresh=attempt > 1))
            except urllib.error.HTTPError as e:
                if e.code == HTTPStatus.NOT_FOUND:
                    return None
                retryable = e.code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.TOO_MANY_REQUESTS) or (
                    e.code >= HTTPStatus.INTERNAL_SERVER_ERROR
                )
                if attempt == self._retries or not retryable:
                    raise
                print(f"Request for {repository}:{tag} failed with HTTP {e.code}, retrying...")
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == self._retries:
                    raise
                print(f"Request for {repository}:{tag} failed: {e}, retrying...")
            time.sleep(2**attempt)
        return None


def parse_version(version: str) -> Tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def get_github_releases(path: str):
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GH_TOKEN']}"
    request = urllib.request.Request(f"{GITHUB_RELEASES_URL}{path}", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def get_latest_version() -> str:
    """Return the version of the latest SAM CLI release, which is the one the release tests install."""
    return cast(str, get_github_releases("/latest")["tag_name"].lstrip("v"))


def get_previous_version(version: str) -> str:
    """Return the most recent SAM CLI release before the given version."""
    previous_versions = [
        release["tag_name"][1:]
        for release in get_github_releases("?per_page=50")
        if not release["prerelease"]
        and not release["draft"]
        and re.fullmatch(r"v\d+\.\d+\.\d+", release["tag_name"])
        and parse_version(release["tag_name"][1:]) < parse_version(version)
    ]
    if not previous_versions:
        raise RuntimeError(f"Could not find a SAM CLI release before {version}")
    return cast(str, max(previous_versions, key=parse_version))


def get_expected_images(registry: PublicEcrRegistry, previous_version: str) -> List[Tuple[str, str]]:
    """
    Return the (repository, architecture) pairs to wait for. Images that were not published for the previous
    release are skipped, since the publishing pipeline does not build them (e.g. deprecated runtimes).
    """
    expected_images = []
    for runtime, architectures in sorted(SUPPORTED_RUNTIMES.items()):
        repository = f"{REPOSITORY_PREFIX}{runtime}"
        for architecture in architectures:
            if registry.digest(repository, f"{previous_version}-{architecture}"):
                expected_images.append((repository, architecture))
            else:
                print(
                    f"Skipping {repository}:{previous_version}-{architecture}, not published for the previous release"
                )
    return expected_images


def is_published(registry: PublicEcrRegistry, repository: str, architecture: str, version: str) -> bool:
    version_digest = registry.digest(repository, f"{version}-{architecture}")
    return version_digest is not None and registry.digest(repository, f"latest-{architecture}") == version_digest


def wait_for_images(
    registry: PublicEcrRegistry, version: str, previous_version: str, timeout_minutes: int, interval: int
):
    pending = get_expected_images(registry, previous_version)
    print(f"Waiting for {len(pending)} build images of SAM CLI {version}, previous release {previous_version}")
    deadline = time.monotonic() + timeout_minutes * 60

    while True:
        # Images are published in parallel, so stop at the first one that is not published yet
        # and check the rest on the next poll, instead of sending requests for every image each minute.
        while pending:
            repository, architecture = pending[0]
            try:
                if not is_published(registry, repository, architecture, version):
                    break
            except (urllib.error.URLError, TimeoutError) as e:
                print(f"Could not check {repository}:{version}-{architecture}: {e}")
                break
            print(f"Published: {REGISTRY}/{repository}:latest-{architecture} is {version}-{architecture}.")
            pending.pop(0)

        if not pending:
            print(f"All build images of SAM CLI {version} are published.")
            return

        if time.monotonic() >= deadline:
            print(
                f"FATAL: build images of SAM CLI {version} were not published within {timeout_minutes} minutes. "
                f"Still waiting for: {', '.join(f'{repository}:{version}-{arch}' for repository, arch in pending)}",
                file=sys.stderr,
            )
            sys.exit(1)

        repository, architecture = pending[0]
        print(f"{len(pending)} images left, waiting for {repository}:{version}-{architecture}...")
        time.sleep(interval)


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sam-cli-version", help="Defaults to the version of the latest SAM CLI release")
    parser.add_argument("--timeout-minutes", type=int, default=120)
    parser.add_argument("--interval-seconds", type=int, default=60)
    args = parser.parse_args()

    version = args.sam_cli_version or get_latest_version()
    previous_version = get_previous_version(version)
    registry = PublicEcrRegistry(get_ecr_public_password())
    wait_for_images(registry, version, previous_version, args.timeout_minutes, args.interval_seconds)


if __name__ == "__main__":
    main()
