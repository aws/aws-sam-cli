provider "aws" {}

variable "HELLO_FUNCTION_SRC_CODE" {
  type    = string
  default = "../src/artifacts/HelloWorldFunction"
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
  building_path                  = "../building"
  hello_world_function_src_path  = var.HELLO_FUNCTION_SRC_CODE
  hello_world_artifact_file_name = "hello_world.zip"
  layer1_src_path                = "../src/artifacts/layer1"
  layer1_artifact_file_name      = "layer1.zip"
}

## /* layer1
resource "null_resource" "build_layer1_version" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "powershell.exe -File ..\\PyBuild.ps1 ${local.layer1_src_path} ${local.building_path} ${local.layer1_artifact_file_name} Layer"
  }
}

resource "null_resource" "sam_metadata_aws_lambda_layer_version_layer1" {
  triggers = {
    resource_name = "aws_lambda_layer_version.layer1[0]"
    resource_type = "LAMBDA_LAYER"

    original_source_code = local.layer1_src_path
    built_output_path    = "${local.building_path}/${local.layer1_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_layer1_version
  ]
}

resource "aws_lambda_layer_version" "layer1" {
  count               = 1
  filename            = "${local.building_path}/${local.layer1_artifact_file_name}"
  layer_name          = "lambda_layer1"
  compatible_runtimes = ["python3.8"]
  depends_on = [
    null_resource.build_layer1_version
  ]
}

## */ layer1

## /* function1 connected to layer1

resource "null_resource" "build_hello_world_lambda_function" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "powershell.exe -File ..\\PyBuild.ps1 ${local.hello_world_function_src_path} ${local.building_path} ${local.hello_world_artifact_file_name} Function"
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

resource "aws_lambda_function" "function1" {
  filename      = "${local.building_path}/${local.hello_world_artifact_file_name}"
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  function_name = "function1"
  timeout       = 300
  role          = aws_iam_role.iam_for_lambda.arn
  layers = [
    aws_lambda_layer_version.layer1[0].arn,
  ]
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}

## /* function1 connected to layer1

## /* layer2
resource "null_resource" "build_layer2_version" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "powershell.exe -File ..\\PyBuild.ps1 ${local.layer1_src_path} ${local.building_path} ${local.layer1_artifact_file_name} Layer"
  }
}

resource "null_resource" "sam_metadata_aws_lambda_layer_version_layer2" {
  triggers = {
    resource_name = "module.layer2.aws_lambda_layer_version.layer"
    resource_type = "LAMBDA_LAYER"

    original_source_code = local.layer1_src_path
    built_output_path    = "${local.building_path}/${local.layer1_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_layer2_version
  ]
}

module "layer2" {
  source      = "../modules/lambda_layer"
  source_code = "${local.building_path}/${local.layer1_artifact_file_name}"
  name        = "lambda_layer2"
  depends_on = [
    null_resource.build_layer2_version
  ]
}

## */ layer2

## /* function2 connected to layer2

resource "null_resource" "sam_metadata_aws_lambda_function2" {
  triggers = {
    resource_name        = "module.function2.aws_lambda_function.this"
    resource_type        = "ZIP_LAMBDA_FUNCTION"
    original_source_code = local.hello_world_function_src_path
    built_output_path    = "${local.building_path}/${local.hello_world_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}

module "function2" {
  source        = "../modules/lambda_function"
  source_code   = "${local.building_path}/${local.hello_world_artifact_file_name}"
  function_name = "function2"
  layers        = [module.layer2.arn]
}

## /* function2 connected to layer2