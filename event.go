package main

import (
	"encoding/json"
	"io/ioutil"
	"net/http"

	"github.com/gorilla/mux"
)

// Event represents an event passed to an AWS Lambda function by the runtime
type Event struct {
	HTTPMethod        string            `json:"httpMethod,omitempty"`
	Body              string            `json:"body,omitempty"`
	Resource          string            `json:"resource,omitempty"`
	RequestContext    RequestContext    `json:"requestContext,omitempty"`
	QueryStringParams map[string]string `json:"queryStringParameters,omitempty"`
	Headers           map[string]string `json:"headers,omitempty"`
	PathParameters    map[string]string `json:"pathParameters,omitempty"`
	StageVariables    map[string]string `json:"stageVariables,omitempty"`
	Path              string            `json:"path,omitempty"`
}

// RequestContext represents the context object that gets passed to an AWS Lambda function
type RequestContext struct {
	ResourceID   string          `json:"resourceId,omitempty"`
	APIID        string          `json:"apiId,omitempty"`
	ResourcePath string          `json:"resourcePath,omitempty"`
	HTTPMethod   string          `json:"httpMethod,omitempty"`
	RequestID    string          `json:"requestId,omitempty"`
	AccountsID   string          `json:"accountId,omitempty"`
	Identity     ContextIdentity `json:"identity,omitempty"`
}

// ContextIdentity represents the identity section of the context object that gets passed to an AWS Lambda function
type ContextIdentity struct {
	APIKey                        string `json:"apiKey,omitempty"`
	UserARN                       string `json:"userArn,omitempty"`
	CognitoAuthenticationType     string `json:"cognitoAuthenticationType,omitempty"`
	Caller                        string `json:"caller,omitempty"`
	UserAgent                     string `json:"userAgent,omitempty"`
	User                          string `json:"user,omitempty"`
	CognitoIdentityPoolID         string `json:"cognitoIdentityPoolId,omitempty"`
	CognitoIdentityID             string `json:"cognitoIdentityId,omitempty"`
	CognitoAuthenticationProvider string `json:"cognitoAuthenticationProvider,omitempty"`
	SourceIP                      string `json:"sourceIp,omitempty"`
	AccountID                     string `json:"accountId,omitempty"`
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

	pathParams := mux.Vars(req)
	if len(pathParams) == 0 {
		pathParams = nil
	}

	event := &Event{
		HTTPMethod:        req.Method,
		Body:              string(body),
		Headers:           headers,
		QueryStringParams: query,
		Path:              req.URL.Path,
		Resource:          req.URL.Path,
		PathParameters:    pathParams,
	}

	event.RequestContext.Identity.SourceIP = req.RemoteAddr
	event.RequestContext.ResourcePath = req.URL.Path
	event.RequestContext.HTTPMethod = req.Method

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
