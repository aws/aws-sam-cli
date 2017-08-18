package intrinsics_test

import (
	"encoding/json"

	. "github.com/awslabs/goformation/intrinsics"

	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
)

var _ = Describe("AWS CloudFormation intrinsic function processing", func() {

	Context("with a template that contains invalid JSON", func() {
		const template = `{`
		processed, err := Process([]byte(template), nil)
		It("should fail to process the template", func() {
			Expect(processed).To(BeNil())
			Expect(err).ToNot(BeNil())
		})
	})

	Context("with a template that contains primitives, intrinsics, and nested intrinsics", func() {

		const template = `{
			"Resources": {
				"ExampleResource": {
					"Type": "AWS::Example::Resource",
					"Properties": {
						"StringProperty": "Simple string example",						
						"BooleanProperty": true,
						"NumberProperty": 123.45,
						"JoinIntrinsicProperty": { "Fn::Join": [ "some", "name" ] },				
						"JoinNestedIntrinsicProperty": { "Fn::Join": [ "some", { "Fn::Join": [ "joined", "value" ] } ] },
						"SubIntrinsicProperty": { "Fn::Sub": [ "some ${value}", { "value": "value" } ] }			
					}
				}
			}
		}`

		Context("with no processor options", func() {

			processed, err := Process([]byte(template), nil)
			It("should successfully process the template", func() {
				Expect(processed).ShouldNot(BeNil())
				Expect(err).Should(BeNil())
			})

			var result interface{}
			err = json.Unmarshal(processed, &result)

			It("should be valid JSON, and marshal to a Go type", func() {
				Expect(processed).ToNot(BeNil())
				Expect(err).To(BeNil())
			})

			template := result.(map[string]interface{})
			resources := template["Resources"].(map[string]interface{})
			resource := resources["ExampleResource"].(map[string]interface{})
			properties := resource["Properties"].(map[string]interface{})

			It("should have the correct value for a primitive string property", func() {
				Expect(properties["StringProperty"]).To(Equal("Simple string example"))
			})

			It("should have the correct value for a primitive boolean property", func() {
				Expect(properties["BooleanProperty"]).To(Equal(true))
			})

			It("should have the correct value for a primitive number property", func() {
				Expect(properties["NumberProperty"]).To(Equal(123.45))
			})

			It("should have the correct value for a Fn::Join intrinsic property", func() {
				Expect(properties["JoinIntrinsicProperty"]).To(Equal("Fn::Join intrinsic function is unsupported"))
			})

			It("should have the correct value for a nested Fn::Join intrinsic property", func() {
				Expect(properties["JoinNestedIntrinsicProperty"]).To(Equal("Fn::Join intrinsic function is unsupported"))
			})

			It("should have the correct value for a Fn::Sub intrinsic property", func() {
				Expect(properties["SubIntrinsicProperty"]).To(Equal("Fn::Sub intrinsic function is unsupported"))
			})

		})

		Context("with a processor options override for the Fn::Join function", func() {

			opts := &ProcessorOptions{
				IntrinsicHandlerOverrides: map[string]IntrinsicHandler{
					"Fn::Join": func(name string, input interface{}) interface{} {
						return "overridden"
					},
				},
			}

			processed, err := Process([]byte(template), opts)
			It("should successfully process the template", func() {
				Expect(processed).ShouldNot(BeNil())
				Expect(err).Should(BeNil())
			})

			result := map[string]interface{}{}
			err = json.Unmarshal(processed, &result)

			It("should be valid JSON, and marshal to a Go type", func() {
				Expect(processed).ToNot(BeNil())
				Expect(err).To(BeNil())
			})

			resources := result["Resources"].(map[string]interface{})
			resource := resources["ExampleResource"].(map[string]interface{})
			properties := resource["Properties"].(map[string]interface{})

			It("should have the correct value for a primitive string property", func() {
				Expect(properties["StringProperty"]).To(Equal("Simple string example"))
			})

			It("should have the correct value for a primitive boolean property", func() {
				Expect(properties["BooleanProperty"]).To(Equal(true))
			})

			It("should have the correct value for a primitive number property", func() {
				Expect(properties["NumberProperty"]).To(Equal(123.45))
			})

			It("should have the correct value for an intrinsic property", func() {
				Expect(properties["JoinIntrinsicProperty"]).To(Equal("overridden"))
			})

			It("should have the correct value for a nested intrinsic property", func() {
				Expect(properties["JoinNestedIntrinsicProperty"]).To(Equal("overridden"))
			})

			It("should have the correct value for an intrinsic property that's not supposed to be overridden", func() {
				Expect(properties["SubIntrinsicProperty"]).To(Equal("Fn::Sub intrinsic function is unsupported"))
			})

		})

	})
})
