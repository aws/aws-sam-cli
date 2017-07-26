package main

import (
	"io"
	"log"
	"os"
	"strconv"
	"time"

	"golang.org/x/net/context"

	"strings"

	"encoding/json"
	"fmt"
	"path"

	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/awslabs/goformation/resources"
	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/jsonmessage"
	"github.com/docker/docker/pkg/stdcopy"
	"github.com/docker/docker/pkg/term"
	"github.com/imdario/mergo"
	"github.com/pkg/errors"
)

// Invoker is a simple interface to help with testing runtimes
type Invoker interface {
	Invoke(string) (io.Reader, io.Reader, error)
	CleanUp()
}

// Runtime contains a reference to a single container for a specific runtime. It is used to invoke functions multiple times against a single container.
type Runtime struct {
	ID              string
	Name            string
	Image           string
	Function        resources.AWSServerlessFunction
	EnvVarOverrides map[string]string
	Context         context.Context
	Client          *client.Client
	TimeoutTimer    *time.Timer
}

var (
	// ErrRuntimeNotDownloaded is thrown when NewRuntime() is called, but the requested
	// runtime has not been downloaded
	ErrRuntimeNotDownloaded = errors.New("requested runtime has not been downloaded")

	// ErrRuntimeNotSupported is thrown with the requested runtime is not yet supported
	ErrRuntimeNotSupported = errors.New("unsupported runtime")
)

var runtimes = map[string]string{
	"nodejs":     "lambci/lambda:nodejs",
	"nodejs4.3":  "lambci/lambda:nodejs4.3",
	"nodejs6.10": "lambci/lambda:nodejs6.10",
	"python2.7":  "lambci/lambda:python2.7",
	"python3.6":  "lambci/lambda:python3.6",
	"java8":      "lambci/lambda:java8",
}

// NewRuntime instantiates a Lambda runtime container
func NewRuntime(function resources.AWSServerlessFunction, envVarsOverrides map[string]string) (Invoker, error) {

	// Determin which docker image to use for the provided runtime
	image, found := runtimes[function.Runtime()]
	if !found {
		return nil, ErrRuntimeNotSupported
	}

	cli, err := client.NewEnvClient()
	if err != nil {
		return nil, err
	}

	r := &Runtime{
		Name:            function.Runtime(),
		Image:           image,
		Function:        function,
		EnvVarOverrides: envVarsOverrides,
		Context:         context.Background(),
		Client:          cli,
	}

	// Check if we have the required Docker image for this runtime
	filter := filters.NewArgs()
	filter.Add("reference", r.Image)
	images, err := cli.ImageList(r.Context, types.ImageListOptions{
		Filters: filter,
	})
	if err != nil {
		return nil, err
	}

	if len(images) < 1 {

		log.Printf("Fetching %s image for %s runtime...\n", r.Image, function.Runtime())
		progress, err := cli.ImagePull(r.Context, r.Image, types.ImagePullOptions{})
		if err != nil {
			log.Fatalf("Could not fetch %s Docker image\n%s", r.Image, err)
			return nil, err
		}

		// Use Docker's standard progressbar to show image pull progress.
		// It does however have a nasty bug (actually, in the Gotty library it uses)
		// which means it panics on some TERM configurations. There's a pull request to
		// fix it, but the Gotty library hasn't been updated in 5yrs and it hasn't been merged.

		// To get around this, we'll do the same as Docker does, and temporarily set
		// the TERM to a non-existant terminal, to force Gotty to use &noTermInfo

		// More info here:
		// https://github.com/Nvveen/Gotty/pull/1

		origTerm := os.Getenv("TERM")
		os.Setenv("TERM", "eifjccgifcdekgnbtlvrgrinjjvfjggrcudfrriivjht")
		jsonmessage.DisplayJSONMessagesStream(progress, os.Stdout, os.Stdout.Fd(), term.IsTerminal(os.Stdout.Fd()), nil)
		os.Setenv("TERM", origTerm)

	}

	return r, nil

}

func overrideHostConfig(cfg *container.HostConfig) error {
	const dotfile = ".config/aws-sam-cli/container-config.json"
	const eMsg = "unable to use container host config override file from '$HOME/%s'"

	homeDir := os.Getenv("HOME")
	if len(homeDir) == 0 {
		return errors.Wrapf(errors.New("HOME env variable is not set"), eMsg, dotfile)
	}

	reader, err := os.Open(path.Join(homeDir, dotfile))
	if err != nil {
		if os.IsNotExist(err) {
			return nil
		}
		return errors.Wrapf(err, eMsg, dotfile)
	}
	defer reader.Close()

	override := new(container.HostConfig)
	if err := json.NewDecoder(reader).Decode(override); err != nil {
		return errors.Wrapf(err, eMsg, dotfile)
	}

	return errors.Wrapf(mergo.MergeWithOverwrite(cfg, override), eMsg, dotfile)
}

