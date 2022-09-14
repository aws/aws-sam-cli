provider "aws" {
  region = "eu-west-1"
}

resource "aws_iam_role" "iam_for_lambda" {
  name = "iam_for_lambda"

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

resource "aws_s3_bucket" "lambda_code_bucket" {
  bucket = "lambda_code_bucket"
}

resource "aws_s3_object" "s3_lambda_code" {
    bucket = "lambda_code_bucket"
    key    = "s3_lambda_code_key"
    source = "HelloWorldFunction.zip"
}

resource "aws_lambda_function" "s3_lambda" {
        s3_bucket = "lambda_code_bucket"
        s3_key = "s3_lambda_code_key"
        handler = "app.lambda_handler"
        runtime = "python3.8"
        function_name = "s3_lambda_function"
        timeout = 500
        role = aws_iam_role.iam_for_lambda.arn
}

resource "aws_lambda_function" "remote_lambda_code" {
        s3_bucket = "lambda_code_bucket"
        s3_key = "remote_lambda_code_key"
        handler = "app.lambda_handler"
        runtime = "python3.8"
        function_name = "s3_remote_lambda_function"
        role = aws_iam_role.iam_for_lambda.arn
}

resource "aws_lambda_function" "root_lambda" {
        filename = "HelloWorldFunction.zip"
        handler = "app.lambda_handler"
        runtime = "python3.8"
        function_name = "root_lambda"
        role = aws_iam_role.iam_for_lambda.arn
}

resource "null_resource" "sam_metadata_aws_lambda_function_s3_lambda" {
  triggers = {
    # This is a way to let SAM CLI correlates between the Lambda layer resource, and this metadata
    # resource
    resource_name = "aws_lambda_function.s3_lambda"
    resource_type = "ZIP_LAMBDA_FUNCTION"

    # The Lambda layer source code.
    original_source_code = "./src/test.py"
    
    # a property to let SAM CLI knows where to find the Lambda layer source code if the provided
    # value for original_source_code attribute is map.
    source_code_property = "path"

    # A property to let SAM CLI knows where to find the Lambda layer built output
    built_output_path = "build/layer.zip"
  }
}

resource "aws_lambda_layer_version" "lambda_layer" {
    s3_bucket = "layer_code_bucket"
    s3_key = "s3_lambda_layer_code_key"
    s3_object_version = "1"
    layer_name = "lambda_layer_name"

    compatible_runtimes = ["nodejs14.x", "nodejs16.x"]
    compatible_architectures = ["arm64"]
}

resource "aws_s3_object" "s3_layer_code" {
    bucket = "layer_code_bucket"
    key    = "s3_lambda_layer_code_key"
    source = "HelloWorldFunctionLayer.zip"
}

resource "null_resource" "sam_metadata_aws_lambda_layer_version_lambda_layer" {
  triggers = {
    # This is a way to let SAM CLI correlates between the Lambda layer resource, and this metadata
    # resource
    resource_name = "aws_lambda_layer_version.lambda_layer"
    resource_type = "LAMBDA_LAYER"

    # The Lambda layer source code.
    original_source_code = "./src/layer.py"

    # a property to let SAM CLI knows where to find the Lambda layer source code if the provided
    # value for original_source_code attribute is map.
    source_code_property = "path"

    # A property to let SAM CLI knows where to find the Lambda layer built output
    built_output_path = "build/layer.zip"
  }
}

module "level1_lambda" {
   source = "./lambda"
   source_code_path = "HelloWorldFunction.zip"
   handler = "app.lambda_handler"
   function_name = "level1_lambda_function"
}