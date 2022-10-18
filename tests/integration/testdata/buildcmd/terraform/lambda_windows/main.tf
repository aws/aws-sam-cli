provider "aws" {
    region = "us-west-1"
}

resource "aws_iam_role" "lambda_role" {
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
    lambda_src_path = "./hello_world"
    lambda_code_filename = "hello_world.zip"
}

resource "random_uuid" "s3_bucket" {
    keepers = {
        my_key = "my_key"
    }
}

resource "aws_s3_bucket" "lambda_code_bucket" {
    bucket = "lambda_code_bukcet_windows"
}

resource "aws_s3_object" "s3_lambda_code" {
    bucket = aws_s3_bucket.lambda_code_bucket.bucket
    key = "s3_lambda_code"
    source = "${local.building_path}/${local.lambda_code_filename}"
}

resource "null_resource" "build_lambda_function" {
    triggers = {
        build_number = "${timestamp()}"
    }

    provisioner "local-exec" {
        command = "powershell.exe -File .\\first_script.ps1 ${local.lambda_src_path} ${local.building_path} ${local.lambda_code_filename}"
    }
}

resource "aws_lambda_function" "from_localfile" {
    filename = "${local.building_path}/${local.lambda_code_filename}"
    handler = "app.handler"
    runtime = "python3.9"
    function_name = "my_lambda_function_from_local_file"
    role = aws_iam_role.lambda_role.arn
    timeout = 20
    depends_on = [
        null_resource.build_lambda_function
    ]
}

resource "null_resource" "sam_metadata_aws_lambda_function_from_localfile" {
    triggers = {
        resource_name = "aws_lambda_function.from_localfile"
        resource_type = "ZIP_LAMBDA_FUNCTION"
        original_source_code = local.lambda_src_path
        built_output_path = "${local.building_path}/${local.lambda_code_filename}"
    }

    depends_on = [
        null_resource.build_lambda_function
    ]
}