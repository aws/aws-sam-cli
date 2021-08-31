FROM public.ecr.aws/lambda/nodejs:12
# Alternatively, you can pull the base image from Docker Hub: amazon/aws-lambda-nodejs:12

# Copy the Lambda functions
COPY app.js package.json ${LAMBDA_TASK_ROOT}/

# Install NPM dependencies for function
RUN npm install