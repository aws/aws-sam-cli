package router

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
	Headers           map[string]string `json:"headers"`
	PathParameters    map[string]string `json:"pathParameters"`
	StageVariables    map[string]string `json:"stageVariables"`
	Path              string            `json:"path"`
	IsBase64Encoded   bool              `json:"isBase64Encoded"`
}

// RequestContext represents the context object that gets passed to an AWS Lambda function
type RequestContext struct {
	ResourceID   string          `json:"resourceId,omitempty"`
	APIID        string          `json:"apiId,omitempty"`
	ResourcePath string          `json:"resourcePath,omitempty"`
	HTTPMethod   string          `json:"httpMethod,omitempty"`
	RequestID    string          `json:"requestId,omitempty"`
	AccountsID   string          `json:"accountId,omitempty"`
	Stage        string          `json:"stage,omitempty"`
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
// event details from a http.Request and isBase64Encoded value
func NewEvent(req *http.Request, isBase64Encoded bool) (*Event, error) {

	var body []byte
	if req.Body != nil {
		var err error
		body, err = ioutil.ReadAll(req.Body)
		if err != nil {
			return nil, err
		}
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
		IsBase64Encoded:   isBase64Encoded,
	}

	event.RequestContext.Identity.SourceIP = req.RemoteAddr
	event.RequestContext.ResourcePath = req.URL.Path
	event.RequestContext.HTTPMethod = req.Method
	event.RequestContext.Stage = "prod"

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
