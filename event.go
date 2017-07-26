package main

import (
	"encoding/json"
	"io/ioutil"
	"net/http"

	"github.com/gorilla/mux"
)

// Event represents an event passed to an AWS Lambda function by the runtime
type Event struct {
	HTTPMethod        string            `json:"httpMethod"`
	Body              string            `json:"body"`
	Resource          string            `json:"resource"`
	RequestContext    RequestContext    `json:"requestContext"`
	QueryStringParams map[string]string `json:"queryStringParameters"`
	Headers           map[string]string `json:"Headers"`
	PathParameters    map[string]string `json:"pathParameters"`
	StageVariables    map[string]string `json:"stageVariables"`
	Path              string            `json:"path"`
}
type RequestContext struct {
	ResourceID   string          `json:"resourceId"`
	APIID        string          `json:"apiId"`
	ResourcePath string          `json:"resourcePath"`
	HTTPMethod   string          `json:"httpMethod"`
	RequestID    string          `json:"requestId"`
	AccountsID   string          `json:"accountId"`
	Identity     ContextIdentity `json:"identity"`
}

type ContextIdentity struct {
	APIKey                        string `json:"apiKey"`
	UserARN                       string `json:"userArn"`
	CognitoAuthenticationType     string `json:"cognitoAuthenticationType"`
	Caller                        string `json:"caller"`
	UserAgent                     string `json:"userAgent"`
	User                          string `json:"user"`
	CognitoIdentityPoolID         string `json:"cognitoIdentityPoolId"`
	CognitoIdentityID             string `json:"cognitoIdentityId"`
	CognitoAuthenticationProvider string `json:"cognitoAuthenticationProvider"`
	SourceIP                      string `json:"sourceIp"`
	AccountID                     string `json:"accountId"`
}

// NewEvent initalises and populates a new ApiEvent with
// event details from a http.Request
func NewEvent(req *http.Request) (*Event, error) {

	body, err := ioutil.ReadAll(req.Body)
	if err != nil {
		return nil, err
	}

	headers := map[string]string{}
	for name, values := range req.Header {
		for _, value := range values {
			headers[name] = value
		}
	}

	query := map[string]string{}
	for name, values := range req.URL.Query() {
		for _, value := range values {
			query[name] = value
		}
	}

	event := &Event{
		HTTPMethod:        req.Method,
		Body:              string(body),
		Headers:           headers,
		QueryStringParams: query,
		Path:              req.URL.Path,
		Resource:          req.URL.Path,
		PathParameters:    mux.Vars(req),
	}

	event.RequestContext.Identity.SourceIP = req.RemoteAddr
	event.RequestContext.ResourcePath = req.URL.Path

	return event, nil

}

// JSON returns the event as a JSON string
func (e *Event) JSON() (string, error) {

	data, err := json.Marshal(e)
	if err != nil {
		return "", err
	}

	return string(data), nil

}
