package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/awslabs/goformation"
	"github.com/awslabs/goformation/cloudformation"
	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
)

var _ = Describe("sam", func() {

	Describe("runtime", func() {

		Context("working directory", func() {

			cwd, err := os.Getwd()
			It("should determin the current working directory", func() {
				Expect(cwd).ToNot(BeNil())
				Expect(err).To(BeNil())
			})

			baseDir := "/" + strings.Trim(os.TempDir(), "/")
			baseDirNonExistent := "/yeHNpGawFr0SJ9RZae6mWJKrqvfjaNbJgOM3oQhAQQif6e1Dpbra"
			baseDirEmpty := ""

			codeUri := "./test"
			codeUriUnknown := "s3://<bucket>/packaged.zip"
			codeUriEmpty := ""
			os.Mkdir(filepath.Join(baseDir, codeUri), 0755)

			inputs := [][]string{
				// basedir, CodeUri, checkWorkingDir, expected result
				[]string{baseDir, codeUri, "true", filepath.Join(baseDir, codeUri)},
				[]string{baseDirNonExistent, codeUri, "true", baseDirNonExistent},
				[]string{baseDirEmpty, codeUri, "true", filepath.Join(cwd, codeUri)},
				[]string{baseDir, codeUriUnknown, "true", baseDir},
				[]string{baseDirNonExistent, codeUriUnknown, "true", baseDirNonExistent},
				[]string{baseDirEmpty, codeUriUnknown, "true", cwd},
				[]string{baseDir, codeUriEmpty, "true", baseDir},
				[]string{baseDirNonExistent, codeUriEmpty, "true", baseDirNonExistent},
				[]string{baseDirEmpty, codeUriEmpty, "true", cwd},

				// getWorkingDir=false is used when SAM Local runs locally, but the Docker container
				// is on a remote host. The base path / CodeUri might not resolve locally.
				[]string{baseDir, codeUri, "false", filepath.Join(baseDir, codeUri)},
				[]string{baseDirNonExistent, codeUri, "false", filepath.Join(baseDirNonExistent, codeUri)},
				[]string{baseDirEmpty, codeUri, "false", filepath.Join(cwd, codeUri)},
				[]string{baseDir, codeUriUnknown, "false", filepath.Join(baseDir, codeUriUnknown)},
				[]string{baseDirNonExistent, codeUriUnknown, "false", filepath.Join(baseDirNonExistent, codeUriUnknown)},
				[]string{baseDirEmpty, codeUriUnknown, "false", filepath.Join(cwd, codeUriUnknown)},
				[]string{baseDir, codeUriEmpty, "false", baseDir},
				[]string{baseDirNonExistent, codeUriEmpty, "false", baseDirNonExistent},
				[]string{baseDirEmpty, codeUriEmpty, "false", cwd},
			}

			// func getWorkingDir(basedir string, codeuri string, checkWorkingDirExist bool) (string, error) {
			for _, input := range inputs {

				basedir := input[0]
				codeuri := input[1]
				check, _ := strconv.ParseBool(input[2])
				expected := input[3]

				context := fmt.Sprintf("with basedir=%s, CodeUri=%s and checkWorkingDirExists=%t", basedir, codeuri, check)
				Context(context, func() {
					It("should have the correct directory", func() {
						dir, err := getWorkingDir(basedir, codeuri, check)
						Expect(err).To(BeNil())
						Expect(dir).To(Equal(expected))
					})
				})

			}

		})

		Context("environment variables", func() {

			var functions map[string]cloudformation.AWSServerlessFunction
			BeforeEach(func() {
				template, _ := goformation.Open("test/templates/sam-official-samples/iot_backend/template.yaml")
				functions = template.GetAllAWSServerlessFunctionResources()
			})

			It("return defaults with those defined in the template", func() {

				for _, function := range functions {
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
				for _, function := range functions {
					variables := getEnvironmentVariables(function, map[string]string{})
					Expect(variables["TABLE_NAME"]).To(Equal("Table"))

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

				for _, function := range functions {
					variables := getEnvironmentVariables(function, overrides)
					Expect(variables["TABLE_NAME"]).To(Equal("OVERRIDE_TABLE"))
				}
				os.Unsetenv("TABLE_NAME")
			})

		})

	})
})
