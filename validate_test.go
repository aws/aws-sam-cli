package main

import (
	"github.com/awslabs/goformation"
	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
	. "github.com/onsi/gomega/gstruct"
)

var _ = Describe("sam", func() {
	Describe("validate", func() {

		Context("with the official AWS SAM example templates", func() {

			inputs := []string{
				"test/templates/sam-official-samples/alexa_skill/template.yaml",
				"test/templates/sam-official-samples/api_backend/template.yaml",
				"test/templates/sam-official-samples/api_swagger_cors/template.yaml",
				"test/templates/sam-official-samples/encryption_proxy/template.yaml",
				"test/templates/sam-official-samples/hello_world/template.yaml",
				"test/templates/sam-official-samples/inline_swagger/template.yaml",
				"test/templates/sam-official-samples/iot_backend/template.yaml",
				"test/templates/sam-official-samples/s3_processor/template.yaml",
				"test/templates/sam-official-samples/schedule/template.yaml",
				"test/templates/sam-official-samples/stream_processor/template.yaml",
			}

			for _, filename := range inputs {
				Context("including "+filename, func() {
					template, err := goformation.Open(filename)
					It("should successfully validate the SAM template", func() {
						Expect(err).To(BeNil())
						Expect(template).ShouldNot(BeNil())
					})
				})
			}

		})

		Context("with the default AWS CodeStar templates", func() {

			inputs := []string{
				"test/templates/codestar/nodejs.yml",
				"test/templates/codestar/python.yml",
				"test/templates/codestar/java.yml",
			}

			for _, filename := range inputs {
				Context("including "+filename, func() {
					template, err := goformation.Open(filename)
					It("should successfully validate the SAM template", func() {
						Expect(err).To(BeNil())
						Expect(template).ShouldNot(BeNil())
					})
				})
			}
		})

		Context("with a Serverless template containing different CodeUri formats", func() {

			template, err := goformation.Open("test/templates/aws-common-string-or-s3-location.yaml")
			It("should successfully parse the template", func() {
				Expect(err).To(BeNil())
				Expect(template).ShouldNot(BeNil())
			})

			functions := template.GetAllAWSServerlessFunctionResources()

			It("should have exactly three functions", func() {
				Expect(functions).To(HaveLen(3))
				Expect(functions).To(HaveKey("CodeUriWithS3LocationSpecifiedAsString"))
				Expect(functions).To(HaveKey("CodeUriWithS3LocationSpecifiedAsObject"))
				Expect(functions).To(HaveKey("CodeUriWithString"))
			})

			f1 := functions["CodeUriWithS3LocationSpecifiedAsString"]
			It("should parse a CodeUri property with an S3 location specified as a string", func() {
				Expect(f1.CodeUri.String).To(PointTo(Equal("s3://testbucket/testkey.zip")))
			})

			f2 := functions["CodeUriWithS3LocationSpecifiedAsObject"]
			It("should parse a CodeUri property with an S3 location specified as an object", func() {
				Expect(f2.CodeUri.S3Location.Bucket).To(Equal("testbucket"))
				Expect(f2.CodeUri.S3Location.Key).To(Equal("testkey.zip"))
				Expect(f2.CodeUri.S3Location.Version).To(Equal(5))
			})

			f3 := functions["CodeUriWithString"]
			It("should parse a CodeUri property with a string", func() {
				Expect(f3.CodeUri.String).To(PointTo(Equal("./testfolder")))
			})

		})

		Context("with a Serverless template containing function environment variables", func() {

			template, err := goformation.Open("test/templates/function-environment-variables.yaml")
			It("should successfully parse the template", func() {
				Expect(err).To(BeNil())
				Expect(template).ShouldNot(BeNil())
			})

			functions := template.GetAllAWSServerlessFunctionResources()

			It("should have exactly one function", func() {
				Expect(functions).To(HaveLen(5))
				Expect(functions).To(HaveKey("EnvironmentVariableTestFunction"))
				Expect(functions).To(HaveKey("IntrinsicEnvironmentVariableTestFunction"))
				Expect(functions).To(HaveKey("NoValueEnvironmentVariableTestFunction"))
				Expect(functions).To(HaveKey("SubEnvironmentVariableTestFunction"))
				Expect(functions).To(HaveKey("NonExistSubEnvironmentVariableTestFunction"))
			})

			f1 := functions["EnvironmentVariableTestFunction"]
			Context("with a simple string based variable", func() {
				It("should have an environment variable named STRING_ENV_VAR", func() {
					Expect(f1.Environment).ToNot(BeNil())
					Expect(f1.Environment.Variables).ToNot(BeNil())
					Expect(f1.Environment.Variables).To(HaveLen(1))
					Expect(f1.Environment.Variables).To(HaveKeyWithValue("STRING_ENV_VAR", "test123"))
				})
			})

			f2 := functions["NoValueEnvironmentVariableTestFunction"]
			Context("with an empty variable value", func() {
				It("should have an environment variable named EMPTY_ENV_VAR", func() {
					Expect(f2.Environment).ToNot(BeNil())
					Expect(f2.Environment.Variables).ToNot(BeNil())
					Expect(f2.Environment.Variables).To(HaveLen(1))
					Expect(f2.Environment.Variables).To(HaveKeyWithValue("EMPTY_ENV_VAR", ""))
				})
			})

			f3 := functions["IntrinsicEnvironmentVariableTestFunction"]
			Context("with a !Ref lookup variable", func() {
				It("should have an environment variable named REF_ENV_VAR", func() {
					Expect(f3.Environment).ToNot(BeNil())
					Expect(f3.Environment.Variables).ToNot(BeNil())
					Expect(f3.Environment.Variables).To(HaveLen(1))
					Expect(f3.Environment.Variables).To(HaveKeyWithValue("REF_ENV_VAR", "SomeValue"))
				})
			})

			f4 := functions["SubEnvironmentVariableTestFunction"]
			Context("with a !Sub variable value", func() {
				It("should have an environment variable named SUB_ENV_VAR", func() {
					Expect(f4.Environment).ToNot(BeNil())
					Expect(f4.Environment.Variables).ToNot(BeNil())
					Expect(f4.Environment.Variables).To(HaveLen(1))
					Expect(f4.Environment.Variables).To(HaveKeyWithValue("SUB_ENV_VAR", "Hello"))
				})
			})

			f5 := functions["NonExistSubEnvironmentVariableTestFunction"]
			Context("with a !Sub variable value that contains a non-existant reference", func() {
				It("should have an environment variable named SUB_REF_ENV_VAR", func() {
					Expect(f5.Environment).ToNot(BeNil())
					Expect(f5.Environment.Variables).ToNot(BeNil())
					Expect(f5.Environment.Variables).To(HaveLen(1))
					Expect(f5.Environment.Variables).To(HaveKeyWithValue("SUB_REF_ENV_VAR", "Hello-"))
				})
			})

		})

		Context("with a Serverless function matching 2016-10-31 specification", func() {

			template, err := goformation.Open("test/templates/function-2016-10-31.yaml")
			It("should successfully validate the SAM template", func() {
				Expect(err).To(BeNil())
				Expect(template).ShouldNot(BeNil())
			})

			functions := template.GetAllAWSServerlessFunctionResources()

			It("should have exactly one function", func() {
				Expect(functions).To(HaveLen(1))
				Expect(functions).To(HaveKey("Function20161031"))
			})

			f := functions["Function20161031"]

			It("should correctly parse all of the function properties", func() {

				Expect(f.Handler).To(Equal("file.method"))
				Expect(f.Runtime).To(Equal("nodejs"))
				Expect(f.FunctionName).To(Equal("functionname"))
				Expect(f.Description).To(Equal("description"))
				Expect(f.MemorySize).To(Equal(128))
				Expect(f.Timeout).To(Equal(30))
				Expect(f.Role).To(Equal("aws::arn::123456789012::some/role"))
				Expect(f.Policies.StringArray).To(PointTo(ContainElement("AmazonDynamoDBFullAccess")))
				Expect(f.Environment).ToNot(BeNil())
				Expect(f.Environment.Variables).To(HaveKeyWithValue("NAME", "VALUE"))

			})

			It("should correctly parse all of the function API event sources/endpoints", func() {

				Expect(f.Events).ToNot(BeNil())
				Expect(f.Events).To(HaveKey("TestApi"))
				Expect(f.Events["TestApi"].Type).To(Equal("Api"))
				Expect(f.Events["TestApi"].Properties.ApiEvent).ToNot(BeNil())

				event := f.Events["TestApi"].Properties.ApiEvent
				Expect(event.Method).To(Equal("any"))
				Expect(event.Path).To(Equal("/testing"))

			})

		})

		Context("with non-resource sections in CloudFormation template", func() {

			inputs := []string{
				"test/templates/output_section.yaml",
			}

			for _, filename := range inputs {
				Context("including "+filename, func() {
					template, err := goformation.Open(filename)
					It("should successfully validate the SAM template", func() {
						Expect(err).To(BeNil())
						Expect(template).ShouldNot(BeNil())
					})
				})
			}

		})

	})
})
