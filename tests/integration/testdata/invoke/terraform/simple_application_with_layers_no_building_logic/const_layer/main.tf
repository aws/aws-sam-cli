variable "input_layer" {
    type = string
}

output "layer_arn" {
    value = var.input_layer
}