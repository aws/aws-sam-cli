variable "source_code" {
  type = string
}

variable "name" {
  type = string
}

resource "aws_lambda_layer_version" "layer" {
  filename   = var.source_code
  layer_name = var.name

  compatible_runtimes = ["python3.9"]
}

output "arn" {
  value = aws_lambda_layer_version.layer.arn
}