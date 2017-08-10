package goformation_test

import (
	"github.com/awslabs/goformation"
	. "github.com/awslabs/goformation/resources"
	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
)

var _ = Describe("Sam", func() {

	Describe("Parse", func() {

		Context("with a Serverless function matching 2016-10-31 specification", func() {

			template, _, err := goformation.Open("test-resources/sam/function.yaml")
			It("should successfully parse the SAM template", func() {
				Expect(err).To(BeNil())
				Expect(template).ShouldNot(BeNil())
			})

			var f AWSServerlessFunction
			for _, fn := range template.GetResourcesByType("AWS::Serverless::Function") {
				f = fn.(AWSServerlessFunction)
			}

			It("should have exactly one function", func() {
				Expect(template.GetResourcesByType("AWS::Serverless::Function")).To(HaveLen(1))
			})

			It("should correctly parse all of the function properties", func() {

				Expect(f.Handler()).To(Equal("file.method"))
				Expect(f.Runtime()).To(Equal("nodejs"))
				Expect(f.FunctionName()).To(Equal("functionname"))
				Expect(f.Description()).To(Equal("description"))
				Expect(f.MemorySize()).To(Equal(128))
				Expect(f.Timeout()).To(Equal(30))
				Expect(f.Role()).To(Equal("aws::arn::123456789012::some/role"))
				Expect(f.Policies()).To(ContainElement("AmazonDynamoDBFullAccess"))
				Expect(f.EnvironmentVariables()).To(HaveKeyWithValue("NAME", "VALUE"))

			})

			It("should correctly parse all of the function API event sources/endpoints", func() {

				endpoints, err := f.Endpoints()
				Expect(err).To(BeNil())

				Expect(endpoints).To(HaveLen(1))

				firstEndpoint := endpoints[0]
				Expect(firstEndpoint.Methods()).To(Equal([]string{"OPTIONS", "GET", "HEAD", "POST", "PUT", "DELETE", "TRACE", "CONNECT"}))
				Expect(firstEndpoint.Path()).To(Equal("/testing"))

			})

		})

		Context("with a template that includes intrinsic functions", func() {

			template, _, err := goformation.Open("test-resources/sam/api-swagger-intrinsic.yaml")
			It("should successfully parse the SAM template", func() {
				Expect(err).To(BeNil())
				Expect(template).ShouldNot(BeNil())
			})

			It("should have exactly three function", func() {
				Expect(template.GetResourcesByType("AWS::Serverless::Function")).To(HaveLen(3))
			})
		})

		Context("with the default CodeStar NodeJS 4.3 Serverless application template", func() {

			template, _, err := goformation.Open("test-resources/sam/codestar-node4.3.yaml")
			It("should successfully parse the SAM template", func() {
				Expect(err).To(BeNil())
				Expect(template).ShouldNot(BeNil())
			})

			It("should have exactly one function", func() {
				Expect(template.GetResourcesByType("AWS::Serverless::Function")).To(HaveLen(1))
			})

		})

		Context("with a Serverless template containing different CodeUri formats", func() {

			template, _, err := goformation.Open("test-resources/aws-common-string-or-s3-location.yaml")
			It("should successfully parse the template", func() {
				Expect(err).To(BeNil())
				Expect(template).ShouldNot(BeNil())
			})

			functions := template.GetResourcesByType("AWS::Serverless::Function")

			It("should have exactly three functions", func() {
				Expect(functions).To(HaveLen(3))
				Expect(functions).To(HaveKey("CodeUriWithS3LocationSpecifiedAsString"))
				Expect(functions).To(HaveKey("CodeUriWithS3LocationSpecifiedAsObject"))
				Expect(functions).To(HaveKey("CodeUriWithString"))
			})

			f1 := functions["CodeUriWithS3LocationSpecifiedAsString"].(AWSServerlessFunction)
			It("should parse a CodeUri property with an S3 location specified as a string", func() {
				Expect(f1.CodeURI().String()).To(Equal("s3://testbucket/testkey.zip"))
			})

			f2 := functions["CodeUriWithS3LocationSpecifiedAsObject"].(AWSServerlessFunction)
			It("should parse a CodeUri property with an S3 location specified as an object", func() {
				Expect(f2.CodeURI().String()).To(Equal("s3://testbucket/testkey.zip#5"))
			})

			f3 := functions["CodeUriWithString"].(AWSServerlessFunction)
			It("should parse a CodeUri property with a string", func() {
				Expect(f3.CodeURI().String()).To(Equal("./testfolder"))
			})

		})

		Context("with a Serverless template containing function environment variables", func() {

			template, _, err := goformation.Open("test-resources/function-environment-variables.yaml")
			It("should successfully parse the template", func() {
				Expect(err).To(BeNil())
				Expect(template).ShouldNot(BeNil())
			})

			functions := template.GetResourcesByType("AWS::Serverless::Function")

			It("should have exactly one function", func() {
				Expect(functions).To(HaveLen(5))
				Expect(functions).To(HaveKey("EnvironmentVariableTestFunction"))
				Expect(functions).To(HaveKey("IntrinsicEnvironmentVariableTestFunction"))
				Expect(functions).To(HaveKey("NoValueEnvironmentVariableTestFunction"))
				Expect(functions).To(HaveKey("SubEnvironmentVariableTestFunction"))
				Expect(functions).To(HaveKey("NonExistSubEnvironmentVariableTestFunction"))
			})

			f1 := functions["EnvironmentVariableTestFunction"].(AWSServerlessFunction)
			Context("with a simple string based variable", func() {
				It("should have an environment variable named STRING_ENV_VAR", func() {
					Expect(f1.EnvironmentVariables()).To(HaveLen(1))
					Expect(f1.EnvironmentVariables()).To(HaveKeyWithValue("STRING_ENV_VAR", "test123"))
				})
			})

			f2 := functions["NoValueEnvironmentVariableTestFunction"].(AWSServerlessFunction)
			Context("with an empty variable value", func() {
				It("should have an environment variable named EMPTY_ENV_VAR", func() {
					Expect(f2.EnvironmentVariables()).To(HaveLen(1))
					Expect(f2.EnvironmentVariables()).To(HaveKeyWithValue("EMPTY_ENV_VAR", ""))
				})
			})

			f3 := functions["IntrinsicEnvironmentVariableTestFunction"].(AWSServerlessFunction)
			Context("with a !Ref lookup variable", func() {
				It("should have an environment variable named REF_ENV_VAR", func() {
					Expect(f3.EnvironmentVariables()).To(HaveLen(1))
					Expect(f3.EnvironmentVariables()).To(HaveKeyWithValue("REF_ENV_VAR", ""))
				})
			})

			f4 := functions["SubEnvironmentVariableTestFunction"].(AWSServerlessFunction)
			Context("with a !Sub variable value", func() {
				It("should have an environment variable named SUB_ENV_VAR", func() {
					Expect(f4.EnvironmentVariables()).To(HaveLen(1))
					Expect(f4.EnvironmentVariables()).To(HaveKeyWithValue("SUB_ENV_VAR", "Hello"))
				})
			})

			f5 := functions["NonExistSubEnvironmentVariableTestFunction"].(AWSServerlessFunction)
			Context("with a !Sub variable value that contains a non-existant reference", func() {
				It("should have an environment variable named SUB_REF_ENV_VAR", func() {
					Expect(f5.EnvironmentVariables()).To(HaveLen(1))
					Expect(f5.EnvironmentVariables()).To(HaveKeyWithValue("SUB_REF_ENV_VAR", "Hello-"))
				})
			})

		})

		Context("with the official AWS SAM example templates", func() {

			inputs := []string{
				"test-resources/sam/alexa_skill/template.yaml",
				"test-resources/sam/api_backend/template.yaml",
				"test-resources/sam/api_swagger_cors/template.yaml",
				"test-resources/sam/encryption_proxy/template.yaml",
				"test-resources/sam/hello_world/template.yaml",
				"test-resources/sam/inline_swagger/template.yaml",
				"test-resources/sam/iot_backend/template.yaml",
				"test-resources/sam/s3_processor/template.yaml",
				"test-resources/sam/schedule/template.yaml",
				"test-resources/sam/stream_processor/template.yaml",
			}

			for _, filename := range inputs {

				Context("including "+filename, func() {
					template, _, err := goformation.Open(filename)
					It("should successfully parse the SAM template", func() {
						Expect(err).To(BeNil())
						Expect(template).ShouldNot(BeNil())
					})
				})

			}

		})

	})

})
