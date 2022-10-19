variable "layer_name" {
    type = string
}

data "aws_lambda_layer_version" "existing" {
  layer_name = var.layer_name
}

output "layer_arn" {
    value = data.aws_lambda_layer_version.existing.arn
}