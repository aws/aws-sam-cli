package router

import (
	"net/http"
	"strings"
)

const MuxPathRegex = ".+"

var HttpMethods = []string{"OPTIONS", "GET", "HEAD", "POST", "PUT", "DELETE", "PATCH"}

// ServerlessRouterMount represents a single mount point on the API
// Such as '/path', the HTTP method, and the function to resolve it
type ServerlessRouterMount struct {
	Name     string
	Function *AWSServerlessFunction
	Handler  http.HandlerFunc
	Path     string
	Method   string

	// authorization settings
	AuthType       string
	AuthFunction   *AWSServerlessFunction
	IntegrationArn *LambdaFunctionArn
}

// Methods gets an array of HTTP methods from a AWS::Serverless::Function
// API event source method declaration (which could include 'any')
func (m *ServerlessRouterMount) Methods() []string {
	switch strings.ToUpper(m.Method) {
	case "ANY":
		return HttpMethods
	default:
		return []string{strings.ToUpper(m.Method)}
	}
}

// Returns the mount path adjusted for mux syntax. For example, if the
// SAM template specifies /{proxy+} we replace that with /{proxy:.*}
func (m *ServerlessRouterMount) GetMuxPath() string {
	outputPath := m.Path

	if strings.Contains(outputPath, "+") {
		outputPath = strings.Replace(outputPath, "+", ":"+MuxPathRegex, -1)
	}

	return outputPath
}
