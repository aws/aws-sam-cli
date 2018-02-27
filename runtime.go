package main

import (
	"archive/zip"
	"bytes"
	"io"
	"io/ioutil"
	"log"
	"mime"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"sync"
	"time"

	"golang.org/x/net/context"

	"strings"

	"encoding/base64"
	"encoding/json"
	"fmt"
	"path"

	"os/signal"
	"syscall"

	"github.com/awslabs/aws-sam-local/router"
	"github.com/awslabs/goformation/cloudformation"
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
	Invoke(string, string) (io.Reader, io.Reader, error)
	InvokeHTTP(string) func(http.ResponseWriter, *router.Event)
	CleanUp()
}

// Runtime contains a reference to a single container for a specific runtime. It is used to invoke functions multiple times against a single container.
type Runtime struct {
	LogicalID       string
	ID              string
	Name            string
	Image           string
	Cwd             string
	DecompressedCwd string
	Function        cloudformation.AWSServerlessFunction
	EnvOverrideFile string
	DebugPort       string
	Context         context.Context
	Client          *client.Client
	TimeoutTimer    *time.Timer
	Logger          io.Writer
	DockerNetwork   string
}

var (
	// ErrRuntimeNotDownloaded is thrown when NewRuntime() is called, but the requested
	// runtime has not been downloaded
	ErrRuntimeNotDownloaded = errors.New("requested runtime has not been downloaded")

	// ErrRuntimeNotSupported is thrown with the requested runtime is not yet supported
	ErrRuntimeNotSupported = errors.New("unsupported runtime")
)

var runtimeName = struct {
	nodejs       string
	nodejs43     string
	nodejs610    string
	python27     string
	python36     string
	java8        string
	go1x         string
	dotnetcore20 string
}{
	nodejs:       "nodejs",
	nodejs43:     "nodejs4.3",
	nodejs610:    "nodejs6.10",
	python27:     "python2.7",
	python36:     "python3.6",
	java8:        "java8",
	go1x:         "go1.x",
	dotnetcore20: "dotnetcore2.0",
}

var runtimeImageFor = map[string]string{
	runtimeName.nodejs:       "lambci/lambda:nodejs",
	runtimeName.nodejs43:     "lambci/lambda:nodejs4.3",
	runtimeName.nodejs610:    "lambci/lambda:nodejs6.10",
	runtimeName.python27:     "lambci/lambda:python2.7",
	runtimeName.python36:     "lambci/lambda:python3.6",
	runtimeName.java8:        "lambci/lambda:java8",
	runtimeName.go1x:         "lambci/lambda:go1.x",
	runtimeName.dotnetcore20: "lambci/lambda:dotnetcore2.0",
}

// NewRuntimeOpt contains parameters that are passed to the NewRuntime method
type NewRuntimeOpt struct {
	Cwd             string
	LogicalID       string
	Function        cloudformation.AWSServerlessFunction
	EnvOverrideFile string
	DebugPort       string
	Logger          io.Writer
	SkipPullImage   bool
	DockerNetwork   string
}

