provider "aws" {
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

resource "null_resource" "sam_metadata_aws_lambda_function_symlink_function" {
  triggers = {
    resource_name        = "aws_lambda_function.symlink_function"
    resource_type        = "ZIP_LAMBDA_FUNCTION"
    original_source_code = "./src"
    built_output_path    = "./artifacts/symlink_function.zip"
  }
}

resource "aws_lambda_function" "symlink_function" {
  filename      = "./artifacts/symlink_function.zip"
  handler       = "app.lambda_handler"
  runtime       = "python3.11"
  function_name = "symlink_function"
  timeout       = 300
  role          = aws_iam_role.iam_for_lambda.arn
}
