package main

import (
	"fmt"
	"os"

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

			inputs := [][]string{
				// input path, output path
				[]string{"", cwd},
				[]string{".", cwd},
				[]string{"/test/directory", "/test/directory"},
				[]string{"test/directory", "test/directory"},
			}

			// func getWorkingDir(basedir string, codeuri string, checkWorkingDirExist bool) (string, error) {
			for _, input := range inputs {

				in := input[0]
				expected := input[1]

				context := fmt.Sprintf("with input %s", in)
				Context(context, func() {
					It("should have the correct directory", func() {
						dir := getWorkingDir(in)
						Expect(dir).To(Equal(expected))
					})
				})

			}

		})

	})
})
