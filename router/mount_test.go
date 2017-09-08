package router_test

import (
	. "github.com/awslabs/aws-sam-local/router"

	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
)

var _ = Describe("ServerlessRouterMount", func() {

	Context("with a method in uppercase", func() {

		m := ServerlessRouterMount{
			Path:   "/test",
			Method: "GET",
		}

		methods := m.Methods()
		It("should have the correct HTTP method", func() {
			Expect(methods).To(HaveLen(1))
			Expect(methods).To(ContainElement("GET"))
		})

	})

	Context("with a method in lowercase", func() {

		m := ServerlessRouterMount{
			Path:   "/test",
			Method: "get",
		}

		methods := m.Methods()
		It("should have the correct HTTP method", func() {
			Expect(methods).To(HaveLen(1))
			Expect(methods).To(ContainElement("GET"))
		})

	})

	Context("with method 'any'", func() {

		m := ServerlessRouterMount{
			Path:   "/test",
			Method: "any",
		}

		methods := m.Methods()
		It("should have the correct HTTP method", func() {
			Expect(methods).To(HaveLen(8))
			Expect(methods).To(ContainElement("OPTIONS"))
			Expect(methods).To(ContainElement("GET"))
			Expect(methods).To(ContainElement("HEAD"))
			Expect(methods).To(ContainElement("POST"))
			Expect(methods).To(ContainElement("PUT"))
			Expect(methods).To(ContainElement("DELETE"))
			Expect(methods).To(ContainElement("TRACE"))
			Expect(methods).To(ContainElement("CONNECT"))
		})

	})

})
