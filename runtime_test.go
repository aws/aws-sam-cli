package main

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"sync"

	. "github.com/onsi/ginkgo"
	. "github.com/onsi/gomega"
)

var _ = Describe("sam", func() {

	Describe("runtime", func() {

		Context("mount directory", func() {
			Context("with a windows style path", func() {
				input := `C:/Users/username/path`
				It("should replace it with the docker-toolbox format", func() {
					result := convertWindowsPath(input)
					Expect(result).To(Equal("/c/Users/username/path"))
				})
			})
		})

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

		Context("parse output", func() {
			var wg sync.WaitGroup
			var out []byte
			var r *fakeResponse

			inputs := []struct {
				name     string
				output   io.Reader
				body     []byte
				status   int
				headers  http.Header
				trailing string
			}{
				{
					name:    "only proxy response",
					output:  strings.NewReader(`{"statusCode":202,"headers":{"foo":"bar"},"body":"{\"nextToken\":null,\"beers\":[]}","base64Encoded":false}`),
					body:    []byte(`{"nextToken":null,"beers":[]}`),
					status:  202,
					headers: http.Header(map[string][]string{"foo": []string{"bar"}}),
				},
				{
					name: "proxy response with extra output",
					output: strings.NewReader(`Foo
					Bar
					{"statusCode":200,"headers":null,"body":"{\"nextToken\":null,\"beers\":[]}","base64Encoded":false}`),
					body:    []byte(`{"nextToken":null,"beers":[]}`),
					status:  200,
					headers: make(http.Header),
					trailing: `Foo
					Bar`,
				},
				{
					name:    "no output",
					output:  strings.NewReader(``),
					body:    []byte(`{ "message": "Internal server error" }`),
					status:  502,
					headers: make(http.Header),
				},
				{
					name:    "bad status code",
					output:  strings.NewReader(`{"statusCode":"xxx","headers":null,"body":"{\"nextToken\":null,\"beers\":[]}","base64Encoded":false}`),
					body:    []byte(`{"nextToken":null,"beers":[]}`),
					status:  502,
					headers: make(http.Header),
				},
				{
					name:    "io error",
					output:  &errReader{},
					body:    []byte(`{ "message": "Internal server error" }`),
					status:  500,
					headers: make(http.Header),
				},
			}

			for _, input := range inputs {

				Context(input.name, func() {
					wg.Add(1)
					r = newResponse()
					out = parseOutput(r, input.output, "foo", &wg)

					It("should have the expected output", func() {
						Expect(r.status).To(Equal(input.status))
						Expect(r.body).To(Equal(input.body))
						Expect(r.headers).To(Equal(input.headers))
						Expect(string(out)).To(Equal(input.trailing))
					})

				})

			}

		})

	})
})

type errReader struct{}

func (r *errReader) Read(p []byte) (int, error) {
	return 0, io.ErrUnexpectedEOF
}

type fakeResponse struct {
	headers http.Header
	body    []byte
	status  int
}

func newResponse() *fakeResponse {
	return &fakeResponse{
		headers: make(http.Header),
	}
}

func (r *fakeResponse) Header() http.Header {
	return r.headers
}

func (r *fakeResponse) Write(body []byte) (int, error) {
	r.body = body
	return len(body), nil
}

func (r *fakeResponse) WriteHeader(status int) {
	r.status = status
}
