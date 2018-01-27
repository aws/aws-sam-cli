package router

import (
	"bytes"
	"encoding/base64"
	"io/ioutil"
	"net/http"
	"net/http/httptest"
	"strings"

	"github.com/awslabs/goformation"
	"github.com/awslabs/goformation/cloudformation"

	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
)

var _ = Describe("ServerlessRouter", func() {
	Context("With a swagger template that has empty mounts", func() {
		It("Mounts the missing function handler", func() {
			template, err := goformation.Open("../test/templates/api-missing-method.yaml")

			Expect(err).To(BeNil())
			Expect(len(template.Resources)).To(Equal(2))
			mux := NewServerlessRouter(false)
			templateApis := template.GetAllAWSServerlessApiResources()

			Expect(len(templateApis)).To(Equal(1))

			for _, api := range templateApis {
				err := mux.AddAPI(&api)
				Expect(err).To(BeNil())
			}

			mounts := mux.Mounts()

			Expect(mounts).ToNot(BeNil())
			Expect(len(mounts)).To(Equal(2))

			req, _ := http.NewRequest("GET", "/badget", nil)
			rr := httptest.NewRecorder()
			mux.Router().ServeHTTP(rr, req)
			Expect(rr.Code).To(Equal(http.StatusBadGateway))
		})
	})

	Context("with SAM template and x-amazon-apigateway-binary-media-types defined in it", func() {
		const input = `{
            "Resources": {
              "MyApi": {
                "Type": "AWS::Serverless::Api",
                "Properties": {
                  "DefinitionBody": {
                    "swagger": "2.0",
                    "paths": {
                      "/post": {
                        "post": {
                          "x-amazon-apigateway-integration": {
                            "httpMethod": "POST",
                            "type": "aws_proxy",
                            "uri": {
                              "Fn::Sub": "arn:aws:apigateway:us-west-2:lambda:path/2015-03-31/functions/dummy/invocations"
                            }
                          },
                          "responses": {}
                        }
                      }
                    },
                    "x-amazon-apigateway-binary-media-types": ["multipart/form-data"]
                  }
                }
              }
            }
          }`
		template, _ := goformation.ParseJSON([]byte(input))

		function := &cloudformation.AWSServerlessFunction{
			Runtime: "nodejs6.10",
			Events: map[string]cloudformation.AWSServerlessFunction_EventSource{
				"PostRequest": {
					Type: "Api",
					Properties: &cloudformation.AWSServerlessFunction_Properties{
						ApiEvent: &cloudformation.AWSServerlessFunction_ApiEvent{
							Path:   "/post",
							Method: "post",
						},
					},
				},
			},
		}
		templateApis := template.GetAllAWSServerlessApiResources()

		It("returns the base64 encoded body on a binary request", func() {
			mux := NewServerlessRouter(false)

			for _, api := range templateApis {
				err := mux.AddAPI(&api)
				Expect(err).To(BeNil())
			}
			data := []byte{'\xe3'}
			req, _ := http.NewRequest("POST", "/post", bytes.NewReader(data))
			req.Header.Add("Content-Type", "multipart/form-data; boundary=something")

			mux.AddFunction(function, func(w http.ResponseWriter, r *http.Request, isBase64Encoded bool) {
				body, err := ioutil.ReadAll(r.Body)
				Expect(err).To(BeNil())
				Expect(string(body)).To(Equal(base64.StdEncoding.EncodeToString(data)))
			})

			rec := httptest.NewRecorder()
			mux.Router().ServeHTTP(rec, req)
		})

		It("returns the text body on a text request", func() {
			mux := NewServerlessRouter(false)

			for _, api := range templateApis {
				err := mux.AddAPI(&api)
				Expect(err).To(BeNil())
			}
			text := "foo"
			req, _ := http.NewRequest("POST", "/post", strings.NewReader(text))
			req.Header.Add("Content-Type", "multipart/form-data; boundary=something")

			mux.AddFunction(function, func(w http.ResponseWriter, r *http.Request, isBase64Encoded bool) {
				body, err := ioutil.ReadAll(r.Body)
				Expect(err).To(BeNil())
				Expect(string(body)).To(Equal(text))
			})

			rec := httptest.NewRecorder()
			mux.Router().ServeHTTP(rec, req)
		})
	})
})