// NewRuntime instantiates a Lambda runtime container
func NewRuntime(opt NewRuntimeOpt) (Invoker, error) {
	// Determine which docker image to use for the provided runtime
	image, found := runtimeImageFor[opt.Function.Runtime]
	if !found {
		return nil, ErrRuntimeNotSupported
	}

	cli, err := client.NewEnvClient()
	if err != nil {
		return nil, err
	}

	r := &Runtime{
		LogicalID:       opt.LogicalID,
		Name:            opt.Function.Runtime,
		Cwd:             getWorkingDir(opt.Cwd),
		Image:           image,
		Function:        opt.Function,
		EnvOverrideFile: opt.EnvOverrideFile,
		DebugPort:       opt.DebugPort,
		Context:         context.Background(),
		Client:          cli,
		Logger:          opt.Logger,
		DockerNetwork:   opt.DockerNetwork,
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

	// By default, pull images unless we are told not to
	pullImage := true

	if opt.SkipPullImage {
		log.Printf("Requested to skip pulling images ...\n")
		pullImage = false
	}

	// However, if we don't have the image we will need it...
	if len(images) == 0 {
		log.Printf("Runtime image missing, will pull....\n")
		pullImage = true
	}

	if pullImage {
		log.Printf("Fetching %s image for %s runtime...\n", r.Image, opt.Function.Runtime)
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

	// If the path is a Windows style one, convert it to the format that Docker Toolbox requires.
	mount = convertWindowsPath(mount)

	log.Printf("Mounting %s as /var/task:ro inside runtime container\n", mount)
	host := &container.HostConfig{
		Resources: container.Resources{
			Memory: int64(r.Function.MemorySize * 1024 * 1024),
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
func (r *Runtime) Invoke(event string, profile string) (io.Reader, io.Reader, error) {

	log.Printf("Invoking %s (%s)\n", r.Function.Handler, r.Name)

	// If the CodeUri has been specified as a .jar or .zip file, unzip it on the fly
	if r.Function.CodeUri != nil && r.Function.CodeUri.String != nil {
		codeuri := filepath.Join(r.Cwd, *r.Function.CodeUri.String)

		// Check if the CodeUri exists on the local filesystem
		if _, err := os.Stat(codeuri); err == nil {
			// It does exist - maybe it's a ZIP/JAR that we need to decompress on the fly
			if strings.HasSuffix(codeuri, ".jar") || strings.HasSuffix(codeuri, ".zip") {
				log.Printf("Decompressing %s\n", codeuri)
				decompressedDir, err := decompressArchive(codeuri)
				if err != nil {
					log.Printf("ERROR: Failed to decompress archive: %s\n", err)
					return nil, nil, fmt.Errorf("failed to decompress archive: %s", err)
				}
				r.DecompressedCwd = decompressedDir
			} else {
				// We have a CodeUri that exists locally, but isn't a ZIP/JAR.
				// Just append it to the working directory
				r.Cwd = codeuri
			}
		} else {
			// The CodeUri specified doesn't exist locally. It could be
			// an S3 location (s3://.....), so just ignore it.
		}
	}

	// If the timeout hasn't been set for the function in the SAM template
	// then default to 3 seconds (as per SAM specification).
	// This needs to be done before environment variables are generated for
	// the Lambda runtime so that the correct AWS_LAMBDA_FUNCTION_TIMEOUT is used
	if r.Function.Timeout <= 0 {
		r.Function.Timeout = 3
	}

	// If the memory size hasn't been set for the function in the SAM template
	// then default to 128MB (as per SAM specification).
	// This needs to be done before environment variables are generated for
	// the Lambda runtime so that the correct AWS_LAMBDA_FUNCTION_MEMORY_SIZE is used
	if r.Function.MemorySize <= 0 {
		r.Function.MemorySize = 128
	}

	// Define the container options
	config := &container.Config{
		WorkingDir:   "/var/task",
		Image:        r.Image,
		Tty:          false,
		ExposedPorts: r.getDebugExposedPorts(),
		Entrypoint:   r.getDebugEntrypoint(),
		Cmd:          []string{r.Function.Handler, event},
		Env: func() []string {
			result := []string{}
			for k, v := range getEnvironmentVariables(r.LogicalID, &r.Function, r.EnvOverrideFile, profile) {
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

	if r.DockerNetwork != "" {
		if err := r.Client.NetworkConnect(r.Context, r.DockerNetwork, resp.ID, nil); err != nil {
			return nil, nil, err
		}
		log.Printf("Connecting container %s to network %s", resp.ID, r.DockerNetwork)
	}

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
	timeout := time.Duration(r.Function.Timeout) * time.Second

	r.TimeoutTimer = time.NewTimer(timeout)
	go func() {
		<-r.TimeoutTimer.C
		log.Printf("Function %s timed out after %d seconds", r.Function.Handler, timeout/time.Second)
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
		log.Printf("Execution of function %q was interrupted", r.Function.Handler)
		stderr.Close()
		stdout.Close()
		r.CleanUp()
		os.Exit(0)
	}()
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
	debuggerArgs := os.Getenv("DEBUGGER_ARGS")
	debuggerArgsArray := strings.Split(debuggerArgs, " ")
	switch r.Name {
	// configs from: https://github.com/lambci/docker-lambda
	// to which we add the extra debug mode options
	case runtimeName.java8:
		overrides = []string{
			"/usr/bin/java",
		}
		overrides = append(overrides, debuggerArgsArray...)
		overrides = append(overrides,
			"-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,quiet=y,address=" + r.DebugPort,
			"-XX:MaxHeapSize=1336935k",
			"-XX:MaxMetaspaceSize=157286k",
			"-XX:ReservedCodeCacheSize=78643k",
			"-XX:+UseSerialGC",
			//"-Xshare:on", doesn't work in conjunction with the debug options
			"-XX:-TieredCompilation",
			"-jar",
			"/var/runtime/lib/LambdaJavaRTEntry-1.0.jar",
		)
	case runtimeName.nodejs:
		overrides = []string{
			"/usr/bin/node",
		}
		overrides = append(overrides, debuggerArgsArray...)
		overrides = append(overrides,
			"--debug-brk=" + r.DebugPort,
			"--nolazy",
			"--max-old-space-size=1229",
			"--max-new-space-size=153",
			"--max-executable-size=153",
			"--expose-gc",
			"/var/runtime/node_modules/awslambda/bin/awslambda",
		)
	case runtimeName.nodejs43:
		overrides = []string{
			"/usr/local/lib64/node-v4.3.x/bin/node",
		}
		overrides = append(overrides, debuggerArgsArray...)
		overrides = append(overrides,
			"--debug-brk=" + r.DebugPort,
			"--nolazy",
			"--max-old-space-size=1229",
			"--max-semi-space-size=76",
			"--max-executable-size=153",
			"--expose-gc",
			"/var/runtime/node_modules/awslambda/index.js",
		)
	case runtimeName.nodejs610:
		overrides = []string{
			"/var/lang/bin/node",
		}
		overrides = append(overrides, debuggerArgsArray...)
		overrides = append(overrides,
			"--inspect=" + r.DebugPort,
			"--debug-brk",
			"--nolazy",
			"--max-old-space-size=1229",
			"--max-semi-space-size=76",
			"--max-executable-size=153",
			"--expose-gc",
			"/var/runtime/node_modules/awslambda/index.js",
		)
	case runtimeName.python27:
		overrides = []string{
			"/usr/bin/python2.7",
		}
		overrides = append(overrides, debuggerArgsArray...)
		overrides = append(overrides, "/var/runtime/awslambda/bootstrap.py")
	}
	return
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

// InvokeHTTP invokes a Lambda function.
func (r *Runtime) InvokeHTTP(profile string) func(http.ResponseWriter, *router.Event) {

	return func(w http.ResponseWriter, event *router.Event) {
		var wg sync.WaitGroup
		w.Header().Set("Content-Type", "application/json")
		acceptHeader, ok := event.Headers["Accept"]
		if !ok {
			acceptHeader = ""
		}

		eventJSON, err := event.JSON()
		if err != nil {
			msg := fmt.Sprintf("Error invoking %s runtime: %s", r.Function.Runtime, err)
			log.Println(msg)
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{ "message": "Internal server error" }`))
			return
		}

		stdoutTxt, stderrTxt, err := r.Invoke(eventJSON, profile)
		if err != nil {
			msg := fmt.Sprintf("Error invoking %s runtime: %s", r.Function.Runtime, err)
			log.Println(msg)
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{ "message": "Internal server error" }`))
			return
		}

		wg.Add(1)
		var output []byte
		go func() {
			output = parseOutput(w, stdoutTxt, r.Function.Runtime, &wg, acceptHeader)
		}()

		wg.Add(1)
		go func() {
			// Finally, copy the container stdout and stderr (runtime logs) to the console stderr
			r.Logger.Write(output)
			io.Copy(r.Logger, stderrTxt)
			wg.Done()
		}()

		wg.Wait()

		r.CleanUp()
	}

}

// parseOutput decodes the proxy response from the output of the function and returns
// the rest
func parseOutput(w http.ResponseWriter, stdoutTxt io.Reader, runtime string, wg *sync.WaitGroup, acceptHeader string) (output []byte) {
	defer wg.Done()

	result, err := ioutil.ReadAll(stdoutTxt)
	if err != nil {
		msg := fmt.Sprintf("Error invoking %s runtime: %s", runtime, err)
		log.Println(msg)
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte(`{ "message": "Internal server error" }`))
		return
	}

	// At this point, we need to see whether the response is in the format
	// of a Lambda proxy response (inc statusCode / body), and if so, handle it
	// otherwise just copy the whole output back to the http.ResponseWriter
	proxy := &struct {
		StatusCode      json.Number       `json:"statusCode"`
		Headers         map[string]string `json:"headers"`
		Body            json.Number       `json:"body"`
		IsBase64Encoded bool              `json:"isBase64Encoded"`
	}{}

	// We only want the last line of stdout, because it's possible that
	// the function may have written directly to stdout using
	// System.out.println or similar, before docker-lambda output the result
	lastNewlineIx := bytes.LastIndexByte(bytes.TrimRight(result, "\n"), '\n')
	if lastNewlineIx > 0 {
		output = result[:lastNewlineIx]
		result = result[lastNewlineIx:]
	}

	if err := json.Unmarshal(result, proxy); err != nil || (proxy.StatusCode == "" && len(proxy.Headers) == 0 && proxy.Body == "") {
		// This is not a proxy integration function, as the response doesn't container headers, statusCode or body.
		// Return HTTP 502 (Bad Gateway) to match API Gateway behaviour: http://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-set-up-simple-proxy.html#api-gateway-simple-proxy-for-lambda-output-format
		log.Printf(color.RedString("Function returned an invalid response (must include one of: body, headers or statusCode in the response object): %s\n"), err)
		w.WriteHeader(http.StatusBadGateway)
		w.Write([]byte(`{ "message": "Internal server error" }`))
		return
	}

	// Set any HTTP headers requested by the proxy function
	if len(proxy.Headers) > 0 {
		for key, value := range proxy.Headers {
			w.Header().Add(key, value)
		}
	}

	// This is a proxy function, so set the http status code and return the body
	if statusCode, err := proxy.StatusCode.Int64(); err != nil {
		w.WriteHeader(http.StatusBadGateway)
	} else {
		w.WriteHeader(int(statusCode))
	}

	acceptMediaTypeMatched := false
	if acceptHeader != "" {
		//API Gateway only honors the first Accept media type.
		acceptMediaType := strings.Split(acceptHeader, ",")[0]
		contentType := proxy.Headers["Content-Type"]
		contentMediaType, _, err := mime.ParseMediaType(contentType)
		acceptMediaTypeMatched = err == nil && acceptMediaType == contentMediaType
	}

	if proxy.IsBase64Encoded && acceptMediaTypeMatched {
		if decodedBytes, err := base64.StdEncoding.DecodeString(string(proxy.Body)); err != nil {
			log.Printf(color.RedString("Function returned an invalid base64 body: %s\n"), err)
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{ "message": "Internal server error" }`))
		} else {
			w.Write(decodedBytes)
		}
	} else {
		w.Write([]byte(proxy.Body))
	}

	return
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

func getWorkingDir(dir string) string {

	// If the template filepath isn't set, just use the cwd
	if dir == "" || dir == "." {
		cwd, err := os.Getwd()
		if err != nil {
			// A directory wasn't specified on the command line
			// and we can't determin the current working directory.
			log.Printf("Could not find working directory for template: %s\n", err)
			return ""
		}
		dir = cwd
	}

	// Docker volumes require an absolute path.
	// If the path exists, use the absolute version.
	if _, err := os.Stat(dir); err == nil {
		absolute, err := filepath.Abs(dir)
		if err == nil {
			dir = absolute
		}
	}

	// Windows uses \ as the path delimiter, but Docker requires / as the path delimiter.
	// Hence the use of filepath.ToSlash for return values.
	return filepath.ToSlash(dir)

}

// decompressArchive unzips a ZIP archive to a temporary directory and returns
// the temporary directory name, or an error
func decompressArchive(src string) (string, error) {

	// Create a temporary directory just for this decompression (dirname: OS tmp directory + unix timestamp))
	tmpdir := os.TempDir()

	// By default on macOS, os.TempDir() returns a directory in /var/folders/.
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

		err := func() error {
			rc, err := f.Open()
			if err != nil {
				return err
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
					return err
				}
				f, err := os.OpenFile(
					fpath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, f.Mode())
				if err != nil {
					return err
				}
				defer f.Close()

				_, err = io.Copy(f, rc)
				if err != nil {
					return err
				}
			}

			return nil
		}()

		if err != nil {
			log.Fatal(err)
			return dest, err
		}
	}

	return dest, nil

}

func convertWindowsPath(input string) string {

	rg := regexp.MustCompile(`^([A-Za-z]+):`)
	drive := rg.FindAllStringSubmatch(input, 1)
	if drive != nil {

		// The path starts with a drive letter.
		// Docker toolbox mounts C:\ as /c/ so we need to extract, convert to lowercase
		// and replace into the correct format
		letter := drive[0][1]

		input = rg.ReplaceAllString(input, "/"+strings.ToLower(letter))

	}

	// Convert all OS seperators to '/'
	input = filepath.ToSlash(input)
	return input

}
