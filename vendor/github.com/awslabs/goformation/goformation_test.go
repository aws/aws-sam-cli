package goformation_test

import (
	"github.com/awslabs/goformation"
	. "github.com/awslabs/goformation/resources"
	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
)

var _ = Describe("Goformation", func() {
	Context("with a simple API backend", func() {

		template, _, err := goformation.Open("test-resources/api-backend.yaml")
		It("should successfully parse the template", func() {
			Expect(err).To(BeNil())
			Expect(template).ShouldNot(BeNil())
		})

		It("Should have the proper version", func() {
			Expect(template.Version()).To(Equal("2010-09-09"))
		})

		It("Should have the proper Transform", func() {
			Expect(template.Transform()).To(HaveLen(1))
			Expect(template.Transform()[0]).To(Equal("AWS::Serverless-2016-10-31"))
		})

		It("Should have resources in the parsed template", func() {
			Expect(template.Resources()).To(HaveLen(3))
		})

		It("Should have the resources parameters configured", func() {
			resources := template.Resources()

			Expect(resources["GetFunction"]).ToNot(BeNil())
			Expect(resources["PutFunction"]).ToNot(BeNil())
			Expect(resources["DeleteFunction"]).ToNot(BeNil())

			Expect(resources["GetFunction"].Type()).To(Equal("AWS::Serverless::Function"))
			Expect(resources["PutFunction"].Type()).To(Equal("AWS::Serverless::Function"))
			Expect(resources["DeleteFunction"].Type()).To(Equal("AWS::Serverless::Function"))

			Expect(resources["GetFunction"].Properties()["CodeUri"].Original()).To(Equal("s3://<bucket>/api_backend.zip"))
			Expect(resources["GetFunction"].Properties()["CodeUri"].Value()).To(Equal("s3://<bucket>/api_backend.zip"))
		})

		It("Should have the resourced casted to the proper Class", func() {
			resources := template.Resources()

			getFunctionClass, getFunctionClassOk := resources["GetFunction"].(AWSServerlessFunction)
			Expect(getFunctionClassOk).To(Equal(true))
			Expect(getFunctionClass.Handler()).To(Equal("index.get"))
		})
	})
})
