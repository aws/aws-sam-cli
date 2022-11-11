variable "source_code" {
  type = string
}

variable "function_name" {
  type = string
}

variable "LAYER_NAME" {
  type = string
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

resource "random_pet" "this" {
  length = 2
}

resource "aws_iam_role" "iam_for_lambda" {
  name = "iam_for_lambda_${random_pet.this.id}"

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
    filename = var.source_code
    handler = "app.lambda_handler"
    runtime = "python3.8"
    timeout = 300
    function_name = var.function_name
    role = aws_iam_role.iam_for_lambda.arn
    layers = ["arn:aws:lambda:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:layer:${var.LAYER_NAME}:1"]
}