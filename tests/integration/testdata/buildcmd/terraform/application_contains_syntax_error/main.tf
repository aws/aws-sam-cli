provider "aws" {}

variable "HELLO_FUNCTION_SRC_CODE" {
  type    = string
  default = "src/artifacts/HelloWorldFunction"
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
  building_path                  = "building"
  hello_world_function_src_path  = var.HELLO_FUNCTION_SRC_CODE
  hello_world_artifact_file_name = "hello_world.zip"
}

## /* function1 connected to layer1

resource "null_resource" "build_hello_world_lambda_function" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "../py_build.sh \"${local.hello_world_function_src_path}\" \"${local.building_path}\" \"${local.hello_world_artifact_file_name}\" Function"
  }
}

resource "null_resource" "sam_metadata_aws_lambda_function1" {
  triggers = {
    resource_name        = "aws_lambda_function.function1"
    resource_type        = "ZIP_LAMBDA_FUNCTION"
    original_source_code = local.hello_world_function_src_path
    built_output_path    = "${local.building_path}/${local.hello_world_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}

resource "aws_lambda_functionnn" "function1" {
  filename      = "${local.building_path}/${local.hello_world_artifact_file_name}"
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  function_name = "function1"
  timeout       = 300
  role          = aws_iam_role.iam_for_lambda.arn
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}