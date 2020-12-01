FROM public.ecr.aws/lambda/nodejs:10

COPY app.js package.json ./

RUN npm install

# Command can be overwritten by providing a different command in the template directly.
CMD ["app.lambdaHandler"]