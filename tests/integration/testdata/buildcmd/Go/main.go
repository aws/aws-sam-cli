package main

import (
	"fmt"

	"github.com/aws/aws-lambda-go/lambda"
)

func handler() (string, error) {
	return fmt.Sprintf("{'message': 'Hello World'}"), nil
}

func main() {
	lambda.Start(handler)
}
