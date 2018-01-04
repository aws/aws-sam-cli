package router

import (
	"net/http"
	"net/http/httptest"

	"github.com/awslabs/goformation"

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
})
