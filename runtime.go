package main

import (
	"archive/zip"
	"io"
	"log"
	"os"
	"path/filepath"
	"strconv"
	"time"

	"golang.org/x/net/context"

	"strings"

	"encoding/json"
	"fmt"
	"path"

	"os/signal"
	"syscall"

	"github.com/aws/aws-sdk-go/aws/session"
	"github.com/awslabs/goformation/resources"
	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/jsonmessage"
	"github.com/docker/docker/pkg/stdcopy"
	"github.com/docker/docker/pkg/term"
	"github.com/docker/go-connections/nat"
	"github.com/fatih/color"
	"github.com/imdario/mergo"
	"github.com/mattn/go-colorable"
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
	Cwd             string
	DecompressedCwd string
	Function        resources.AWSServerlessFunction
	EnvVarOverrides map[string]string
	DebugPort       string
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

var runtimeName = struct {
	nodejs    string
	nodejs43  string
	nodejs610 string
	python27  string
	python36  string
	java8     string
}{
	nodejs:    "nodejs",
	nodejs43:  "nodejs4.3",
	nodejs610: "nodejs6.10",
	python27:  "python2.7",
	python36:  "python3.6",
	java8:     "java8",
}

var runtimeImageFor = map[string]string{
	runtimeName.nodejs:    "lambci/lambda:nodejs",
	runtimeName.nodejs43:  "lambci/lambda:nodejs4.3",
	runtimeName.nodejs610: "lambci/lambda:nodejs6.10",
	runtimeName.python27:  "lambci/lambda:python2.7",
	runtimeName.python36:  "lambci/lambda:python3.6",
	runtimeName.java8:     "lambci/lambda:java8",
}

// NewRuntimeOpt contains parameters that are passed to the NewRuntime method
type NewRuntimeOpt struct {
	Function             resources.AWSServerlessFunction
	EnvVarsOverrides     map[string]string
	Basedir              string
	CheckWorkingDirExist bool
	DebugPort            string
}

// NewRuntime instantiates a Lambda runtime container
func NewRuntime(opt NewRuntimeOpt) (Invoker, error) {
	// Determine which docker image to use for the provided runtime
	image, found := runtimeImageFor[opt.Function.Runtime()]
	if !found {
		return nil, ErrRuntimeNotSupported
	}

	cli, err := client.NewEnvClient()
	if err != nil {
		return nil, err
	}

	cwd, err := getWorkingDir(opt.Basedir, opt.Function.CodeURI().String(), opt.CheckWorkingDirExist)
	if err != nil {
		return nil, err
	}

	r := &Runtime{
		Name:            opt.Function.Runtime(),
		Cwd:             cwd,
		Image:           image,
		Function:        opt.Function,
		EnvVarOverrides: opt.EnvVarsOverrides,
		DebugPort:       opt.DebugPort,
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

	log.Printf("Fetching %s image for %s runtime...\n", r.Image, opt.Function.Runtime())
	progress, err := cli.ImagePull(r.Context, r.Image, types.ImagePullOptions{})
	if len(images) < 0 && err != nil {
		log.Fatalf("Could not fetch %s Docker image\n%s", r.Image, err)
		return nil, err
	}

	if err != nil {
		log.Printf("Could not fetch %s Docker image: %s\n", r.Image, err)
	} else {

		// Use Docker's standard progressbar to show image pull progress.
		// However there is a bug that we are working around. We'll do the same
		// as Docker does, and temporarily set the TERM to a non-existant
		// terminal
		// More info here:
		// https://github.com/Nvveen/Gotty/pull/1

		origTerm := os.Getenv("TERM")
		os.Setenv("TERM", "eifjccgifcdekgnbtlvrgrinjjvfjggrcudfrriivjht")
		defer os.Setenv("TERM", origTerm)

		// Show the Docker pull messages in green
		color.Output = colorable.NewColorableStderr()
		color.Set(color.FgGreen)
		defer color.Unset()

		jsonmessage.DisplayJSONMessagesStream(progress, os.Stderr, os.Stderr.Fd(), term.IsTerminal(os.Stderr.Fd()), nil)

	}

	return r, nil

}

func overrideHostConfig(cfg *container.HostConfig) error {
	const dotfile = ".config/aws-sam-local/container-config.json"
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

	// Check if there is a decompressed archive directory we should
	// be using instead of the normal working directory (e.g. if a
	// ZIP/JAR archive was specified as the CodeUri)
	mount := r.Cwd
	if r.DecompressedCwd != "" {
		mount = r.DecompressedCwd
	}

	host := &container.HostConfig{
		Resources: container.Resources{
			Memory: int64(r.Function.MemorySize() * 1024 * 1024),
		},
		Binds: []string{
			fmt.Sprintf("%s:/var/task:ro", mount),
		},
		PortBindings: r.getDebugPortBindings(),
	}

	if err := overrideHostConfig(host); err != nil {
		log.Print(err)
	}

	return host, nil
}

// Invoke runs a Lambda function within the runtime with the provided event
// payload and returns a pair of io.Readers for it's stdout (callback results)
// and stderr (runtime logs).
func (r *Runtime) Invoke(event string) (io.Reader, io.Reader, error) {

	log.Printf("Invoking %s (%s)\n", r.Function.Handler(), r.Name)

	// If the CodeUri has been specified as a .jar or .zip file, unzip it on the fly
	if strings.HasSuffix(r.Cwd, ".jar") || strings.HasSuffix(r.Cwd, ".zip") {
		log.Printf("Decompressing %s into runtime container...\n", filepath.Base(r.Cwd))
		decompressedDir, err := decompressArchive(r.Cwd)
		if err != nil {
			log.Printf("ERROR: Failed to decompress archive: %s\n", err)
			return nil, nil, fmt.Errorf("failed to decompress archive: %s", err)
		}
		r.DecompressedCwd = decompressedDir

	}

	env := getEnvironmentVariables(r.Function, r.EnvVarOverrides)

	// Define the container options
	config := &container.Config{
		WorkingDir:   "/var/task",
		Image:        r.Image,
		Tty:          false,
		ExposedPorts: r.getDebugExposedPorts(),
		Entrypoint:   r.getDebugEntrypoint(),
		Cmd:          []string{r.Function.Handler(), event},
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

	if len(r.DebugPort) == 0 {
		r.setupTimeoutTimer(stdout, stderr)
	} else {
		r.setupInterruptHandler(stdout, stderr)
	}

	return stdout, stderr, nil

}

func (r *Runtime) setupTimeoutTimer(stdout, stderr io.ReadCloser) {
	// Start a timer, we'll use this to abort the function if it runs beyond the specified timeout
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
}

func (r *Runtime) setupInterruptHandler(stdout, stderr io.ReadCloser) {
	iChan := make(chan os.Signal, 2)
	signal.Notify(iChan, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-iChan
		log.Printf("Execution of function %q was interrupted", r.Function.Handler())
		stderr.Close()
		stdout.Close()
		r.CleanUp()
		os.Exit(0)
	}()
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
	if sess, err := session.NewSession(); err == nil {
		if creds, err := sess.Config.Credentials.Get(); err == nil {
			if *sess.Config.Region != "" {
				result["region"] = *sess.Config.Region
			}

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

func (r *Runtime) getDebugPortBindings() nat.PortMap {
	if len(r.DebugPort) == 0 {
		return nil
	}
	return nat.PortMap{
		nat.Port(r.DebugPort): []nat.PortBinding{{HostPort: r.DebugPort}},
	}
}

func (r *Runtime) getDebugExposedPorts() nat.PortSet {
	if len(r.DebugPort) == 0 {
		return nil
	}
	return nat.PortSet{nat.Port(r.DebugPort): {}}
}

func (r *Runtime) getDebugEntrypoint() (overrides []string) {
	if len(r.DebugPort) == 0 {
		return
	}
	switch r.Name {
	// configs from: https://github.com/lambci/docker-lambda
	// to which we add the extra debug mode options
	case runtimeName.java8:
		overrides = []string{
			"/usr/bin/java",
			"-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address=" + r.DebugPort,
			"-XX:MaxHeapSize=1336935k",
			"-XX:MaxMetaspaceSize=157286k",
			"-XX:ReservedCodeCacheSize=78643k",
			"-XX:+UseSerialGC",
			//"-Xshare:on", doesn't work in conjunction with the debug options
			"-XX:-TieredCompilation",
			"-jar",
			"/var/runtime/lib/LambdaJavaRTEntry-1.0.jar",
		}
	case runtimeName.nodejs:
		overrides = []string{
			"/usr/bin/node",
			"--debug-brk=" + r.DebugPort,
			"--nolazy",
			"--max-old-space-size=1229",
			"--max-new-space-size=153",
			"--max-executable-size=153",
			"--expose-gc",
			"/var/runtime/node_modules/awslambda/bin/awslambda",
		}
	case runtimeName.nodejs43:
		overrides = []string{
			"/usr/local/lib64/node-v4.3.x/bin/node",
			"--debug-brk=" + r.DebugPort,
			"--nolazy",
			"--max-old-space-size=1229",
			"--max-semi-space-size=76",
			"--max-executable-size=153",
			"--expose-gc",
			"/var/runtime/node_modules/awslambda/index.js",
		}
	case runtimeName.nodejs610:
		overrides = []string{
			"/var/lang/bin/node",
			"--debug-brk=" + r.DebugPort,
			"--nolazy",
			"--max-old-space-size=1229",
			"--max-semi-space-size=76",
			"--max-executable-size=153",
			"--expose-gc",
			"/var/runtime/node_modules/awslambda/index.js",
		}
		// TODO: also add debug mode for Python runtimes
	}
	return
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
		"AWS_SAM_LOCAL":                   "true",
		"AWS_REGION":                      creds["region"],
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

	// Stop the Lambda timeout timer
	if r.TimeoutTimer != nil {
		r.TimeoutTimer.Stop()
	}

	// Remove the container
	r.Client.ContainerKill(r.Context, r.ID, "SIGKILL")
	r.Client.ContainerRemove(r.Context, r.ID, types.ContainerRemoveOptions{})

	// Remove any decompressed archive if there was one (e.g. ZIP/JAR)
	if r.DecompressedCwd != "" {
		os.RemoveAll(r.DecompressedCwd)
	}

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

		stdoutwriter.Write([]byte("\n"))

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

func getWorkingDir(basedir string, codeuri string, checkWorkingDirExist bool) (string, error) {

	// Determine which directory to mount into the runtime container.
	// If no CodeUri is specified for this function, then use the same
	// directory as the SAM template (basedir), otherwise mount the
	// directory specified in the CodeUri property.
	abs, err := filepath.Abs(basedir)
	if err != nil {
		return "", err
	}

	dir := filepath.Join(abs, codeuri)

	if checkWorkingDirExist {

		// ...but only if it actually exists
		if _, err := os.Stat(dir); err != nil {
			// It doesn't, so just use the directory of the SAM template
			// which might have been passed as a relative directory
			dir = abs
		}

	}

	// Windows uses \ as the path delimiter, but Docker requires / as the path delimiter.
	dir = filepath.ToSlash(dir)
	return dir, nil

}

// decompressArchive unzips a ZIP archive to a temporary directory and returns
// the temporary directory name, or an error
func decompressArchive(src string) (string, error) {

	// Create a temporary directory just for this decompression (dirname: OS tmp directory + unix timestamp))
	tmpdir := os.TempDir()

	// By default on OSX, os.TempDir() returns a directory in /var/folders/.
	// This sits outside the default Docker Shared Files directories, however
	// /var/folders is just a symlink to /private/var/folders/, so use that instead
	if strings.HasPrefix(tmpdir, "/var/folders") {
		tmpdir = "/private" + tmpdir
	}

	dest := filepath.Join(tmpdir, "aws-sam-local-"+strconv.FormatInt(time.Now().UnixNano(), 10))

	var filenames []string

	r, err := zip.OpenReader(src)
	if err != nil {
		return dest, err
	}
	defer r.Close()

	for _, f := range r.File {

		rc, err := f.Open()
		if err != nil {
			return dest, err
		}
		defer rc.Close()

		// Store filename/path for returning and using later on
		fpath := filepath.Join(dest, f.Name)
		filenames = append(filenames, fpath)

		if f.FileInfo().IsDir() {

			// Make Folder
			os.MkdirAll(fpath, os.ModePerm)

		} else {

			// Make File
			var fdir string
			if lastIndex := strings.LastIndex(fpath, string(os.PathSeparator)); lastIndex > -1 {
				fdir = fpath[:lastIndex]
			}

			err = os.MkdirAll(fdir, os.ModePerm)
			if err != nil {
				log.Fatal(err)
				return dest, err
			}
			f, err := os.OpenFile(
				fpath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, f.Mode())
			if err != nil {
				return dest, err
			}
			defer f.Close()

			_, err = io.Copy(f, rc)
			if err != nil {
				return dest, err
			}

		}
	}

	return dest, nil

}
