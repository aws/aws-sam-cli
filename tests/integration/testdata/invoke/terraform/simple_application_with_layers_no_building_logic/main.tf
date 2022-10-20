provider "aws" {
  region = "us-east-1"
}

variable "input_layer" {
    type = string
}

variable "layer_name" {
    type = string
}

variable "bucket_name" {
    type = string
}

resource "random_pet" "this" {
  length = 2
}

resource "aws_s3_bucket" "lambda_functions_code_bucket" {
  bucket = "simpleapplicationtesting${random_pet.this.id}"
  force_destroy = true
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

resource "aws_s3_object" "layer6_code" {
  bucket = aws_s3_bucket.lambda_functions_code_bucket.id
  key    = "layer6_code"
  source = "./artifacts/simple_layer6.zip"
}

resource "aws_lambda_layer_version" "layer6" {
  s3_bucket = aws_s3_bucket.lambda_functions_code_bucket.id
  s3_key = "layer6_code"
  layer_name = "lambda_layer6_${random_pet.this.id}"
  compatible_runtimes = ["python3.8"]
}

resource "aws_s3_object" "layer7_code" {
  bucket = var.bucket_name
  key    = "layer7_code"
  source = "./artifacts/simple_layer7.zip"
}

resource "aws_lambda_layer_version" "layer7" {
  s3_bucket = var.bucket_name
  s3_key = "layer7_code"
  layer_name = "lambda_layer7_${random_pet.this.id}"
  compatible_runtimes = ["python3.8"]
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
  count = 1
  source = "./lambda_function"
  source_code = "./artifacts/HelloWorldFunction.zip"
  function_name = "function5_${random_pet.this.id}"
  layers = [module.layer5.arn]
}

resource "aws_s3_object" "function6_code" {
  bucket = aws_s3_bucket.lambda_functions_code_bucket.id
  key    = "function6_code"
  source = "./artifacts/HelloWorldFunction.zip"
}

resource "aws_lambda_function" "function6" {
    s3_bucket = aws_s3_bucket.lambda_functions_code_bucket.id
    s3_key = "function6_code"
    handler = "app.lambda_handler"
    runtime = "python3.8"
    function_name = "function6_${random_pet.this.id}"
    role = aws_iam_role.iam_for_lambda.arn
    layers = [
        aws_lambda_layer_version.layer6.arn,
    ]
}

resource "aws_s3_object" "function7_code" {
  bucket = var.bucket_name
  key    = "function7_code"
  source = "./artifacts/HelloWorldFunction.zip"
}

resource "aws_lambda_function" "function7" {
    s3_bucket = var.bucket_name
    s3_key = "function7_code"
    handler = "app.lambda_handler"
    runtime = "python3.8"
    function_name = "function7_${random_pet.this.id}"
    role = aws_iam_role.iam_for_lambda.arn
    layers = [
        aws_lambda_layer_version.layer7.arn,
    ]
}

# serverless.tf 3rd party module
module "layer8" {
  # this should be changed to `terraform-aws-modules/lambda/aws` when our change got merged and released`
  source = "git::https://github.com/moelasmar/terraform-aws-lambda.git?ref=master_sam_cli_integration_null_resource_solution"
  create_layer = true
  create_package = false
  layer_name = "lambda_layer8_${random_pet.this.id}"
  compatible_runtimes = ["python3.8"]
  runtime = "python3.8"
  local_existing_package = "./artifacts/simple_layer8.zip"
}

resource "aws_s3_object" "layer9_code" {
  bucket = var.bucket_name
  key    = "layer9_code"
  source = "./artifacts/simple_layer9.zip"
}

module "layer9" {
  # this should be changed to `terraform-aws-modules/lambda/aws` when our change got merged and released`
  source = "git::https://github.com/moelasmar/terraform-aws-lambda.git?ref=master_sam_cli_integration_null_resource_solution"
  create_layer = true
  create_package = false
  s3_existing_package = {
    bucket = var.bucket_name
    key = "layer9_code"
  }
  layer_name = "lambda_layer9_${random_pet.this.id}"
  compatible_runtimes = ["python3.8"]
  runtime = "python3.8"
}

module "function8" {
  # this should be changed to `terraform-aws-modules/lambda/aws` when our change got merged and released`
  source = "git::https://github.com/moelasmar/terraform-aws-lambda.git?ref=master_sam_cli_integration_null_resource_solution"
  create_package = false
  function_name = "function8_${random_pet.this.id}"
  handler       = "app.lambda_handler"
  runtime       = "python3.8"

  layers = [module.layer8.lambda_layer_arn]

  local_existing_package = "./artifacts/HelloWorldFunction.zip"
}

resource "aws_s3_object" "function9_code" {
  bucket = var.bucket_name
  key    = "function9_code"
  source = "./artifacts/HelloWorldFunction.zip"
}

module "function9" {
  # this should be changed to `terraform-aws-modules/lambda/aws` when our change got merged and released`
  source = "git::https://github.com/moelasmar/terraform-aws-lambda.git?ref=master_sam_cli_integration_null_resource_solution"
  create_package = false
  s3_existing_package = {
    bucket = var.bucket_name
    key = "function9_code"
  }
  function_name = "function9_${random_pet.this.id}"
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  layers = [module.layer9.lambda_layer_arn]
}
