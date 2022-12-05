variable "source_code" {
  type = string
}

variable "function_name" {
  type = string
}

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
    layers = ["arn:aws:lambda:us-east-1:772514331817:layer:simple_layer1-09695bc2-9810-427c-942e-fbf4009e70f0:1"]
}