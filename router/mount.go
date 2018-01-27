package router

import (
	"encoding/base64"
	"io/ioutil"
	"mime"
	"net/http"
	"strings"
	"unicode/utf8"
	"log"
	"fmt"
)

const MuxPathRegex = ".+"
var HttpMethods = []string{"OPTIONS", "GET", "HEAD", "POST", "PUT", "DELETE", "PATCH"}

// EventHandlerFunc is similar to Go http.Handler but it receives an event from API Gateway
// instead of http.Request
type EventHandlerFunc func(http.ResponseWriter, *Event)

// ServerlessRouterMount represents a single mount point on the API
// Such as '/path', the HTTP method, and the function to resolve it
type ServerlessRouterMount struct {
	Name             string
	Function         *AWSServerlessFunction
	Handler          EventHandlerFunc
	Path             string
	Method           string
	BinaryMediaTypes []string

	// authorization settings
	AuthType       string
	AuthFunction   *AWSServerlessFunction
	IntegrationArn *LambdaFunctionArn
}

// Returns the wrapped handler to encode the body as base64 when binary
// media types contains Content-Type
func (m *ServerlessRouterMount) WrappedHandler() http.HandlerFunc {
	return http.HandlerFunc(func(w http.ResponseWriter, req *http.Request) {
		contentType := req.Header.Get("Content-Type")
		mediaType, _, err := mime.ParseMediaType(contentType)
		binaryContent := false

		if err == nil {
			for _, value := range m.BinaryMediaTypes {
				if value != "" && value == mediaType {
					binaryContent = true
					break
				}
			}
		}

		if binaryContent {
			if body, err := ioutil.ReadAll(req.Body); err == nil && !utf8.Valid(body) {
				req.Body = ioutil.NopCloser(strings.NewReader(base64.StdEncoding.EncodeToString(body)))
			} else {
				req.Body = ioutil.NopCloser(strings.NewReader(string(body)))
			}
		}

		event, err := NewEvent(req, binaryContent)
		if err != nil {
			msg := fmt.Sprintf("Error creating a new event: %s", err)
			log.Println(msg)
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{ "message": "Internal server error" }`))
		} else {
			m.Handler(w, event)
		}
	})
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
		outputPath = strings.Replace(outputPath, "+", ":" + MuxPathRegex, -1)
	}

	return outputPath
}