func (r *Runtime) getHostConfig() (*container.HostConfig, error) {
	pwd, err := os.Getwd()
	if err != nil {
		return nil, errors.Wrap(err, "unable to create container host config")
	}
	host := &container.HostConfig{
		Resources: container.Resources{
			Memory: int64(r.Function.MemorySize() * 1024 * 1024),
		},
		Binds: []string{
			fmt.Sprintf("%s:/var/task:ro", pwd),
		},
	}
	if err := overrideHostConfig(host); err != nil {
		log.Print(err)
	}

	return host, nil
}

// Invoke runs a Lambda function within the runtime with the provided event payload
// and returns a pair of io.Readers for it's stdout (callback results) and
//  stderr (runtime logs).
func (r *Runtime) Invoke(event string) (io.Reader, io.Reader, error) {

	log.Printf("Invoking %s (%s)\n", r.Function.Handler(), r.Name)

	env := getEnvironmentVariables(r.Function, r.EnvVarOverrides)

	// Define the container options
	config := &container.Config{
		WorkingDir: "/var/task",
		Image:      r.Image,
		Tty:        false,
		Cmd:        []string{r.Function.Handler(), event},
		Env: func() []string {
			result := []string{}
			for k, v := range env {
				result = append(result, k+"="+v)
			}
			return result
		}(),
	}

	host, err := r.getHostConfig()
	if err != nil {
		return nil, nil, err
	}

	resp, err := r.Client.ContainerCreate(r.Context, config, host, nil, "")
	if err != nil {
		return nil, nil, err
	}

	r.ID = resp.ID

	// Invoke the container
	if err := r.Client.ContainerStart(r.Context, resp.ID, types.ContainerStartOptions{}); err != nil {
		return nil, nil, err
	}

	// Attach to the container to read the stdout/stderr stream
	attach, err := r.Client.ContainerAttach(r.Context, resp.ID, types.ContainerAttachOptions{
		Stream: true,
		Stdin:  false,
		Stdout: true,
		Stderr: true,
		Logs:   true,
	})

	// As per the Docker SDK documentation, when attaching to a container
	// the resulting io.Reader stream is has stdin, stdout and stderr muxed
	// into a single stream, with a 8 byte header defining the type/size.
	// Demux the stream into separate io.Readers for stdout and stderr
	// src: https://docs.docker.com/engine/api/v1.28/#operation/ContainerAttach
	stdout, stderr, err := demuxDockerStream(attach.Reader)
	if err != nil {
		return nil, nil, err
	}

	// Start a timer, we'll use this to abort the function if it runs beyond the specified timeout
	// TODO: Remove this default timeout once the SAM parser allows defaults to be specified
	timeout := time.Duration(3) * time.Second
	if r.Function.Timeout() > 0 {
		timeout = time.Duration(r.Function.Timeout()) * time.Second
	}
	r.TimeoutTimer = time.NewTimer(timeout)
	go func() {
		<-r.TimeoutTimer.C
		log.Printf("Function %s timed out after %d seconds", r.Function.Handler(), timeout/time.Second)
		stderr.Close()
		stdout.Close()
		r.CleanUp()
	}()

	return stdout, stderr, nil

}

func getSessionOrDefaultCreds() map[string]string {

	region := "us-east-1"
	key := "defaultkey"
	secret := "defaultsecret"
	sessiontoken := "sessiontoken"

	result := map[string]string{
		"region":  region,
		"key":     key,
		"secret":  secret,
		"session": sessiontoken,
	}

	// Obtain AWS credentials and pass them through to the container runtime via env variables
	if sess, err := session.NewSession(); err != nil {
		if creds, err := sess.Config.Credentials.Get(); err != nil {
			result["region"] = *sess.Config.Region
			result["key"] = creds.AccessKeyID
			result["secret"] = creds.SecretAccessKey
			result["sessiontoken"] = creds.SessionToken
		}
	}
	return result
}

func getOsEnviron() map[string]string {

	result := map[string]string{}
	for _, value := range os.Environ() {

		keyVal := strings.Split(value, "=")
		result[keyVal[0]] = keyVal[1]
	}

	return result
}

