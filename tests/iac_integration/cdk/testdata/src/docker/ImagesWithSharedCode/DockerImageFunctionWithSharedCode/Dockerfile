FROM public.ecr.aws/lambda/nodejs:14

# Add the lambda handler for this feature
COPY DockerImageFunctionWithSharedCode/app.js  ./

# Add the shared code
COPY SharedCode/ ./SharedCode

# Add the shared dependencies
COPY package.json ./

# Install the dependencies
RUN npm install

# Set the CMD to your handler (could also be done as a parameter override outside of the Dockerfile)
CMD [ "app.lambdaHandler" ]