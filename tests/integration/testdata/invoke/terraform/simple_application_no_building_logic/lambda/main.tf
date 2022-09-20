variable "source_code_path" {
	type = string
}

variable "handler" {
	type = string
}

variable "function_name" {
	type = string
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


resource "aws_lambda_function" "this" {
	filename = var.source_code_path
	handler = var.handler
	runtime = "python3.8"
	function_name = var.function_name
	role = aws_iam_role.iam_for_lambda.arn
}

module "level2_lambda" {
   source = "./lambda2"
   source_code_path = "HelloWorldFunction.zip"
   handler = "app.lambda_handler"
   function_name = "level2_lambda_function"
}

resource "null_resource" "sam_metadata_aws_lambda_function_s3_lambda" {
  triggers = {
    # This is a way to let SAM CLI correlates between the Lambda layer resource, and this metadata
    # resource
    resource_name = "aws_lambda_function.this"
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

