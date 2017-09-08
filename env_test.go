package main

import (
	"os"

	"github.com/awslabs/goformation"
	"github.com/awslabs/goformation/cloudformation"

	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
)

var _ = Describe("Environment Variables", func() {

	Context("with a template that has environment variables defined", func() {

		var functions map[string]cloudformation.AWSServerlessFunction
		BeforeEach(func() {
			template, _ := goformation.Open("test/templates/sam-official-samples/iot_backend/template.yaml")
			functions = template.GetAllAWSServerlessFunctionResources()
		})

		It("return defaults with those defined in the template", func() {

			for name, function := range functions {
				variables := getEnvironmentVariables(name, &function, "")
				Expect(variables).To(HaveLen(10))
				Expect(variables).To(HaveKey("AWS_SAM_LOCAL"))
				Expect(variables).To(HaveKey("AWS_REGION"))
				Expect(variables).To(HaveKey("AWS_DEFAULT_REGION"))
				Expect(variables).To(HaveKey("AWS_ACCESS_KEY_ID"))
				Expect(variables).To(HaveKey("AWS_SECRET_ACCESS_KEY"))
				Expect(variables).To(HaveKey("AWS_SESSION_TOKEN"))
				Expect(variables).To(HaveKey("AWS_LAMBDA_FUNCTION_MEMORY_SIZE"))
				Expect(variables).To(HaveKey("AWS_LAMBDA_FUNCTION_TIMEOUT"))
				Expect(variables).To(HaveKey("AWS_LAMBDA_FUNCTION_HANDLER"))
				Expect(variables).To(HaveKey("TABLE_NAME"))
			}
		})

		It("overides template with environment variables", func() {
			for name, function := range functions {
				variables := getEnvironmentVariables(name, &function, "")
				Expect(variables["TABLE_NAME"]).To(Equal(""))

				os.Setenv("TABLE_NAME", "ENV_TABLE")
				variables = getEnvironmentVariables(name, &function, "")
				Expect(variables["TABLE_NAME"]).To(Equal("ENV_TABLE"))
				os.Unsetenv("TABLE_NAME")
			}
		})

		It("overrides template and environment with customer overrides", func() {
			for name, function := range functions {
				variables := getEnvironmentVariables(name, &function, "test/environment-overrides.json")
				Expect(variables["TABLE_NAME"]).To(Equal("OVERRIDE_TABLE"))
			}
			os.Unsetenv("TABLE_NAME")
		})

	})
})
