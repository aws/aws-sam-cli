package router

import (
	"github.com/awslabs/goformation/cloudformation"
)

// AWSServerlessFunction wraps GoFormation's AWS::Serverless::Function definition
// and adds some convenience methods for extracting the ServerlessRouterMount's
// from the event sources.
type AWSServerlessFunction struct {
	*cloudformation.AWSServerlessFunction
	handler EventHandlerFunc
}

// Mounts fetches an array of the ServerlessRouterMount's for this API.
// These contain the path, method and handler function for each mount point.
func (f *AWSServerlessFunction) Mounts() ([]*ServerlessRouterMount, error) {

	mounts := []*ServerlessRouterMount{}

	for name, event := range f.Events {
		if event.Type == "Api" {
			if event.Properties != nil && event.Properties.ApiEvent != nil {
				mounts = append(mounts, &ServerlessRouterMount{
					Name:      name,
					Path:      event.Properties.ApiEvent.Path,
					Method:    event.Properties.ApiEvent.Method,
					Handler:   f.handler,
					Function:  f,
				})
			}
		}
	}

	return mounts, nil

}
