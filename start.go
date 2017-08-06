package main

import (
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sync"

	"github.com/awslabs/goformation"
	"github.com/awslabs/goformation/resources"
	"github.com/codegangsta/cli"
	"github.com/gorilla/mux"
)

type mount struct {
	Handler  string
	Runtime  string
	Endpoint string
	Methods  []string
}

func start(c *cli.Context) {

	// Setup the logger
	stderr := io.Writer(os.Stderr)
	logarg := c.String("log")

	if len(logarg) > 0 {
		if logFile, err := os.Create(logarg); err == nil {
			stderr = io.Writer(logFile)
			log.SetOutput(stderr)
		} else {
			log.Fatalf("Failed to open log file %s: %s\n", c.String("log"), err)
		}
	}

	template, _, errs := goformation.Open(c.String("template"))
	if len(errs) > 0 {
		for _, err := range errs {
			log.Printf("%s\n", err)
		}
		os.Exit(1)
	}

	// Check connectivity to docker
	dockerVersion, err := getDockerVersion()
	if err != nil {
		log.Printf("Running AWS SAM projects locally requires Docker. Have you got it installed?\n")
		log.Printf("%s\n", err)
		os.Exit(1)
	}

	log.Printf("Connected to Docker %s", dockerVersion)

	envVarsFile := c.String("env-vars")
	envVarsOverrides := map[string]map[string]string{}
	if len(envVarsFile) > 0 {

		f, err := os.Open(c.String("env-vars"))
		if err != nil {
			fmt.Printf("Failed to open environment variables values file\n%s\n", err)
			os.Exit(1)
		}

		data, err := ioutil.ReadAll(f)
		if err != nil {
			fmt.Printf("Unable to read the environment variable values file\n%s\n", err)
			os.Exit(1)
		}

		// This is a JSON of structure {FunctionName: {key:value}, FunctionName: {key:value}}
		if err = json.Unmarshal(data, &envVarsOverrides); err != nil {
			fmt.Printf("Environment variable values must be a valid JSON\n%s\n", err)
			os.Exit(1)
		}
	}

	log.Printf("Successfully parsed %s (version %s)", c.String("template"), template.Version())

	// Create a new HTTP router to mount the functions on
	router := mux.NewRouter()

	functions := template.GetResourcesByType("AWS::Serverless::Function")

	// Keep track of successfully mounted functions, used for error reporting
	mounts := []mount{}
	endpointCount := 0

	for _, resource := range functions {

		if function, ok := resource.(resources.AWSServerlessFunction); ok {

			endpoints, err := function.Endpoints()
			if err != nil {
				log.Printf("Error while parsing API endpoints for %s: %s\n", function.Handler(), err)
				continue
			}

			for x := range endpoints {

				endpoint := endpoints[x].(resources.AWSServerlessFunctionEndpoint)
				endpointCount++

				// Find the env-vars map for the function
				funcEnvVarsOverrides := envVarsOverrides[function.FunctionName()]

				basedir := filepath.Dir(c.String("template"))
				runt, err := NewRuntime(basedir, function, funcEnvVarsOverrides)
				if err != nil {
					if err == ErrRuntimeNotSupported {
						log.Printf("Ignoring %s due to unsupported runtime (%s)\n", function.Handler(), function.Runtime())
						continue
					} else {
						log.Printf("Ignoring %s due to %s runtime init error: %s\n", function.Handler(), function.Runtime(), err)
						continue
					}
				}

				// Keep track of this successful mount, for displaying to the user
				mounts = append(mounts, mount{
					Handler:  function.Handler(),
					Runtime:  function.Runtime(),
					Endpoint: endpoint.Path(),
					Methods:  endpoint.Methods(),
				})

				router.HandleFunc(endpoint.Path(), func(w http.ResponseWriter, r *http.Request) {

					var wg sync.WaitGroup

					w.Header().Set("Content-Type", "application/json")

					event, err := NewEvent(r)
					if err != nil {
						msg := fmt.Sprintf("Error invoking %s runtime: %s", function.Runtime(), err)
						log.Println(msg)
						w.WriteHeader(http.StatusInternalServerError)
						w.Write([]byte(`{ "message": "Internal server error" }`))
						return
					}

					eventJSON, err := event.JSON()
					if err != nil {
						msg := fmt.Sprintf("Error invoking %s runtime: %s", function.Runtime(), err)
						log.Println(msg)
						w.WriteHeader(http.StatusInternalServerError)
						w.Write([]byte(`{ "message": "Internal server error" }`))
						return
					}

					stdoutTxt, stderrTxt, err := runt.Invoke(eventJSON)
					if err != nil {
						w.WriteHeader(http.StatusInternalServerError)
						w.Write([]byte(`{ "message": "Internal server error" }`))
						return
					}

					wg.Add(1)
					go func() {

						result, err := ioutil.ReadAll(stdoutTxt)
						if err != nil {
							w.WriteHeader(http.StatusInternalServerError)
							w.Write([]byte(`{ "message": "Internal server error" }`))
							wg.Done()
							return
						}

						// At this point, we need to see whether the response is in the format
						// of a Lambda proxy response (inc statusCode / body), and if so, handle it
						// otherwise just copy the whole output back to the http.ResponseWriter
						proxy := &struct {
							StatusCode int               `json:"statusCode"`
							Headers    map[string]string `json:"headers"`
							Body       string            `json:"body"`
						}{}

						if err := json.Unmarshal(result, proxy); err != nil || (proxy.StatusCode == 0 && len(proxy.Headers) == 0 && proxy.Body == "") {
							// This is not a proxy function, so just write the full output to the http response
							w.Write(result)
						} else {

							// Set any HTTP headers requested by the proxy function
							if len(proxy.Headers) > 0 {
								for key, value := range proxy.Headers {
									w.Header().Set(key, value)
								}
							}

							// This is a proxy function, so set the http status code and return the body
							if proxy.StatusCode != 0 {
								w.WriteHeader(proxy.StatusCode)
							}

							w.Write([]byte(proxy.Body))

						}

						wg.Done()

					}()

					wg.Add(1)
					go func() {
						// Finally, copy the container stderr (runtime logs) to the console stderr
						io.Copy(stderr, stderrTxt)
						wg.Done()
					}()

					wg.Wait()

					runt.CleanUp()

				}).Methods(endpoint.Methods()...)

			}

		}
	}

	if len(mounts) < 1 {

		if len(functions) < 1 {
			fmt.Fprintf(stderr, "ERROR: No Serverless functions were found in your SAM template.\n")
			os.Exit(1)
		}

		if endpointCount < 1 {
			fmt.Fprintf(stderr, "ERROR: None of the Serverless functions in your SAM template have valid API event sources.\n")
			os.Exit(1)
		}

		fmt.Fprintf(stderr, "ERROR: None of the Serverless functions in your SAM template were able to be mounted. See above for errors.\n")
		os.Exit(1)

	}

	fmt.Fprintf(stderr, "\n")
	for _, mount := range mounts {
		msg := fmt.Sprintf("Mounting %s (%s) at http://%s:%s%s %s", mount.Handler, mount.Runtime, c.String("host"), c.String("port"), mount.Endpoint, mount.Methods)
		fmt.Fprintf(os.Stderr, "%s\n", msg)
	}

	fmt.Fprintf(stderr, "\n")
	fmt.Fprintf(stderr, "You can now browse to the above endpoints to invoke your functions.\n")
	fmt.Fprintf(stderr, "You do not need to restart/reload sam-local while working on your functions,\n")
	fmt.Fprintf(stderr, "changes will be reflected instantly/automatically. You only need to restart\n")
	fmt.Fprintf(stderr, "SAM CLI if you update your AWS SAM template.\n")
	fmt.Fprintf(stderr, "\n")

	log.Fatal(http.ListenAndServe(c.String("host")+":"+c.String("port"), router))

}
