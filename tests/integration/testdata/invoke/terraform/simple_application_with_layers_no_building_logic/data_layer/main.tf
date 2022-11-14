variable "LAYER_NAME" {
    type = string
}

data "aws_lambda_layer_version" "existing" {
  layer_name = var.LAYER_NAME
}

output "layer_arn" {
    value = data.aws_lambda_layer_version.existing.arn
}