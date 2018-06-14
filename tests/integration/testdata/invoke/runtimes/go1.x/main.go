package main

import (
	"github.com/aws/aws-lambda-go/lambda"
)

// Handler is your Lambda function handler
// It uses Amazon API Gateway request/responses provided by the aws-lambda-go/events package,
// However you could use other event sources (S3, Kinesis etc), or JSON-decoded primitive types such as 'string'.
func Handler() (string, error) {

	return "Hello World", nil

}

func main() {
	lambda.Start(Handler)
}
