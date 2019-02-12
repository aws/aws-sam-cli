package main

import (
	"github.com/aws/aws-lambda-go/events"
	"github.com/aws/aws-lambda-go/lambda"
)

func handler(request events.APIGatewayProxyRequest) (string, error) {
    check_that_dependency_is_usable := events.APIGatewayProxyResponse{
		Body:       "Hello",
		StatusCode: 200,
	}

	_ = check_that_dependency_is_usable

	return "Hello World", nil
}

func main() {
	lambda.Start(handler)
}