variable "function_name" {
    type = string
}

variable "image_uri" {
    type = string
}

variable "l2_function_name" {
    type = string
}

variable "l2_image_uri" {
    type = string
}

resource "aws_iam_role" "iam_for_lambda" {
    name = "iam_for_lambda_l1"

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
    function_name = var.function_name
    role = aws_iam_role.iam_for_lambda.arn
    package_type = "Image"
    handler = null
    timeout = 300
    image_uri = var.image_uri
}

module "l2_lambda" {
    source = "./l2_lambda"
    function_name = var.l2_function_name
    image_uri = var.l2_image_uri
}