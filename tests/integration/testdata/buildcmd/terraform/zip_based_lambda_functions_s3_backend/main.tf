terraform {
  backend "s3" {}
}

provider "aws" {
}

variable "HELLO_FUNCTION_SRC_CODE" {
  type    = string
  default = "./artifacts/HelloWorldFunction"
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
  building_path                  = "./building"
  lambda_src_path                = "./src/list_books"
  lambda_code_filename           = "list_books.zip"
  layer_src_path                 = "./my_layer_code"
  layer_code_filename            = "my_layer.zip"
  hello_world_function_src_path  = var.HELLO_FUNCTION_SRC_CODE
  hello_world_artifact_file_name = "hello_world.zip"
  layer1_src_path                = "./artifacts/layer1"
  layer1_artifact_file_name      = "layer1.zip"
  layer2_src_path                = "./artifacts/layer2"
  layer2_artifact_file_name      = "layer2.zip"
  layer3_src_path                = "./artifacts/layer3"
  layer3_artifact_file_name      = "layer3.zip"
  layer4_src_path                = "./artifacts/layer4"
  layer4_artifact_file_name      = "layer4.zip"
  layer5_src_path                = "./artifacts/layer5"
  layer5_artifact_file_name      = "layer5.zip"
  layer6_src_path                = "./artifacts/layer6"
  layer6_artifact_file_name      = "layer6.zip"
  layer7_src_path                = "./artifacts/layer7"
  layer8_src_path                = "./artifacts/layer8"
  layer10_src_path               = "./artifacts/layer10"
  layer9_src_path                = "./artifacts/layer9"
  layer9_artifact_file_name      = "layer9.zip"
  layer11_src_path               = "./artifacts/layer11"
}

resource "random_uuid" "s3_bucket" {
  keepers = {
    my_key = "my_key"
  }
}

resource "aws_s3_bucket" "lambda_code_bucket" {
  bucket = "lambda_code_bucket-${random_uuid.s3_bucket.result}"
}

resource "aws_s3_object" "s3_lambda_code" {
  bucket = aws_s3_bucket.lambda_code_bucket.id
  key    = "s3_lambda_code"
  source = "${local.building_path}/${local.lambda_code_filename}"
}

resource "null_resource" "build_lambda_function" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "./py_build.sh \"${local.lambda_src_path}\" \"${local.building_path}\" \"${local.lambda_code_filename}\" Function"
  }
}

resource "null_resource" "build_layer_version" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "./py_build.sh \"${local.layer_src_path}\" \"${local.building_path}\" \"${local.layer_code_filename}\" Layer"
  }
}


## /* Lambda Function with code from a local file ###
resource "aws_lambda_function" "from_localfile" {
  filename      = "${local.building_path}/${local.lambda_code_filename}"
  handler       = "index.lambda_handler"
  runtime       = "python3.8"
  function_name = "my_function_from_localfile"
  role          = aws_iam_role.iam_for_lambda.arn
  timeout       = 300
  depends_on = [
    null_resource.build_lambda_function
  ]
}

resource "null_resource" "sam_metadata_aws_lambda_function_from_localfile" {
  triggers = {
    resource_name        = "aws_lambda_function.from_localfile"
    resource_type        = "ZIP_LAMBDA_FUNCTION"
    original_source_code = local.lambda_src_path
    built_output_path    = "${local.building_path}/${local.lambda_code_filename}"
  }
  depends_on = [
    null_resource.build_lambda_function
  ]
}
## */

## /* Lambda Function with code from S3
resource "aws_lambda_function" "from_s3" {
  s3_bucket     = aws_s3_bucket.lambda_code_bucket.bucket
  s3_key        = aws_s3_object.s3_lambda_code.key
  handler       = "index.lambda_handler"
  runtime       = "python3.8"
  function_name = "my_function_from_s3"
  role          = aws_iam_role.iam_for_lambda.arn
  timeout       = 300
  depends_on = [
    null_resource.build_lambda_function
  ]
}

resource "null_resource" "sam_metadata_aws_lambda_function_from_s3" {
  triggers = {
    resource_name        = "aws_lambda_function.from_s3"
    resource_type        = "ZIP_LAMBDA_FUNCTION"
    original_source_code = local.lambda_src_path
    built_output_path    = "${local.building_path}/${local.lambda_code_filename}"
  }
  depends_on = [
    null_resource.build_lambda_function
  ]
}
## */

