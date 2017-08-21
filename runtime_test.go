package main

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

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

	})
})
