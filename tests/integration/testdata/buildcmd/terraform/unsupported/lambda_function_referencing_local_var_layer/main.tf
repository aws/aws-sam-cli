provider "aws" {
}

resource "random_uuid" "role" {
    keepers = {
        my_key = "my_key"
    }
}

resource "aws_iam_role" "iam_for_lambda" {
    name = "dummy_iam_role_${random_uuid.role.result}"

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
    src_path = "./lambda_src"
    function_artifact_filename = "function1.zip"
    layer1_artifact_filename = "layer1.zip"
    layer2_artifact_filename = "layer2.zip"
    my_layer = aws_lambda_layer_version.layer1.arn
}

resource "random_uuid" "s3_bucket" {
    keepers = {
        my_key = "my_key"
    }
}

resource "aws_s3_bucket" "lambda_code_bucket" {
    bucket = "lambda-code-bucket-${random_uuid.s3_bucket.result}"
}

resource "aws_s3_object" "lambda_function_code" {
    bucket = aws_s3_bucket.lambda_code_bucket.bucket
    key = "function"
    source = "${local.src_path}/${local.function_artifact_filename}"
}

resource "aws_lambda_function" "function1" {
    s3_bucket = aws_s3_bucket.lambda_code_bucket.bucket
    s3_key = aws_s3_object.lambda_function_code.key
    handler = "app.lambda_handler"
    runtime = "python3.8"
    function_name = "${var.namespace}-function1-${random_uuid.s3_bucket.result}"
    role = aws_iam_role.iam_for_lambda.arn
    timeout = 300
    layers = [
        local.my_layer
    ]
}

## /* layer1

resource "aws_lambda_layer_version" "layer1" {
    filename = "${local.src_path}/${local.layer1_artifact_filename}"
    layer_name = "${var.namespace}_lambda_layer1"
    compatible_runtimes = ["python3.8", "python3.9"]
}
## */