## /* Level1 Lambda Module and Level2 Lambda Module
module "level1_lambda" {
  source              = "./lambda_tf_module"
  source_code_path    = "${local.building_path}/${local.lambda_code_filename}"
  handler             = "index.lambda_handler"
  function_name       = "my_level1_lambda"
  l2_source_code_path = "${local.building_path}/${local.lambda_code_filename}"
  l2_handler          = "index.lambda_handler"
  l2_function_name    = "my_level2_lambda"
  depends_on = [
    null_resource.build_lambda_function
  ]
}

resource "null_resource" "sam_metadata_aws_lambda_function_level1_lambda" {
  triggers = {
    resource_name        = "module.level1_lambda.aws_lambda_function.this"
    resource_type        = "ZIP_LAMBDA_FUNCTION"
    original_source_code = local.lambda_src_path
    built_output_path    = "${local.building_path}/${local.lambda_code_filename}"
  }
  depends_on = [
    null_resource.build_lambda_function
  ]
}

resource "null_resource" "sam_metadata_aws_lambda_function_level2_lambda" {
  triggers = {
    resource_name        = "module.level1_lambda.module.level2_lambda.aws_lambda_function.this"
    resource_type        = "ZIP_LAMBDA_FUNCTION"
    original_source_code = local.lambda_src_path
    built_output_path    = "${local.building_path}/${local.lambda_code_filename}"
  }
  depends_on = [
    null_resource.build_lambda_function
  ]
}
## */

## /* Lambda Layer with local source code
resource "aws_lambda_layer_version" "from_local" {
  filename   = "${local.building_path}/${local.layer_code_filename}"
  layer_name = "my_layer"

  compatible_runtimes = ["python3.8", "python3.9"]
}

resource "null_resource" "sam_metadata_aws_lambda_layer_version_from_local" {
  triggers = {
    resource_name = "aws_lambda_layer_version.from_local"
    resource_type = "LAMBDA_LAYER"

    original_source_code = local.layer_src_path
    source_code_property = "path"
    built_output_path    = "${local.building_path}/${local.layer_code_filename}"
  }
  depends_on = [
    null_resource.build_layer_version
  ]
}
## */

## /* hello world code builder
resource "null_resource" "build_hello_world_lambda_function" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "./py_build.sh \"${local.hello_world_function_src_path}\" \"${local.building_path}\" \"${local.hello_world_artifact_file_name}\" Function"
  }
}

## */

## /* layer1
resource "null_resource" "build_layer1_version" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "./py_build.sh \"${local.layer1_src_path}\" \"${local.building_path}\" \"${local.layer1_artifact_file_name}\" Layer"
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

## /* layer2
resource "null_resource" "build_layer2_version" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "./py_build.sh \"${local.layer2_src_path}\" \"${local.building_path}\" \"${local.layer2_artifact_file_name}\" Layer"
  }
}

resource "null_resource" "sam_metadata_aws_lambda_layer_version_layer2" {
  triggers = {
    resource_name = "module.layer2.aws_lambda_layer_version.layer"
    resource_type = "LAMBDA_LAYER"

    original_source_code = local.layer2_src_path
    built_output_path    = "${local.building_path}/${local.layer2_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_layer2_version
  ]
}

module "layer2" {
  source      = "./lambda_layer"
  source_code = "${local.building_path}/${local.layer2_artifact_file_name}"
  name        = "lambda_layer2"
  depends_on = [
    null_resource.build_layer2_version
  ]
}

## */ layer2

## /* layer3
resource "null_resource" "build_layer3_version" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "./py_build.sh \"${local.layer3_src_path}\" \"${local.building_path}\" \"${local.layer3_artifact_file_name}\" Layer"
  }
}

resource "null_resource" "sam_metadata_aws_lambda_layer_version_layer3" {
  triggers = {
    resource_name = "aws_lambda_layer_version.layer3[\"my_idx\"]"
    resource_type = "LAMBDA_LAYER"

    original_source_code = local.layer3_src_path
    built_output_path    = "${local.building_path}/${local.layer3_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_layer3_version
  ]
}

resource "aws_s3_object" "layer3_code" {
  bucket = aws_s3_bucket.lambda_code_bucket.id
  key    = "layer3_code"
  source = "${local.building_path}/${local.layer3_artifact_file_name}"
  depends_on = [
    null_resource.build_layer3_version
  ]
}

