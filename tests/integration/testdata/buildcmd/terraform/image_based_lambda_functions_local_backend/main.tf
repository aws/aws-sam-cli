provider "aws" {
    # Make it faster by skipping something
    skip_get_ec2_platforms      = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_credentials_validation = true
    skip_requesting_account_id  = true
}

resource "aws_iam_role" "iam_for_lambda" {
    name = "dummy_iam_role"

    assume_role_policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Action": "sts:AssumeRole",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Effect": "Allow",
            "Sid": ""
        }
    ]
}
EOF
}

locals {
    lambda_src_path = "./hello_world"
}

resource "random_pet" "this" {
  length = 2
}

resource "aws_lambda_function" "function_with_non_image_uri" {
    function_name = "function_with_non_image_uri"
    role = aws_iam_role.iam_for_lambda.arn
    package_type = "Image"
    image_uri = "some_image_uri_${random_pet.this.id}"
    timeout = 300
}

resource "null_resource" "sam_metadata_aws_lambda_function_function_with_non_image_uri" {
    triggers = {
        resource_name = "aws_lambda_function.function_with_non_image_uri"
        resource_type = "IMAGE_LAMBDA_FUNCTION"

        docker_context = local.lambda_src_path
        docker_file = "Dockerfile"
        docker_tag = "latest"
    }
}

resource "aws_lambda_function" "my_image_function" {
    function_name = "my_image_function"
    role = aws_iam_role.iam_for_lambda.arn
    package_type = "Image"
    handler = null
    timeout = 300
    image_uri = "some_image_uri"
}

resource "null_resource" "sam_metadata_aws_lambda_function_my_image_function" {
    triggers = {
        resource_name = "aws_lambda_function.my_image_function"
        resource_type = "IMAGE_LAMBDA_FUNCTION"

        docker_context = local.lambda_src_path
        # docker_context_property_path = ""
        docker_file = "Dockerfile"
        docker_build_args = ""
        docker_tag = "latest"
    }
}

module "l1_lambda" {
    source = "./l1_lambda"
    function_name = "my_l1_lambda"
    image_uri = "my_l1_lambda_image_uri"
    l2_function_name = "my_l2_lambda"
    l2_image_uri = "my_l2_lambda_image_uri"
}

resource "null_resource" "sam_metadata_aws_lambda_function_l1_function" {
    triggers = {
        resource_name = "module.l1_lambda.aws_lambda_function.this"
        resource_type = "IMAGE_LAMBDA_FUNCTION"

        docker_context = local.lambda_src_path
        docker_context_property_path = ""
        docker_file = "Dockerfile"
        docker_build_args = ""
        docker_tag = "latest"
    }
}

resource "null_resource" "sam_metadata_aws_lambda_function_l2_function" {
    triggers = {
        resource_name = "module.l1_lambda.module.l2_lambda.aws_lambda_function.this"
        resource_type = "IMAGE_LAMBDA_FUNCTION"

        docker_context = local.lambda_src_path
        docker_context_property_path = ""
        docker_file = "Dockerfile"
        docker_build_args = ""
        docker_tag = "latest"
    }
}

## Serverless TF
module "docker_image" {
  source  = "terraform-aws-modules/lambda/aws//modules/docker-build"
  version = "4.10.1"
  create_ecr_repo = false
  ecr_repo        = "existing_test_repo"
  image_tag       = "latest"
  source_path     = local.lambda_src_path
}

module "serverless_tf_image_function" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "4.10.1"
  timeout = 300
  function_name = "serverless_tf_image_function"
  create_package = false
  image_uri     = module.docker_image.image_uri
  package_type  = "Image"
}