/**
 The Environment Variable Saga..

 There are two types of environment variables
 	- Lambda runtime variables starting with "AWS_" and passed to every function
 	- Custom environment variables defined in SAM template for each function

 Custom environment variables defined in the SAM template can contain hard-coded
 values or fetch from a stack parameter or use Intrinsics to generate a value at
 at stack creation time like ARNs. It can get complicated to support all cases

 Instead we will parse only hard-coded values from the template. For the rest,
 users can supply values through the Shell's environment or the env-var override
 CLI argument. If a value is provided through more than one method, the method
 with higher priority will win.

 Priority (Highest to lowest)
	Env-Var CLI argument
	Shell's Environment
	Hard-coded values from template

 This priority also applies to AWS_* system variables
*/
func getEnvironmentVariables(function resources.AWSServerlessFunction, overrides map[string]string) map[string]string {

	creds := getSessionOrDefaultCreds()

	// Variables available in Lambda execution environment for all functions (AWS_* variables)
	env := map[string]string{
		"AWS_DEFAULT_REGION":              creds["region"],
		"AWS_ACCESS_KEY_ID":               creds["key"],
		"AWS_SECRET_ACCESS_KEY":           creds["secret"],
		"AWS_SESSION_TOKEN":               creds["sessiontoken"],
		"AWS_LAMBDA_FUNCTION_MEMORY_SIZE": strconv.Itoa(int(function.MemorySize())),
		"AWS_LAMBDA_FUNCTION_TIMEOUT":     strconv.Itoa(int(function.Timeout())),
		"AWS_LAMBDA_FUNCTION_HANDLER":     function.Handler(),
		// "AWS_ACCOUNT_ID=",
		// "AWS_LAMBDA_EVENT_BODY=",
		// "AWS_REGION=",
		// "AWS_LAMBDA_FUNCTION_NAME=",
		// "AWS_LAMBDA_FUNCTION_VERSION=",
	}

	// Get all env vars from SAM file. Use values if it was hard-coded
	osEnviron := getOsEnviron()
	for name, value := range function.EnvironmentVariables() {
		// hard-coded values, lowest priority
		if stringedValue, ok := toStringMaybe(value); ok {
			// Get only hard-coded values from the template
			env[name] = stringedValue
		}

		// Shell's environment, second priority
		if value, ok := osEnviron[name]; ok {
			env[name] = value
		}

		// EnvVars overrides provided by customer, highest priority
		if len(overrides) > 0 {
			if value, ok := overrides[name]; ok {
				env[name] = value
			}
		}
	}

	return env
}

// Converts the input to string if it is a primitive type, Otherwise returns nil
func toStringMaybe(value interface{}) (string, bool) {

	switch value.(type) {
	case string:
		return value.(string), true
	case int:
		return strconv.Itoa(value.(int)), true
	case float32, float64:
		return strconv.FormatFloat(value.(float64), 'f', -1, 64), true
	case bool:
		return strconv.FormatBool(value.(bool)), true
	default:
		return "", false
	}
}

// CleanUp removes the Docker container used by this runtime
func (r *Runtime) CleanUp() {
	r.TimeoutTimer.Stop()
	r.Client.ContainerKill(r.Context, r.ID, "SIGKILL")
	r.Client.ContainerRemove(r.Context, r.ID, types.ContainerRemoveOptions{})
}

// demuxDockerStream takes a Docker attach stream, and parses out stdout/stderr
// into separate streams, based on the Docker engine documentation here:
// https://docs.docker.com/engine/api/v1.28/#operation/ContainerAttach
// Due to the use of io.Pipe, you should take care to read from the streams
// in a separate Go routine to avoid deadlocks.
func demuxDockerStream(input io.Reader) (io.ReadCloser, io.ReadCloser, error) {

	stdoutreader, stdoutwriter := io.Pipe()
	stderrreader, stderrwriter := io.Pipe()

	// Return early and continue to copy i/o in another go routine
	go func() {

		_, err := stdcopy.StdCopy(stdoutwriter, stderrwriter, input)
		if err != nil {
			log.Printf("Error reading I/O from runtime container: %s\n", err)
		}

		stdoutwriter.Close()
		stderrwriter.Close()

	}()

	return stdoutreader, stderrreader, nil

}

func getDockerVersion() (string, error) {

	cli, err := client.NewEnvClient()
	if err != nil {
		return "", err
	}

	response, err := cli.Ping(context.Background())
	return response.APIVersion, err

}
