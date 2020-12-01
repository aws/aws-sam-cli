FROM openjdk:8 as build-image

ARG SCRATCH_DIR=/var/task/build
WORKDIR /var/task

COPY src/ src/
COPY gradle/ gradle/
COPY build.gradle gradlew ./

RUN mkdir build
COPY gradle/lambda-build-init.gradle ./build

RUN echo $SCRATCH_DIR

RUN ./gradlew --project-cache-dir $SCRATCH_DIR/gradle-cache -Dsoftware.amazon.aws.lambdabuilders.scratch-dir=$SCRATCH_DIR --init-script $SCRATCH_DIR/lambda-build-init.gradle build
RUN rm -r $SCRATCH_DIR/gradle-cache
RUN rm -r $SCRATCH_DIR/lambda-build-init.gradle
RUN cp -r $SCRATCH_DIR/*/build/distributions/lambda-build/* .

FROM public.ecr.aws/lambda/java:8.al2

COPY --from=build-image /var/task/META-INF ./
COPY --from=build-image /var/task/helloworld ./helloworld
COPY --from=build-image /var/task/lib/ ./lib
# Command can be overwritten by providing a different command in the template directly.
CMD ["helloworld.App::handleRequest"]
