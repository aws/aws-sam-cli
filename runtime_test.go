package main

import (
  "os"
  "github.com/awslabs/goformation"
  "github.com/awslabs/goformation/resources"
  . "github.com/onsi/ginkgo"
  . "github.com/onsi/gomega"
)

var _ = Describe("sam", func() {
  Describe("runtime", func() {

    var functions map[string]resources.Resource

    Context("environment variables", func() {

      BeforeEach(func() {
        template, _, _ := goformation.Open("test/templates/sam-official-samples/iot_backend/template.yaml")
        functions = template.GetResourcesByType("AWS::Serverless::Function")
      })

      It("return defaults with those defined in the template", func() {

        for _, resource := range functions {
          function := resource.(resources.AWSServerlessFunction)
          variables := getEnvironmentVariables(function, map[string]string{})
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
        for _, resource := range functions {
          function := resource.(resources.AWSServerlessFunction)
          variables := getEnvironmentVariables(function, map[string]string{})
          Expect(variables["TABLE_NAME"]).To(Equal(""))

          os.Setenv("TABLE_NAME", "ENV_TABLE")
          variables = getEnvironmentVariables(function, map[string]string{})
          Expect(variables["TABLE_NAME"]).To(Equal("ENV_TABLE"))
          os.Unsetenv("TABLE_NAME")
        }
      })

      It("overrides template and environment with customer overrides", func() {
        os.Setenv("TABLE_NAME", "ENV_TABLE")
        overrides := map[string]string{
          "TABLE_NAME": "OVERRIDE_TABLE",
        }

        for _, resource := range functions {
          function := resource.(resources.AWSServerlessFunction)
          variables := getEnvironmentVariables(function, overrides)
          Expect(variables["TABLE_NAME"]).To(Equal("OVERRIDE_TABLE"))
        }
        os.Unsetenv("TABLE_NAME")
      })

    })

  })
})
