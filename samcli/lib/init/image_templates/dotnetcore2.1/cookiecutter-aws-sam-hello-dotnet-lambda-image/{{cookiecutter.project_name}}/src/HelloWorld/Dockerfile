FROM mcr.microsoft.com/dotnet/core/sdk:2.1 as build-image
ARG SAM_BUILD_MODE="run"
ARG FUNCTION_DIR="/build"
ENV PATH="/root/.dotnet/tools:${PATH}"

RUN apt-get update && apt-get -y install zip

RUN mkdir $FUNCTION_DIR
WORKDIR $FUNCTION_DIR
COPY Function.cs HelloWorld.csproj aws-lambda-tools-defaults.json $FUNCTION_DIR/
RUN dotnet tool install -g Amazon.Lambda.Tools

# Build and Copy artifacts depending on build mode.
RUN mkdir -p build_artifacts
RUN if [ "$SAM_BUILD_MODE" = "debug" ]; then dotnet lambda package --configuration Debug; else dotnet lambda package --configuration Release; fi
RUN if [ "$SAM_BUILD_MODE" = "debug" ]; then cp -r /build/bin/Debug/netcoreapp2.1/publish/* /build/build_artifacts; else cp -r /build/bin/Release/netcoreapp2.1/publish/* /build/build_artifacts; fi

FROM public.ecr.aws/lambda/dotnet:core2.1

COPY --from=build-image /build/build_artifacts/ /var/task/

# Command can be overwritten by providing a different command in the template directly.
CMD ["HelloWorld::HelloWorld.Function::FunctionHandler"]