resource "aws_lambda_layer_version" "layer3" {
  for_each = {
    my_idx = "lambda_layer3"
  }
  s3_bucket           = aws_s3_bucket.lambda_code_bucket.id
  s3_key              = "layer3_code"
  layer_name          = each.value
  compatible_runtimes = ["python3.8"]
  depends_on = [
    null_resource.build_layer3_version, aws_s3_object.layer3_code
  ]
}
## */ layer3

## /* layer4
resource "null_resource" "build_layer4_version" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "./py_build.sh \"${local.layer4_src_path}\" \"${local.building_path}\" \"${local.layer4_artifact_file_name}\" Layer"
  }
}

resource "null_resource" "sam_metadata_aws_lambda_layer_version_layer4" {
  triggers = {
    resource_name = "aws_lambda_layer_version.layer4"
    resource_type = "LAMBDA_LAYER"

    original_source_code = local.layer4_src_path
    built_output_path    = "${local.building_path}/${local.layer4_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_layer4_version
  ]
}

resource "aws_s3_object" "layer4_code" {
  bucket = "existing_s3_bucket_name"
  key    = "layer4_code"
  source = "${local.building_path}/${local.layer4_artifact_file_name}"
  depends_on = [
    null_resource.build_layer4_version
  ]
}

resource "aws_lambda_layer_version" "layer4" {
  s3_bucket           = "existing_s3_bucket_name"
  s3_key              = "layer4_code"
  layer_name          = "lambda_layer4"
  compatible_runtimes = ["python3.8"]
  depends_on = [
    null_resource.build_layer4_version, aws_s3_object.layer4_code
  ]
}
## */ layer4

## /* layer5
resource "null_resource" "build_layer5_version" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "./py_build.sh \"${local.layer5_src_path}\" \"${local.building_path}\" \"${local.layer5_artifact_file_name}\" Layer"
  }
}

resource "null_resource" "sam_metadata_aws_lambda_layer_version_layer5" {
  triggers = {
    resource_type        = "LAMBDA_LAYER"
    original_source_code = local.layer5_src_path
    built_output_path    = "${local.building_path}/${local.layer5_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_layer5_version
  ]
}

resource "aws_s3_object" "layer5_code" {
  bucket = "existing_s3_bucket_name"
  key    = "layer5_code"
  source = "${local.building_path}/${local.layer5_artifact_file_name}"
  depends_on = [
    null_resource.build_layer5_version
  ]
}

resource "aws_lambda_layer_version" "layer5" {
  s3_bucket           = "existing_s3_bucket_name"
  s3_key              = "layer5_code"
  layer_name          = "lambda_layer5"
  compatible_runtimes = ["python3.8"]
  depends_on = [
    null_resource.build_layer5_version, aws_s3_object.layer5_code
  ]
}
## */ layer5

## /* layer6
resource "null_resource" "build_layer6_version" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "./py_build.sh \"${local.layer6_src_path}\" \"${local.building_path}\" \"${local.layer6_artifact_file_name}\" Layer"
  }
}

resource "null_resource" "sam_metadata_aws_lambda_layer_version_layer6" {
  triggers = {
    resource_type        = "LAMBDA_LAYER"
    original_source_code = local.layer6_src_path
    built_output_path    = "${local.building_path}/${local.layer6_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_layer6_version
  ]
}

resource "aws_lambda_layer_version" "layer6" {
  filename            = "${local.building_path}/${local.layer6_artifact_file_name}"
  layer_name          = "lambda_layer6"
  compatible_runtimes = ["python3.8"]
  depends_on = [
    null_resource.build_layer6_version
  ]
}
## */ layer6

## /* function1 connected to layer1

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
  role          = aws_iam_role.iam_for_lambda.arn
  timeout       = 300
  layers = [
    aws_lambda_layer_version.layer1[0].arn,
  ]
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}

## /* function1 connected to layer1

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
  source        = "./lambda_function"
  source_code   = "${local.building_path}/${local.hello_world_artifact_file_name}"
  function_name = "function2"
  layers        = [module.layer2.arn]
}

## /* function2 connected to layer2

