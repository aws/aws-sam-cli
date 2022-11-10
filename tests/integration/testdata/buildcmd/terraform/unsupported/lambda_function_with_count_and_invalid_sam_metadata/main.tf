provider "aws" {
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
    building_path = "./building"
    function_src_path = "./lambda_src/function1"
    function_artifact_filename = "function1.zip"
    layer1_src_path = "./lambda_src/layer1"
    layer1_artifact_filename = "layer1.zip"
    layer2_src_path = "./lambda_src/layer2"
    layer2_artifact_filename = "layer2.zip"
}

resource "random_uuid" "s3_bucket" {
    keepers = {
        my_key = "my_key"
    }
}

resource "aws_s3_bucket" "lambda_code_bucket" {
    bucket = "lambda_code_bucket-${random_uuid.s3_bucket.result}"
}

resource "aws_s3_object" "lambda_function_code" {
    bucket = aws_s3_bucket.lambda_code_bucket.bucket
    key = "function"
    source = "${local.building_path}/${local.function_artifact_filename}"
}

resource "null_resource" "build_function" {
    triggers = {
        build_number = "${timestamp()}"
    }

    provisioner "local-exec" {
        command = "./py_build.sh \"${local.function_src_path}\" \"${local.building_path}\" \"${local.function_artifact_filename}\" Function"
    }
}

resource "null_resource" "sam_metadata_aws_lambda_function1" {
    triggers = {
        resource_name = "aws_lambda_function.function1"
        resource_type = "ZIP_LAMBDA_FUNCTION"
        original_source_code = local.function_src_path
        built_output_path = "${local.building_path}/${local.function_artifact_filename}"
    }
    depends_on = [
        null_resource.build_function
    ]
}

resource "aws_lambda_function" "function1" {
    count = 1
    s3_bucket = aws_s3_bucket.lambda_code_bucket.bucket
    s3_key = aws_s3_object.lambda_function_code.key
    handler = "app.lambda_handler"
    runtime = "python3.8"
    function_name = "${var.namespace}-function1-${random_uuid.s3_bucket.result}"
    role = aws_iam_role.iam_for_lambda.arn
    timeout = 300
    layers = [
        aws_lambda_layer_version.layer1[0].arn
    ]
    depends_on = [
        null_resource.sam_metadata_aws_lambda_function1
    ]
}

## /* layer1
resource "null_resource" "build_layer1_version" {
    triggers = {
        build_number = "${timestamp()}"
    }

    provisioner "local-exec" {
        command = "./py_build.sh \"${local.layer1_src_path}\" \"${local.building_path}\" \"${local.layer1_artifact_filename}\" Layer"
    }
}

resource "null_resource" "sam_metadata_aws_lambda_layer_version_layer1" {
    triggers = {
        resource_name = "aws_lambda_layer_version.layer1[0]"
        resource_type = "LAMBDA_LAYER"

        original_source_code = local.layer1_src_path
        built_output_path = "${local.building_path}/${local.layer1_artifact_filename}"
    }
    depends_on = [
        null_resource.build_layer1_version
    ]
}

resource "aws_lambda_layer_version" "layer1" {
    count = 1
    filename = "${local.building_path}/${local.layer1_artifact_filename}"
    layer_name = "${var.namespace}_lambda_layer1"
    compatible_runtimes = ["python3.8", "python3.9"]
    depends_on = [
        null_resource.build_layer1_version
    ]
}
## */