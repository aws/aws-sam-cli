# A base image no arm64 test uses: the classic builder can reuse a locally cached base image
# that was pulled for another platform, so sharing a tag with the arm64 tests could make this
# build use an arm64 base.
FROM public.ecr.aws/docker/library/alpine:3.20

# Executes an x86_64 binary during the build, so on an arm64 host it needs emulation.
RUN uname -m > /built_arch.txt
