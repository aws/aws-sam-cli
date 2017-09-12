# Full Example for a Python Lambda with external Dependencies

## Development 

### Prerequisites

- Install [Docker](https://github.com/awslabs/aws-sam-local#prerequisites)
- Install [AWS SAM local](https://github.com/awslabs/aws-sam-local) from 
  [here](https://github.com/awslabs/aws-sam-local/releases)

### Run 

As we defined `EnvDownHandler` in [`template.yml`](template.yml), our 
`invoke` call looks like this

```bash
$ echo '{ "resources": ["arn:aws:events:eu-west-1:482174156240:rule/10MinuteTickRule"] }' | sam local invoke EnvDownHandler
2017/09/06 11:06:39 Successfully parsed template.yml
2017/09/06 11:06:39 Connected to Docker 1.30
2017/09/06 11:06:39 Fetching lambci/lambda:python3.6 image for python3.6 runtime...
python3.6: Pulling from lambci/lambda
Digest: sha256:b0245d6aaae7648b4c488ffa3113e20d67b77ecc15392589162f67e7fa8e1bb7
Status: Image is up to date for lambci/lambda:python3.6
2017/09/06 11:06:41 Reading invoke payload from stdin (you can also pass it from file with --event)
2017/09/06 11:06:41 Invoking schedule.lambda_sandbox_down_handler (python3.6)
START RequestId: 09c35258-f743-4906-bbc5-35f12a542fb9 Version: $LATEST
hello from handler
END RequestId: 09c35258-f743-4906-bbc5-35f12a542fb9
REPORT RequestId: 09c35258-f743-4906-bbc5-35f12a542fb9 Duration: 31 ms Billed Duration: 0 ms Memory Size: 0 MB Max Memory Used: 19 MB

"foo"
```

We can see what kind of payload we'll receive via
 
```bash
$ sam local generate-event schedule
{
  "account": "123456789012",
  "region": "us-east-1",
  "detail": {},
  "detail-type": "Scheduled Event",
  "source": "aws.events",
  "time": "1970-01-01T00:00:00Z",
  "id": "cdc73f9d-aea9-11e3-9d5a-835b769c0d9c",
  "resources": [
    "arn:aws:events:us-east-1:123456789012:rule/my-schedule"
  ]
}
```

### Build

To be able to package third-party dependencies as we know it via virtualenv, we need to interact 
with docker directly [5]. 

To just build the current status, run 

```bash
make bundle
```

If you want to inspect the image, perform an interactive shell

```bash
docker run -v $PWD:/var/task -it lambci/lambda:build-python3.6 /bin/bash
```

### Deploy 

#### TL;DR

For a complete release action, just call 

```bash
make release
```


#### More Detailed

For deployment we follow [the SAM documentation](https://github.com/awslabs/aws-sam-local#package-and-deploy-to-lambda)

To include our AWS credentials and to make things easy, there are two `make` targets

```bash
make package
make deploy
```

- `make package` takes the `template.yml`, uploads our `build.zip` and creates a new template (`packaged.yml`) 
  with the matching S3 reference in `CodeUri`.

- `make deploy` will wire the uploaded zip file on S3 to a fully functional lambda. Ours can be listed 
  [here](https://eu-west-1.console.aws.amazon.com/lambda/home?region=eu-west-1#/functions)
  

### Using the virtualenv in a different Architecture

There is no reason not to call 

```bash
make clean build
``` 
locally. Just ensure that you always use `clean` to avoid confusion inside of the virtualenv.


## Background

1.  A general blueprint how to start with cloudwatch events and lambda handlers exists [from Amazon](https://aws.amazon.com/premiumsupport/knowledge-center/start-stop-lambda-cloudwatch/). This does
not include SAM Local or external sources; still it provides a good overview.
 
1.  A python package with dependencies requires us to [build a `virtualenv` on 
a `amd64` kernel](
http://docs.aws.amazon.com/lambda/latest/dg/with-s3-example-deployment-pkg.html#with-s3-example-deployment-pkg-python).

1.  Howto integrate third party libs into lambda via SAM Local [seems unclear](https://github.com/awslabs/aws-sam-local/issues/53)

1.  About [Packaging Lambda Functions](https://github.com/awslabs/serverless-application-model/blob/master/HOWTO.md#packing-artifacts) 

1.  [Replications](https://github.com/lambci/docker-lambda) of the live AWS Lambda environment

1.  [About packaging `virtualenv` projects for AWS Lambda](http://www.perrygeo.com/running-python-with-compiled-code-on-aws-lambda.html)

1.  Create a Deployment Package [on AWS](http://docs.aws.amazon.com/lambda/latest/dg/with-s3-example-deployment-pkg.html#with-s3-example-deployment-pkg-python) 
1.  Create a Deployment Package [for Lambda](http://docs.aws.amazon.com/lambda/latest/dg/lambda-python-how-to-create-deployment-package.html#deployment-pkg-for-virtualenv) 

1.  [About Lambda Roles](http://docs.aws.amazon.com/lambda/latest/dg/with-s3-example-create-iam-role.html)

1.  [Example Policies for EC2 handling](http://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ExamplePolicies_EC2.html)