## /* function3 connected to layer3
resource "null_resource" "sam_metadata_aws_lambda_function3" {
  triggers = {
    resource_name        = "aws_lambda_function.function3"
    resource_type        = "ZIP_LAMBDA_FUNCTION"
    original_source_code = local.hello_world_function_src_path
    built_output_path    = "${local.building_path}/${local.hello_world_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}

resource "aws_s3_object" "function3_code" {
  bucket = aws_s3_bucket.lambda_code_bucket.id
  key    = "function3_code"
  source = "${local.building_path}/${local.hello_world_artifact_file_name}"
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}

resource "aws_lambda_function" "function3" {
  s3_bucket     = aws_s3_bucket.lambda_code_bucket.id
  s3_key        = "function3_code"
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  function_name = "function3"
  role          = aws_iam_role.iam_for_lambda.arn
  timeout       = 300
  layers = [
    aws_lambda_layer_version.layer3["my_idx"].arn,
  ]
  depends_on = [
    null_resource.build_hello_world_lambda_function, aws_s3_object.function3_code
  ]
}
## /* function3 connected to layer3

## /* function4 connected to layer4
resource "null_resource" "sam_metadata_aws_lambda_function4" {
  triggers = {
    resource_name        = "aws_lambda_function.function4"
    resource_type        = "ZIP_LAMBDA_FUNCTION"
    original_source_code = local.hello_world_function_src_path
    built_output_path    = "${local.building_path}/${local.hello_world_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}

resource "aws_s3_object" "function4_code" {
  bucket = "existing_s3_bucket_name"
  key    = "function4_code"
  source = "${local.building_path}/${local.hello_world_artifact_file_name}"
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}

resource "aws_lambda_function" "function4" {
  s3_bucket     = "existing_s3_bucket_name"
  s3_key        = "function4_code"
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  function_name = "function4"
  role          = aws_iam_role.iam_for_lambda.arn
  timeout       = 300
  layers = [
    aws_lambda_layer_version.layer4.arn,
  ]
  depends_on = [
    null_resource.build_hello_world_lambda_function, aws_s3_object.function4_code
  ]
}
## /* function4 connected to layer4

## /* function5 connected to layer5
resource "null_resource" "sam_metadata_aws_lambda_function5" {
  triggers = {
    resource_type        = "ZIP_LAMBDA_FUNCTION"
    original_source_code = local.hello_world_function_src_path
    built_output_path    = "${local.building_path}/${local.hello_world_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}

resource "aws_s3_object" "function5_code" {
  bucket = "existing_s3_bucket_name"
  key    = "function5_code"
  source = "${local.building_path}/${local.hello_world_artifact_file_name}"
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}

resource "aws_lambda_function" "function5" {
  s3_bucket     = "existing_s3_bucket_name"
  s3_key        = "function5_code"
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  function_name = "function5"
  role          = aws_iam_role.iam_for_lambda.arn
  timeout       = 300
  layers = [
    aws_lambda_layer_version.layer5.arn,
  ]
  depends_on = [
    null_resource.build_hello_world_lambda_function, aws_s3_object.function5_code
  ]
}
## /* function5 connected to layer5


## /* function6 connected to layer6
resource "null_resource" "sam_metadata_aws_lambda_function6" {
  triggers = {
    resource_type        = "ZIP_LAMBDA_FUNCTION"
    original_source_code = local.hello_world_function_src_path
    built_output_path    = "${local.building_path}/${local.hello_world_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}

resource "aws_lambda_function" "function6" {
  filename      = "${local.building_path}/${local.hello_world_artifact_file_name}"
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  function_name = "function6"
  role          = aws_iam_role.iam_for_lambda.arn
  timeout       = 300
  layers = [
    aws_lambda_layer_version.layer6.arn,
  ]
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}
## /* function6 connected to layer6

# serverless.tf 3rd party module
module "layer7" {
  source              = "terraform-aws-modules/lambda/aws"
  version             = "4.6.0"
  create_layer        = true
  layer_name          = "lambda_layer7"
  compatible_runtimes = ["python3.8"]
  runtime             = "python3.8"
  source_path = {
    path             = local.layer7_src_path
    prefix_in_zip    = "python"
    pip_requirements = true
  }
}

module "function7" {
  source        = "terraform-aws-modules/lambda/aws"
  version       = "4.6.0"
  source_path   = local.hello_world_function_src_path
  function_name = "function7"
  timeout       = 300
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  layers        = [module.layer7.lambda_layer_arn]
}

module "layer8" {
  source              = "terraform-aws-modules/lambda/aws"
  version             = "4.6.0"
  create_layer        = true
  layer_name          = "lambda_layer8"
  compatible_runtimes = ["python3.8"]
  runtime             = "python3.8"
  store_on_s3         = true
  s3_bucket           = "existing_s3_bucket"
  source_path = {
    path             = local.layer8_src_path
    prefix_in_zip    = "python"
    pip_requirements = true
  }
}

module "function8" {
  source        = "terraform-aws-modules/lambda/aws"
  version       = "4.6.0"
  source_path   = local.hello_world_function_src_path
  function_name = "function8"
  timeout       = 300
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  layers        = [module.layer8.lambda_layer_arn]
  store_on_s3   = true
  s3_bucket     = "existing_s3_bucket"
}

## /* layer 9 - Serverless tf
resource "null_resource" "build_layer9_version" {
  triggers = {
    build_number = "${timestamp()}"
  }

  provisioner "local-exec" {
    command = "./py_build.sh \"${local.layer9_src_path}\" \"${local.building_path}\" \"${local.layer9_artifact_file_name}\" Layer"
  }
}

resource "null_resource" "sam_metadata_aws_lambda_layer_version_layer9" {
  triggers = {
    resource_name        = "module.layer9.aws_lambda_layer_version.this[0]"
    resource_type        = "LAMBDA_LAYER"
    original_source_code = local.layer1_src_path
    built_output_path    = "${local.building_path}/${local.layer9_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_layer9_version
  ]
}

module "layer9" {
  source                 = "terraform-aws-modules/lambda/aws"
  version                = "4.6.0"
  create_layer           = true
  create_package         = false
  layer_name             = "lambda_layer9"
  compatible_runtimes    = ["python3.8"]
  runtime                = "python3.8"
  s3_bucket              = "existing_s3_bucket"
  local_existing_package = "${local.building_path}/${local.layer9_artifact_file_name}"
}
## */ Layer9


## /* function1 connected to layer1 - Serverless tf
resource "null_resource" "sam_metadata_aws_lambda_function9" {
  triggers = {
    resource_name        = "module.function9.aws_lambda_function.this[0]"
    resource_type        = "ZIP_LAMBDA_FUNCTION"
    original_source_code = local.hello_world_function_src_path
    built_output_path    = "${local.building_path}/${local.hello_world_artifact_file_name}"
  }
  depends_on = [
    null_resource.build_hello_world_lambda_function
  ]
}

module "function9" {
  source                 = "terraform-aws-modules/lambda/aws"
  version                = "4.6.0"
  local_existing_package = "${local.building_path}/${local.hello_world_artifact_file_name}"
  create_package         = false
  timeout                = 300
  function_name          = "function9"
  handler                = "app.lambda_handler"
  runtime                = "python3.8"
  layers                 = [module.layer9.lambda_layer_arn]
}
## /* function9 connected to layer9


module "layer10" {
  source              = "terraform-aws-modules/lambda/aws"
  version             = "4.6.0"
  create_layer        = true
  layer_name          = "lambda_layer10"
  compatible_runtimes = ["python3.8"]
  runtime             = "python3.8"
  store_on_s3         = true
  s3_bucket           = aws_s3_bucket.lambda_code_bucket.id
  source_path = {
    path             = local.layer10_src_path
    prefix_in_zip    = "python"
    pip_requirements = true
  }
}

module "function10" {
  source        = "terraform-aws-modules/lambda/aws"
  version       = "4.6.0"
  source_path   = local.hello_world_function_src_path
  function_name = "function10"
  timeout       = 300
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  layers        = [module.layer10.lambda_layer_arn]
  store_on_s3   = true
  s3_bucket     = aws_s3_bucket.lambda_code_bucket.id
}

module "layer11" {
  source              = "terraform-aws-modules/lambda/aws"
  version             = "4.6.0"
  create_layer        = true
  layer_name          = "lambda_layer11"
  compatible_runtimes = ["python3.8"]
  runtime             = "python3.8"
  source_path = [{
    path             = local.layer11_src_path
    prefix_in_zip    = "python"
    pip_requirements = true
  }]
}

module "function11" {
  source  = "terraform-aws-modules/lambda/aws"
  version = "4.6.0"
  timeout = 300
  source_path = [{
    path = local.hello_world_function_src_path
  }]
  function_name = "function11"
  handler       = "app.lambda_handler"
  runtime       = "python3.8"
  layers        = [module.layer11.lambda_layer_arn]
}
