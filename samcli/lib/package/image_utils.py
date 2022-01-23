"""
Image artifacts based utilities
"""
import docker
from docker.errors import APIError, NullResource

from samcli.commands.package.exceptions import DockerGetLocalImageFailedError
from samcli.lib.package.utils import is_ecr_url

SHA_CHECKSUM_TRUNCATION_LENGTH = 12


class NonLocalImageException(Exception):
    pass


class NoImageFoundException(Exception):
    pass


def tag_translation(image, docker_image_id=None, gen_tag="latest"):
    """
    Translates a given local image structure such as `helloworld:v1` into
    just a tag structure such as `helloworld-v1` , this tag will then be applied
    to an image that is to be uploaded to a remote registry.

    :param docker_image_id: an Id associated with a docker image.
    :param image: an image referenceable by docker locally.
    :param gen_tag: tag to be generated if the image did not have a tag assigned to it.
    :return: fully qualified tag.
    """
    # NOTE(sriram-mv): assumption on tag structure, needs vetting.
    if is_ecr_url(image):
        raise NonLocalImageException(f"{image} is a non-local image")

    if not docker_image_id:
        try:
            docker_client = docker.from_env()
            docker_image_id = docker_client.images.get(image).id
        except APIError as ex:
            raise DockerGetLocalImageFailedError(str(ex)) from ex
        except NullResource as ex:
            raise NoImageFoundException(str(ex)) from ex

    # NOTE(sriram-mv): Checksum truncation Length is set to 12
    _id = docker_image_id.split(":")[1][:SHA_CHECKSUM_TRUNCATION_LENGTH]
    if ":" in image:
        name, tag = image.split(":")
    else:
        name = image
        tag = None
    _tag = tag if tag else gen_tag
    return f"{name}-{_id}-{_tag}"
