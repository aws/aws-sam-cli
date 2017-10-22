package router

import (
	"regexp"
	"fmt"
)

type ApiGatewayIntegration struct {
	Uri string `json:"uri"`
	PassthroughBehavior string `json:"passthroughBehavior"`
	Type string `json:"type"`
}

func (i *ApiGatewayIntegration) GetFunctionArn() (*LambdaFunctionArn, error) {
	// arn:aws:apigateway:us-west-2:lambda:path//2015-03-31/functions/arn:aws:lambda:us-west-2:123456789012:function:Calc/invocations
	firstMatch, err := getFirstMatch(`.*/functions/(.*)/invocations`, i.Uri)

	if err != nil {
		return nil, err
	}

	return &LambdaFunctionArn{ Arn: firstMatch }, nil
}

type LambdaFunctionArn struct {
	Arn string
}

func (a *LambdaFunctionArn) GetFunctionName() (string, error) {
	firstMatch, err := getFirstMatch(`.*:function:(.*)/invocations`, a.Arn)

	if err != nil {
		return "", err
	}

	return firstMatch, nil
}

func getFirstMatch(regex string, value string) (string, error) {
	re := regexp.MustCompile(regex)
	match := re.FindStringSubmatch(value)

	if len(match) < 2 {
		return "", fmt.Errorf("Could not find match in %s", value)
	}

	return match[1], nil
}