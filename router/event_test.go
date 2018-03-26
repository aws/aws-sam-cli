package router

import (
	"bytes"
	"net/http"
	"net/http/httptest"

	"github.com/awslabs/goformation/cloudformation"

	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
)

var _ = Describe("Event", func() {
	Describe("PathParameters", func() {
		var r *ServerlessRouter
		BeforeEach(func() {
			r = NewServerlessRouter(false)
		})

		Context("with path parameters on the route", func() {
			function := &cloudformation.AWSServerlessFunction{
				Runtime: "nodejs6.10",
				Events: map[string]cloudformation.AWSServerlessFunction_EventSource{
					"GetRequest": cloudformation.AWSServerlessFunction_EventSource{
						Type: "Api",
						Properties: &cloudformation.AWSServerlessFunction_Properties{
							ApiEvent: &cloudformation.AWSServerlessFunction_ApiEvent{
								Path:   "/get",
								Method: "get",
							},
						},
					},
					"GetRequestsWithParams": cloudformation.AWSServerlessFunction_EventSource{
						Type: "Api",
						Properties: &cloudformation.AWSServerlessFunction_Properties{
							ApiEvent: &cloudformation.AWSServerlessFunction_ApiEvent{
								Path:   "/get/{parameter}",
								Method: "get",
							},
						},
					},
				},
			}

			Context("and path parameters on the request", func() {
				req, _ := http.NewRequest("GET", "/get/1", new(bytes.Buffer))

				It("returns the parameters on the event", func() {
					r.AddFunction(function, func(w http.ResponseWriter, e *Event) {
						Expect(e.PathParameters).To(HaveKeyWithValue("parameter", "1"))
					})

					rec := httptest.NewRecorder()
					r.Router().ServeHTTP(rec, req)
				})
			})

			Context("and path parameters on the request", func() {
				req, _ := http.NewRequest("GET", "/get/1", new(bytes.Buffer))

				It("returns stage property with value \"prod\"", func() {
					r.AddFunction(function, func(w http.ResponseWriter, e *Event) {
						Expect(e.RequestContext.Stage).To(BeIdenticalTo("prod"))
					})

					rec := httptest.NewRecorder()
					r.Router().ServeHTTP(rec, req)
				})
			})

			Context("and no path parameters on the request", func() {
				req, _ := http.NewRequest("GET", "/get", new(bytes.Buffer))

				It("returns nil for PathParameters on the event", func() {
					r.AddFunction(function, func(w http.ResponseWriter, e *Event) {
						Expect(e.PathParameters).To(BeNil())
					})

					rec := httptest.NewRecorder()
					r.Router().ServeHTTP(rec, req)
				})
			})

			Context("Includes forwarded headers", func() {
				req, _ := http.NewRequest("GET", "http://localhost:3000/get", new(bytes.Buffer))

				It("Includes Host header", func() {
					r.AddFunction(function, func(w http.ResponseWriter, e *Event) {
						hostHeader, ok := e.Headers["Host"]
						Expect(ok).To(BeTrue())
						Expect(hostHeader).To(BeIdenticalTo("localhost"))
					})
					rec := httptest.NewRecorder()
					r.Router().ServeHTTP(rec, req)
				})

				It("Includes X-Forwarded-Proto header", func() {
					r.AddFunction(function, func(w http.ResponseWriter, e *Event) {
						hostHeader, ok := e.Headers["X-Forwarded-Proto"]
						Expect(ok).To(BeTrue())
						Expect(hostHeader).To(BeIdenticalTo("http"))
					})
					rec := httptest.NewRecorder()
					r.Router().ServeHTTP(rec, req)
				})

				It("Includes X-Forwarded-Port header", func() {
					r.AddFunction(function, func(w http.ResponseWriter, e *Event) {
						hostHeader, ok := e.Headers["X-Forwarded-Port"]
						Expect(ok).To(BeTrue())
						Expect(hostHeader).To(BeIdenticalTo("3000"))
					})
					rec := httptest.NewRecorder()
					r.Router().ServeHTTP(rec, req)
				})
			})
		})

		Context("with no parameters on the route", func() {
			function := &cloudformation.AWSServerlessFunction{
				Runtime: "nodejs6.10",
				Events: map[string]cloudformation.AWSServerlessFunction_EventSource{
					"GetRequest": cloudformation.AWSServerlessFunction_EventSource{
						Type: "Api",
						Properties: &cloudformation.AWSServerlessFunction_Properties{
							ApiEvent: &cloudformation.AWSServerlessFunction_ApiEvent{
								Path:   "/get",
								Method: "get",
							},
						},
					},
				},
			}

			req, _ := http.NewRequest("GET", "/get", new(bytes.Buffer))

			It("returns nil for PathParameters on the event", func() {
				r.AddFunction(function, func(w http.ResponseWriter, e *Event) {
					Expect(e.PathParameters).To(BeNil())
				})

				rec := httptest.NewRecorder()
				r.Router().ServeHTTP(rec, req)
			})
		})
	})
})
