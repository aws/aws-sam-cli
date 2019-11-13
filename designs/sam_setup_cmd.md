# `sam setup` command

As a part of packaging Lambda functions for deployment to AWS, users of the AWS SAM CLI currently need to provide an S3 bucket to store their code artifacts in. This creates a number of extra setup steps today, from users needing to go and set up an S3 bucket, to needing to track which bucket is appropriate for a given region (S3 bucket region must match CloudFormation deployment region). This project aims to simplify this experience.

## Goals

1. AWS SAM CLI users should be able to set up an S3 bucket for their SAM project entirely through the AWS SAM CLI.
2. The AWS SAM CLI, in setting up such a bucket, should choose an appropriate region and populate the users’s SAM CLI config file in their project.
3. A user doing the interactive deploy experience should be able to be completely separated from the S3 bucket used for source code storage, if the user does not wish to directly configure their source bucket.

## Design

We propose creating a new SAM CLI command, sam setup for this process. The underlying functionality would also be accessible to other commands, such as package itself.

The `sam setup` command would have the following parameters:

* `--region` This parameter is **CONDITIONALLY REQUIRED**, because the primary goal of this command is to ensure that the user’s region has an S3 bucket set up. We will also accept the `AWS_REGION` environment variable, or the default region in a user’s profile. In short, a region must be provided in some way, or we will fail.
* `--profile` This is associated with a user’s AWS profile, and defaults to `"default"` if not provided. It will be used for sourcing credentials for CloudFormation commands used when setting up the bucket, and for doing S3 ListBucket calls to see if a suitable bucket already exists.

## Challenges

Both S3 buckets and CloudFormation stacks do not have sufficiently efficient ways to search by tags. Simply put, there’s likely to be some computational inefficiency as up to hundreds of API calls might be required to identify an existing bucket that was created to be a source bucket. This means that to avoid severe performance issues, we need to make compromises. Proposed:

* The default managed bucket uses a fixed stack name per region, such as “aws-sam-cli-managed-source-bucket”. If the user for some reason has a stack with that name, then we cannot support a managed bucket for them.
* Alternatively, when doing sam setup, the user providing a bucket name would mean that we just check for it to exist and if it does and is in the correct region, populate the config file.
