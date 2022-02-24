package main

import (
	"context"
	"reflect"
	"testing"

	"github.com/aws/aws-lambda-go/events"
)

func TestHandler(t *testing.T) {
	got, err := handler(context.Background(), events.APIGatewayV2HTTPRequest{})
	if err != nil {
		t.Errorf("got an error: %s", err)
	}
	want := events.APIGatewayV2HTTPResponse{StatusCode: 200, Body: "CDK!"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %v want %v", got, want)
	}
}