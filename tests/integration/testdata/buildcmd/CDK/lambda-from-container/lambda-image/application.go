package main

import (
  "fmt"
  "context"
  "github.com/aws/aws-lambda-go/lambda"
)

type LambdaEvent struct {
  Name string `json:"name"`
}

func lambdaHandler(ctx context.Context, name LambdaEvent) (string, error) {
  return fmt.Sprintf("It Works!"), nil
}

func main() {
  lambda.Start(lambdaHandler)
}