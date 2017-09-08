package router

import (
	"net/http"
	"strings"
)

// ServerlessRouterMount represents a single mount point on the API
// Such as '/path', the HTTP method, and the function to resolve it
type ServerlessRouterMount struct {
	Name     string
	Function *AWSServerlessFunction
	Handler  http.HandlerFunc
	Path     string
	Method   string
}

// Methods gets an array of HTTP methods from a AWS::Serverless::Function
// API event source method declaration (which could include 'any')
func (m *ServerlessRouterMount) Methods() []string {
	switch strings.ToUpper(m.Method) {
	case "ANY":
		return []string{"OPTIONS", "GET", "HEAD", "POST", "PUT", "DELETE", "TRACE", "CONNECT"}
	default:
		return []string{strings.ToUpper(m.Method)}
	}
}
