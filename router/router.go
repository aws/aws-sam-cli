package router

import (
	"errors"
	"net/http"
	"strings"

	"github.com/awslabs/goformation/cloudformation"
	"github.com/gorilla/mux"
	//"github.com/docker/docker/api/types/mount"
)

// ErrNoEventsFound is thrown if a AWS::Serverless::Function is added to this
// router, but no API event sources exist for it.
var ErrNoEventsFound = errors.New("no events with type 'Api' were found")

// ServerlessRouter takes AWS::Serverless::Function and AWS::Serverless::API objects
// and creates a Go http.Handler with the correct paths/methods mounted
type ServerlessRouter struct {
	mux       *mux.Router
	mounts    []*ServerlessRouterMount
	usePrefix bool
}

// NewServerlessRouter creates a new instance of ServerlessRouter.
// If usePrefix is true then route matching is done using prefix instead of exact match
func NewServerlessRouter(usePrefix bool) *ServerlessRouter {
	return &ServerlessRouter{
		mux:       mux.NewRouter(),
		mounts:    []*ServerlessRouterMount{},
		usePrefix: usePrefix,
	}
}

// AddFunction adds a AWS::Serverless::Function to the router and mounts all of it's
// event sources that have type 'Api'
func (r *ServerlessRouter) AddFunction(f *cloudformation.AWSServerlessFunction, handler RequestHandlerFunc) error {

	// Wrap GoFormation's AWS::Serverless::Function definition in our own, which provides
	// convenience methods for extracting the ServerlessRouterMount(s) from it.
	function := &AWSServerlessFunction{f, handler}
	mounts, err := function.Mounts()
	if err != nil {
		return err
	}

	if len(mounts) < 1 {
		return ErrNoEventsFound
	}

	//r.mounts = append(r.mounts, mounts...)
	err = r.mergeMounts(mounts)
	if err != nil {
		return err
	}

	return nil

}

// AddAPI adds a AWS::Serverless::Api resource to the router, and mounts all of it's API definition
func (r *ServerlessRouter) AddAPI(a *cloudformation.AWSServerlessApi) error {

	// Wrap GoFormation's AWS::Serverless::Api definition in our own, which provides
	// convenience methods for extracting the ServerlessRouterMount(s) from it.
	api := &AWSServerlessApi{a}
	mounts, err := api.Mounts()
	if err != nil {
		return err
	}

	//r.mounts = append(r.mounts, mounts...)
	err = r.mergeMounts(mounts)
	if err != nil {
		return err
	}

	return nil
}

// merges the various mount paths. mounts could be coming from a function as well as API
// definition. Mounts defined by an API do not have a handler, only a function ARN.
func (r *ServerlessRouter) mergeMounts(newMounts []*ServerlessRouterMount) error {
	for _, newMount := range newMounts {
		newMountExists := false

		for _, existingMount := range r.mounts {
			if newMount.Path == existingMount.Path && strings.ToLower(newMount.Method) == strings.ToLower(existingMount.Method) {
				newMountExists = true
				// if the new mount has a valid handler I override the existing one anyway
				if newMount.Handler != nil {
					existingMount.Handler = newMount.Handler
					existingMount.Function = newMount.Function
				}
			}
		}

		if !newMountExists {
			if newMount.Handler == nil {
				newMount.Handler = r.missingFunctionHandler()
			}
			r.mounts = append(r.mounts, newMount)
		}
	}
	return nil
}

// AddStaticDir mounts a static directory provided, at the mount point also provided
func (r *ServerlessRouter) AddStaticDir(dirname string) {
	r.mux.NotFoundHandler = http.FileServer(http.Dir(dirname))
}

// Router returns the Go http.Handler for the router, to be passed to http.ListenAndServe()
func (r *ServerlessRouter) Router() http.Handler {

	// Mount all of the things!
	for _, mount := range r.Mounts() {
		r.mux.Handle(mount.GetMuxPath(), mount.WrappedHandler()).Methods(mount.Methods()...)
	}

	return r.mux

}

// Mounts returns a list of the mounts associated with this router
func (r *ServerlessRouter) Mounts() []*ServerlessRouterMount {
	return r.mounts
}

func (r *ServerlessRouter) missingFunctionHandler() func(http.ResponseWriter, *http.Request, bool) {
	return func(w http.ResponseWriter, req *http.Request, isBase64Encoded bool) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadGateway)
		w.Write([]byte(`{ "message": "No function defined for resource method" }`))
	}
}
