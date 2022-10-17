provider "aws" {
  region = "us-east-1"
}

variable "input_layer" {
    type = string
}

variable "layer_name" {
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


module const_layer1 {
    source = "./const_layer"
    input_layer = var.input_layer
}

module const_layer2 {
    source = "./const_layer"
}

module existing_data_layer {
  source = "./data_layer"
  layer_name = var.layer_name
}

resource "aws_lambda_layer_version" "layer4" {
  count = 1
  filename   = "./artifacts/simple_layer4.zip"
  layer_name = "lambda_layer4_${random_pet.this.id}"

  compatible_runtimes = ["python3.8"]
}

module "layer5" {
  source = "./lambda_layer"
  source_code   = "./artifacts/simple_layer5.zip"
  name = "lambda_layer5_${random_pet.this.id}"
}

resource "aws_lambda_function" "function1" {
    filename = "./artifacts/HelloWorldFunction.zip"
    handler = "app.lambda_handler"
    runtime = "python3.8"
    function_name = "function1_${random_pet.this.id}"
    role = aws_iam_role.iam_for_lambda.arn
    layers = [
        module.const_layer1.layer_arn,
    ]
}

resource "aws_lambda_function" "function2" {
    filename = "./artifacts/HelloWorldFunction.zip"
    handler = "app.lambda_handler"
    runtime = "python3.8"
    function_name = "function2_${random_pet.this.id}"
    role = aws_iam_role.iam_for_lambda.arn
    layers = [
        module.const_layer2.layer_arn,
    ]
}

resource "aws_lambda_function" "function3" {
    filename = "./artifacts/HelloWorldFunction.zip"
    handler = "app.lambda_handler"
    runtime = "python3.8"
    function_name = "function3_${random_pet.this.id}"
    role = aws_iam_role.iam_for_lambda.arn
    layers = [
        module.existing_data_layer.layer_arn,
    ]
}

resource "aws_lambda_function" "function4" {
    filename = "./artifacts/HelloWorldFunction.zip"
    handler = "app.lambda_handler"
    runtime = "python3.8"
    function_name = "function4_${random_pet.this.id}"
    role = aws_iam_role.iam_for_lambda.arn
    layers = [
        aws_lambda_layer_version.layer4[0].arn,
    ]
}

module "function5" {
  source = "./lambda_function"
  source_code = "./artifacts/HelloWorldFunction.zip"
  function_name = "function5_${random_pet.this.id}"
  layers = [module.layer5.arn]
}