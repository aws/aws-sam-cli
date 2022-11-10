variable "INPUT_LAYER" {
    type = string
    default="arn:aws:lambda:us-east-1:772514331817:layer:simple_layer1-09695bc2-9810-427c-942e-fbf4009e70f0:1"
}

output "layer_arn" {
    value = var.INPUT_LAYER
}