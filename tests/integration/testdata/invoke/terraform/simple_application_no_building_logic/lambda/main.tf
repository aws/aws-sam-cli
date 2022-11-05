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
	timeout = 300
	role = aws_iam_role.iam_for_lambda.arn
}

module "level2_lambda" {
   source = "./lambda2"
   source_code_path = "HelloWorldFunction.zip"
   handler = "app.lambda_handler"
   function_name = "level2_lambda_function"
}