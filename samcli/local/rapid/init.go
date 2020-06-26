package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"math"
	"math/rand"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"reflect"
	"regexp"
	"strconv"
	"sync"
	"syscall"
	"time"

	"github.com/go-chi/chi"
	"github.com/go-chi/render"
	"github.com/rjeczalik/notify"
)

var logDebug = os.Getenv("DOCKER_LAMBDA_DEBUG") != ""
var stayOpen = os.Getenv("DOCKER_LAMBDA_STAY_OPEN") != ""
var noBootstrap = os.Getenv("DOCKER_LAMBDA_NO_BOOTSTRAP") != ""
var apiPort = getEnv("DOCKER_LAMBDA_API_PORT", "9001")
var runtimePort = getEnv("DOCKER_LAMBDA_RUNTIME_PORT", "9001")
var useStdin = os.Getenv("DOCKER_LAMBDA_USE_STDIN") != ""
var noModifyLogs = os.Getenv("DOCKER_LAMBDA_NO_MODIFY_LOGS") != ""
var watchMode = os.Getenv("DOCKER_LAMBDA_WATCH") != ""

var curState = "STATE_INIT"

var transitions = map[string]map[string]bool{
	"STATE_INIT_ERROR":      map[string]bool{"STATE_INIT": true},
	"STATE_INVOKE_NEXT":     map[string]bool{"STATE_INIT": true, "STATE_INVOKE_NEXT": true, "STATE_INVOKE_RESPONSE": true, "STATE_INVOKE_ERROR": true},
	"STATE_INVOKE_RESPONSE": map[string]bool{"STATE_INVOKE_NEXT": true},
	"STATE_INVOKE_ERROR":    map[string]bool{"STATE_INVOKE_NEXT": true},
}

var acceptedResponse = &statusResponse{Status: "OK", HTTPStatusCode: 202}

var curContext *mockLambdaContext
var bootstrapCmd *exec.Cmd
var initPrinted bool
var eventChan chan *mockLambdaContext
var bootstrapExitedGracefully bool
var bootstrapIsRunning bool
var bootstrapPath *string
var bootstrapArgs []string
var bootstrapMutex sync.Mutex
var logsBuf bytes.Buffer
var serverInitEnd time.Time

func newContext() *mockLambdaContext {
	context := &mockLambdaContext{
		RequestID:       fakeGUID(),
		FnName:          getEnv("AWS_LAMBDA_FUNCTION_NAME", "test"),
		Version:         getEnv("AWS_LAMBDA_FUNCTION_VERSION", "$LATEST"),
		MemSize:         getEnv("AWS_LAMBDA_FUNCTION_MEMORY_SIZE", "1536"),
		Timeout:         getEnv("AWS_LAMBDA_FUNCTION_TIMEOUT", "300"),
		Region:          getEnv("AWS_REGION", getEnv("AWS_DEFAULT_REGION", "us-east-1")),
		AccountID:       getEnv("AWS_ACCOUNT_ID", strconv.FormatInt(int64(rand.Int31()), 10)),
		XAmznTraceID:    getEnv("_X_AMZN_TRACE_ID", ""),
		ClientContext:   getEnv("AWS_LAMBDA_CLIENT_CONTEXT", ""),
		CognitoIdentity: getEnv("AWS_LAMBDA_COGNITO_IDENTITY", ""),
		Start:           time.Now(),
		Done:            make(chan bool),
	}
	context.ParseTimeout()
	context.ParseFunctionArn()
	return context
}

type key int

const (
	keyRequestID key = iota
)

func main() {
	rand.Seed(time.Now().UTC().UnixNano())
	log.SetOutput(os.Stderr)

	interrupt := make(chan os.Signal, 1)
	signal.Notify(interrupt, os.Interrupt)

	render.Respond = renderJSON

	eventChan = make(chan *mockLambdaContext)

	bootstrapPath = flag.String("bootstrap", "/var/runtime/bootstrap", "path to bootstrap")
	bootstrapArgsString := flag.String("bootstrap-args", "[]", "additional arguments passed to bootstrap, as a stringified JSON Array")
	flag.Bool("enable-msg-logs", false, "enable message logs")

	flag.Parse()
	positionalArgs := flag.Args()

	if err := json.Unmarshal([]byte(*bootstrapArgsString), &bootstrapArgs); err != nil {
		log.Fatal(fmt.Errorf("Value of --bootstrap-args should be a JSON Array. Error: %s", err))
		return
	}

	var handler string
	if len(positionalArgs) > 0 {
		handler = positionalArgs[0]
	} else {
		handler = getEnv("AWS_LAMBDA_FUNCTION_HANDLER", getEnv("_HANDLER", "handler"))
	}
	os.Setenv("_HANDLER", handler)

	var eventBody []byte
	if len(positionalArgs) > 1 {
		eventBody = []byte(positionalArgs[1])
	} else {
		eventBody = []byte(os.Getenv("AWS_LAMBDA_EVENT_BODY"))
		if len(eventBody) == 0 {
			if useStdin {
				eventBody, _ = ioutil.ReadAll(os.Stdin)
			} else {
				eventBody = []byte("{}")
			}
		}
	}

	curContext = newContext()

	os.Setenv("AWS_LAMBDA_FUNCTION_NAME", curContext.FnName)
	os.Setenv("AWS_LAMBDA_FUNCTION_VERSION", curContext.Version)
	os.Setenv("AWS_LAMBDA_FUNCTION_MEMORY_SIZE", curContext.MemSize)
	os.Setenv("AWS_LAMBDA_LOG_GROUP_NAME", "/aws/lambda/"+curContext.FnName)
	os.Setenv("AWS_LAMBDA_LOG_STREAM_NAME", logStreamName(curContext.Version))
	os.Setenv("AWS_REGION", curContext.Region)
	os.Setenv("AWS_DEFAULT_REGION", curContext.Region)
	os.Setenv("_X_AMZN_TRACE_ID", curContext.XAmznTraceID)

	runtimeAddress := ":" + runtimePort
	if apiPort != runtimePort {
		// We can restrict runtime to 127.0.0.1 if we don't need the port for the Lambda API
		runtimeAddress = "127.0.0.1" + runtimeAddress
	}
	runtimeListener, err := net.Listen("tcp", runtimeAddress)
	if err != nil {
		log.Fatal(err)
		return
	}

	var runtimeServer *http.Server

	runtimeRouter := createRuntimeRouter()
	runtimeServer = &http.Server{Handler: addAPIRoutes(runtimeRouter)}

	go runtimeServer.Serve(runtimeListener)

	exitCode := 0

	serverInitEnd = time.Now()

	if stayOpen {
		if watchMode {
			setupFileWatchers()
		}
		setupSighupHandler()
		systemLog(fmt.Sprintf("Lambda API listening on port %s...", apiPort))
		<-interrupt
	} else {
		res, err := http.Post(
			"http://127.0.0.1:"+runtimePort+"/2015-03-31/functions/"+curContext.FnName+"/invocations",
			"application/json",
			bytes.NewBuffer(eventBody),
		)
		if err != nil {
			log.Fatal(err)
			return
		}
		functionError := res.Header.Get("X-Amz-Function-Error")

		body, err := ioutil.ReadAll(res.Body)
		if err != nil {
			log.Fatal(err)
			return
		}
		res.Body.Close()

		fmt.Println("\n" + formatOneLineJSON(body))

		if functionError != "" {
			exitCode = 1
		}
	}

	exit(exitCode)
}

func setupSighupHandler() {
	sighupReceiver := make(chan os.Signal, 1)
	signal.Notify(sighupReceiver, syscall.SIGHUP)
	go func() {
		for {
			<-sighupReceiver
			systemLog(fmt.Sprintf("SIGHUP received, restarting bootstrap..."))
			reboot()
		}
	}()
}

func setupFileWatchers() {
	fileWatcher := make(chan notify.EventInfo, 1)
	if err := notify.Watch("/var/task/...", fileWatcher, notify.All); err != nil {
		log.Fatal(err)
	}
	if err := notify.Watch("/opt/...", fileWatcher, notify.All); err != nil {
		log.Fatal(err)
	}
	go func() {
		for {
			ei := <-fileWatcher
			debug("Received notify event: ", ei)
			systemLog(fmt.Sprintf("Handler/layer file changed, restarting bootstrap..."))
			reboot()
		}
	}()
}

func formatOneLineJSON(body []byte) string {
	payloadObj := &json.RawMessage{}
	if json.Unmarshal(body, payloadObj) == nil {
		if formattedPayload, err := json.Marshal(payloadObj); err == nil {
			body = formattedPayload
		}
	}
	return string(body)
}

func ensureBootstrapIsRunning(context *mockLambdaContext) error {
	if noBootstrap || bootstrapIsRunning {
		return nil
	}
	bootstrapMutex.Lock()
	defer bootstrapMutex.Unlock()
	if bootstrapIsRunning {
		return nil
	}
	for _, cmdPath := range []string{*bootstrapPath, "/var/task/bootstrap", "/opt/bootstrap"} {
		if fi, err := os.Stat(cmdPath); err == nil && !fi.IsDir() {
			bootstrapCmd = exec.Command(cmdPath, bootstrapArgs...)
			break
		}
	}
	if bootstrapCmd == nil {
		return fmt.Errorf("Couldn't find valid bootstrap(s): [/var/task/bootstrap /opt/bootstrap]")
	}

	awsAccessKey := getEnv("AWS_ACCESS_KEY", getEnv("AWS_ACCESS_KEY_ID", "SOME_ACCESS_KEY_ID"))
	awsSecretKey := getEnv("AWS_SECRET_KEY", getEnv("AWS_SECRET_ACCESS_KEY", "SOME_SECRET_ACCESS_KEY"))
	awsSessionToken := getEnv("AWS_SESSION_TOKEN", os.Getenv("AWS_SECURITY_TOKEN"))

	bootstrapCmd.Env = append(os.Environ(),
		"AWS_LAMBDA_RUNTIME_API=127.0.0.1:"+runtimePort,
		"AWS_ACCESS_KEY_ID="+awsAccessKey,
		"AWS_SECRET_ACCESS_KEY="+awsSecretKey,
	)
	if len(awsSessionToken) > 0 {
		bootstrapCmd.Env = append(bootstrapCmd.Env, "AWS_SESSION_TOKEN="+awsSessionToken)
	}

	if stayOpen {
		bootstrapCmd.Stdout = io.MultiWriter(os.Stdout, &logsBuf)
		bootstrapCmd.Stderr = io.MultiWriter(os.Stderr, &logsBuf)
	} else {
		bootstrapCmd.Stdout = os.Stderr
		bootstrapCmd.Stderr = os.Stderr
	}
	if !noModifyLogs {
		bootstrapCmd.Stdout = &replaceWriter{writer: bootstrapCmd.Stdout, old: []byte("\r"), new: []byte("\n")}
		bootstrapCmd.Stderr = &replaceWriter{writer: bootstrapCmd.Stderr, old: []byte("\r"), new: []byte("\n")}
	}

	bootstrapCmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}

	if err := bootstrapCmd.Start(); err != nil {
		return err
	}

	bootstrapIsRunning = true
	bootstrapExitedGracefully = false

	// Get an initial read of memory, and update when we finish
	context.MaxMem, _ = allProcsMemoryInMb()

	go func() {
		bootstrapCmd.Wait()
		bootstrapIsRunning = false
		curState = "STATE_INIT"
		if !bootstrapExitedGracefully {
			// context may have changed, use curContext instead
			curContext.SetError(fmt.Errorf("Runtime exited without providing a reason"))
		}
	}()

	return nil
}

func exit(exitCode int) {
	killBootstrap()
	os.Exit(exitCode)
}

func reboot() {
	if noBootstrap {
		os.Exit(2)
	} else {
		killBootstrap()
	}
}

func killBootstrap() {
	bootstrapExitedGracefully = true
	if bootstrapCmd != nil && bootstrapCmd.Process != nil {
		syscall.Kill(-bootstrapCmd.Process.Pid, syscall.SIGKILL)
	}
}

func waitForContext(context *mockLambdaContext) {
	if err := ensureBootstrapIsRunning(context); err != nil {
		context.EndInvoke(err)
	} else {
		eventChan <- context
		<-context.Done
	}
}

func addAPIRoutes(r *chi.Mux) *chi.Mux {
	r.Post("/2015-03-31/functions/{function}/invocations", func(w http.ResponseWriter, r *http.Request) {
		context := newContext()

		if r.Header.Get("X-Amz-Invocation-Type") != "" {
			context.InvocationType = r.Header.Get("X-Amz-Invocation-Type")
		}
		if r.Header.Get("X-Amz-Client-Context") != "" {
			buf, err := base64.StdEncoding.DecodeString(r.Header.Get("X-Amz-Client-Context"))
			if err != nil {
				render.Render(w, r, &errResponse{
					HTTPStatusCode: 400,
					ErrorType:      "ClientContextDecodingError",
					ErrorMessage:   err.Error(),
				})
				return
			}
			context.ClientContext = string(buf)
		}
		if r.Header.Get("X-Amz-Log-Type") != "" {
			context.LogType = r.Header.Get("X-Amz-Log-Type")
		}

		if context.InvocationType == "DryRun" {
			w.Header().Set("x-amzn-RequestId", context.RequestID)
			w.Header().Set("x-amzn-Remapped-Content-Length", "0")
			w.WriteHeader(204)
			return
		}

		if body, err := ioutil.ReadAll(r.Body); err == nil {
			context.EventBody = string(body)
		} else {
			render.Render(w, r, &errResponse{
				HTTPStatusCode: 500,
				ErrorType:      "BodyReadError",
				ErrorMessage:   err.Error(),
			})
			return
		}
		r.Body.Close()

		if context.InvocationType == "Event" {
			w.Header().Set("x-amzn-RequestId", context.RequestID)
			w.Header().Set("x-amzn-Remapped-Content-Length", "0")
			w.Header().Set("X-Amzn-Trace-Id", context.XAmznTraceID)
			w.WriteHeader(202)
			go waitForContext(context)
			return
		}

		waitForContext(context)

		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("x-amzn-RequestId", context.RequestID)
		w.Header().Set("x-amzn-Remapped-Content-Length", "0")
		w.Header().Set("X-Amz-Executed-Version", context.Version)
		w.Header().Set("X-Amzn-Trace-Id", context.XAmznTraceID)

		if context.LogType == "Tail" {
			// We assume context.LogTail is already base64 encoded
			w.Header().Set("X-Amz-Log-Result", context.LogTail)
		}

		if context.Reply.Error != nil {
			errorType := "Unhandled"
			if context.ErrorType != "" {
				errorType = context.ErrorType
			}
			w.Header().Set("X-Amz-Function-Error", errorType)
		}

		// Lambda will usually return the payload instead of an error if the payload exists
		if len(context.Reply.Payload) > 0 {
			w.Header().Set("Content-Length", strconv.FormatInt(int64(len(context.Reply.Payload)), 10))
			w.Write(context.Reply.Payload)
			return
		}

		if payload, err := json.Marshal(context.Reply.Error); err == nil {
			w.Header().Set("Content-Length", strconv.FormatInt(int64(len(payload)), 10))
			w.Write(payload)
		} else {
			render.Render(w, r, &errResponse{
				HTTPStatusCode: 500,
				ErrorType:      "ErrorMarshalError",
				ErrorMessage:   err.Error(),
			})
		}
	})
	return r
}

func createRuntimeRouter() *chi.Mux {
	r := chi.NewRouter()

	r.Route("/2018-06-01", func(r chi.Router) {
		r.Get("/ping", func(w http.ResponseWriter, r *http.Request) {
			w.Write([]byte("pong"))
		})

		r.Route("/runtime", func(r chi.Router) {
			r.
				With(updateState("STATE_INIT_ERROR")).
				Post("/init/error", func(w http.ResponseWriter, r *http.Request) {
					debug("In /init/error")
					curContext = <-eventChan
					handleErrorRequest(w, r)
					curContext.EndInvoke(nil)
				})

			r.
				With(updateState("STATE_INVOKE_NEXT")).
				Get("/invocation/next", func(w http.ResponseWriter, r *http.Request) {
					debug("In /invocation/next")

					if curContext.Reply != nil {
						debug("Reply is not nil")
						curContext.EndInvoke(nil)
					}

					closeNotify := w.(http.CloseNotifier).CloseNotify()
					go func() {
						<-closeNotify
						debug("Connection closed, sending ignore event")
						eventChan <- &mockLambdaContext{Ignore: true}
					}()

					debug("Waiting for next event...")
					context := <-eventChan
					if context.Ignore {
						debug("Ignore event received, returning")
						w.Write([]byte{})
						return
					}
					curContext = context
					context.LogStartRequest()

					w.Header().Set("Content-Type", "application/json")
					w.Header().Set("Lambda-Runtime-Aws-Request-Id", context.RequestID)
					w.Header().Set("Lambda-Runtime-Deadline-Ms", strconv.FormatInt(context.Deadline().UnixNano()/int64(time.Millisecond), 10))
					w.Header().Set("Lambda-Runtime-Invoked-Function-Arn", context.InvokedFunctionArn)
					w.Header().Set("Lambda-Runtime-Trace-Id", context.XAmznTraceID)

					if context.ClientContext != "" {
						w.Header().Set("Lambda-Runtime-Client-Context", context.ClientContext)
					}
					if context.CognitoIdentity != "" {
						w.Header().Set("Lambda-Runtime-Cognito-Identity", context.CognitoIdentity)
					}

					if context.LogType != "" {
						w.Header().Set("Docker-Lambda-Log-Type", context.LogType)
					}

					w.Write([]byte(context.EventBody))
				})

			r.Route("/invocation/{requestID}", func(r chi.Router) {
				r.Use(awsRequestIDValidator)

				r.
					With(updateState("STATE_INVOKE_RESPONSE")).
					Post("/response", func(w http.ResponseWriter, r *http.Request) {
						body, err := ioutil.ReadAll(r.Body)
						if err != nil {
							render.Render(w, r, &errResponse{
								HTTPStatusCode: 500,
								ErrorType:      "BodyReadError", // Not sure what this would be in production?
								ErrorMessage:   err.Error(),
							})
							return
						}
						r.Body.Close()

						debug("Setting Reply in /response")
						curContext.Reply = &invokeResponse{Payload: body}

						curContext.SetLogTail(r)
						curContext.SetInitEnd(r)

						render.Render(w, r, acceptedResponse)
						w.(http.Flusher).Flush()
					})

				r.
					With(updateState("STATE_INVOKE_ERROR")).
					Post("/error", handleErrorRequest)
			})
		})
	})
	return r
}

func handleErrorRequest(w http.ResponseWriter, r *http.Request) {
	lambdaErr := &lambdaError{}
	response := acceptedResponse

	body, err := ioutil.ReadAll(r.Body)
	if err != nil || json.Unmarshal(body, lambdaErr) != nil {
		debug(fmt.Sprintf("Could not parse error body as JSON %v", err))
		debug(string(body))
		response = &statusResponse{Status: "InvalidErrorShape", HTTPStatusCode: 299}
		lambdaErr = &lambdaError{Message: "InvalidErrorShape"}
	}
	r.Body.Close()

	errorType := r.Header.Get("Lambda-Runtime-Function-Error-Type")
	if errorType != "" {
		curContext.ErrorType = errorType
	}

	// TODO: Figure out whether we want to handle Lambda-Runtime-Function-XRay-Error-Cause

	debug("Setting Reply in handleErrorRequest")
	debug(lambdaErr)

	curContext.Reply = &invokeResponse{Error: lambdaErr}

	curContext.SetLogTail(r)
	curContext.SetInitEnd(r)

	render.Render(w, r, response)
	w.(http.Flusher).Flush()
}

func updateState(nextState string) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if _, ok := transitions[nextState][curState]; !ok {
				render.Render(w, r, &errResponse{
					HTTPStatusCode: 403,
					ErrorType:      "InvalidStateTransition",
					ErrorMessage:   fmt.Sprintf("Transition from %s to %s is not allowed.", curState, nextState),
				})
				return
			}
			curState = nextState
			next.ServeHTTP(w, r)
		})
	}
}

func awsRequestIDValidator(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requestID := chi.URLParam(r, "requestID")

		if requestID != curContext.RequestID {
			render.Render(w, r, &errResponse{
				HTTPStatusCode: 400,
				ErrorType:      "InvalidRequestID",
				ErrorMessage:   "Invalid request ID",
			})
			return
		}

		ctx := context.WithValue(r.Context(), keyRequestID, requestID)

		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

type statusResponse struct {
	HTTPStatusCode int    `json:"-"`
	Status         string `json:"status"`
}

func (sr *statusResponse) Render(w http.ResponseWriter, r *http.Request) error {
	render.Status(r, sr.HTTPStatusCode)
	return nil
}

type errResponse struct {
	HTTPStatusCode int    `json:"-"`
	ErrorType      string `json:"errorType,omitempty"`
	ErrorMessage   string `json:"errorMessage"`
}

func (e *errResponse) Render(w http.ResponseWriter, r *http.Request) error {
	render.Status(r, e.HTTPStatusCode)
	return nil
}

func renderJSON(w http.ResponseWriter, r *http.Request, v interface{}) {
	buf := &bytes.Buffer{}
	enc := json.NewEncoder(buf)
	enc.SetEscapeHTML(true)
	if err := enc.Encode(v); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	if status, ok := r.Context().Value(render.StatusCtxKey).(int); ok {
		w.WriteHeader(status)
	}
	w.Write(buf.Bytes())
}

func getEnv(key, fallback string) string {
	value := os.Getenv(key)
	if value != "" {
		return value
	}
	return fallback
}

func fakeGUID() string {
	randBuf := make([]byte, 16)
	rand.Read(randBuf)

	hexBuf := make([]byte, hex.EncodedLen(len(randBuf))+4)

	hex.Encode(hexBuf[0:8], randBuf[0:4])
	hexBuf[8] = '-'
	hex.Encode(hexBuf[9:13], randBuf[4:6])
	hexBuf[13] = '-'
	hex.Encode(hexBuf[14:18], randBuf[6:8])
	hexBuf[18] = '-'
	hex.Encode(hexBuf[19:23], randBuf[8:10])
	hexBuf[23] = '-'
	hex.Encode(hexBuf[24:], randBuf[10:])

	hexBuf[14] = '1' // Make it look like a v1 guid

	return string(hexBuf)
}

func logStreamName(version string) string {
	randBuf := make([]byte, 16)
	rand.Read(randBuf)

	hexBuf := make([]byte, hex.EncodedLen(len(randBuf)))
	hex.Encode(hexBuf, randBuf)

	return time.Now().Format("2006/01/02") + "/[" + version + "]" + string(hexBuf)
}

func arn(region string, accountID string, fnName string) string {
	nonDigit := regexp.MustCompile(`[^\d]`)
	return "arn:aws:lambda:" + region + ":" + nonDigit.ReplaceAllString(accountID, "") + ":function:" + fnName
}

func allProcsMemoryInMb() (uint64, error) {
	files, err := ioutil.ReadDir("/proc/")
	if err != nil {
		return 0, err
	}
	totalMem := uint64(0)
	for _, file := range files {
		if pid, err := strconv.Atoi(file.Name()); err == nil {
			pidMem, err := calculateMemoryInKb(pid)
			if err != nil {
				return 0, err
			}
			totalMem += pidMem
		}
	}
	return totalMem / 1024, nil
}

// Thanks to https://stackoverflow.com/a/31881979
func calculateMemoryInKb(pid int) (uint64, error) {
	f, err := os.Open(fmt.Sprintf("/proc/%d/smaps", pid))
	if err != nil {
		return 0, err
	}
	defer f.Close()

	res := uint64(0)
	pfx := []byte("Pss:")
	r := bufio.NewScanner(f)
	for r.Scan() {
		line := r.Bytes()
		if bytes.HasPrefix(line, pfx) {
			var size uint64
			_, err := fmt.Sscanf(string(line[4:]), "%d", &size)
			if err != nil {
				return 0, err
			}
			res += size
		}
	}
	if err := r.Err(); err != nil {
		return 0, err
	}

	return res, nil
}

func getErrorType(err interface{}) string {
	errorType := reflect.TypeOf(err)
	if errorType.Kind() == reflect.Ptr {
		return errorType.Elem().Name()
	}
	return errorType.Name()
}

func debug(v ...interface{}) {
	if logDebug {
		log.Println(v...)
	}
}

func systemLog(msg string) {
	fmt.Fprintln(os.Stderr, "\033[32m"+msg+"\033[0m")
}

type exitError struct {
	err     error
	context *mockLambdaContext
}

func (e *exitError) Error() string {
	return fmt.Sprintf("RequestId: %s Error: %s", e.context.RequestID, e.err.Error())
}

type lambdaError struct {
	Type       string                `json:"errorType,omitempty"`
	Message    string                `json:"errorMessage"`
	StackTrace []*json.RawMessage    `json:"stackTrace,omitempty"`
	Cause      *lambdaError          `json:"cause,omitempty"`
}

type mockLambdaContext struct {
	RequestID          string
	EventBody          string
	FnName             string
	Version            string
	MemSize            string
	Timeout            string
	Region             string
	AccountID          string
	XAmznTraceID       string
	InvokedFunctionArn string
	ClientContext      string
	CognitoIdentity    string
	Start              time.Time
	InvokeWait         time.Time
	InitEnd            time.Time
	TimeoutDuration    time.Duration
	Reply              *invokeResponse
	Done               chan bool
	MaxMem             uint64
	InvocationType     string
	LogType            string
	LogTail            string // base64 encoded tail, no greater than 4096 bytes
	ErrorType          string // Unhandled vs Handled
	Ended              bool
	Ignore             bool
}

func (mc *mockLambdaContext) ParseTimeout() {
	timeoutDuration, err := time.ParseDuration(mc.Timeout + "s")
	if err != nil {
		panic(err)
	}
	mc.TimeoutDuration = timeoutDuration
}

func (mc *mockLambdaContext) ParseFunctionArn() {
	mc.InvokedFunctionArn = getEnv("AWS_LAMBDA_FUNCTION_INVOKED_ARN", arn(mc.Region, mc.AccountID, mc.FnName))
}

func (mc *mockLambdaContext) Deadline() time.Time {
	return mc.Start.Add(mc.TimeoutDuration)
}

func (mc *mockLambdaContext) HasExpired() bool {
	return time.Now().After(mc.Deadline())
}

func (mc *mockLambdaContext) TimeoutErr() error {
	return fmt.Errorf("%s %s Task timed out after %s.00 seconds", time.Now().Format("2006-01-02T15:04:05.999Z"),
		mc.RequestID, mc.Timeout)
}

func (mc *mockLambdaContext) SetLogTail(r *http.Request) {
	defer logsBuf.Reset()

	mc.LogTail = ""

	if mc.LogType != "Tail" {
		return
	}
	if noBootstrap {
		mc.LogTail = r.Header.Get("Docker-Lambda-Log-Result")
		return
	}

	// This is very annoying but seems to be necessary to ensure we get all the stdout/stderr from the subprocess
	time.Sleep(1 * time.Millisecond)

	logs := logsBuf.Bytes()

	if len(logs) == 0 {
		return
	}

	if len(logs) > 4096 {
		logs = logs[len(logs)-4096:]
	}
	mc.LogTail = base64.StdEncoding.EncodeToString(logs)
}

func (mc *mockLambdaContext) SetInitEnd(r *http.Request) {
	invokeWaitHeader := r.Header.Get("Docker-Lambda-Invoke-Wait")
	if invokeWaitHeader != "" {
		invokeWaitMs, err := strconv.ParseInt(invokeWaitHeader, 10, 64)
		if err != nil {
			log.Fatal(fmt.Errorf("Could not parse Docker-Lambda-Invoke-Wait header as int. Error: %s", err))
			return
		}
		mc.InvokeWait = time.Unix(0, invokeWaitMs*int64(time.Millisecond))
	}
	initEndHeader := r.Header.Get("Docker-Lambda-Init-End")
	if initEndHeader != "" {
		initEndMs, err := strconv.ParseInt(initEndHeader, 10, 64)
		if err != nil {
			log.Fatal(fmt.Errorf("Could not parse Docker-Lambda-Init-End header as int. Error: %s", err))
			return
		}
		mc.InitEnd = time.Unix(0, initEndMs*int64(time.Millisecond))
	}
}

func (mc *mockLambdaContext) SetError(exitErr error) {
	err := &exitError{err: exitErr, context: mc}
	responseErr := lambdaError{
		Message: err.Error(),
		Type:    getErrorType(err),
	}
	if responseErr.Type == "errorString" {
		responseErr.Type = ""
		if responseErr.Message == "unexpected EOF" {
			responseErr.Message = "RequestId: " + mc.RequestID + " Process exited before completing request"
		}
	} else if responseErr.Type == "ExitError" {
		responseErr.Type = "Runtime.ExitError" // XXX: Hack to add 'Runtime.' to error type
	}
	debug("Setting Reply in SetError")
	debug(responseErr)
	if mc.Reply == nil {
		mc.Reply = &invokeResponse{Error: &responseErr}
	} else {
		mc.Reply.Error = &responseErr
	}
}

func (mc *mockLambdaContext) EndInvoke(exitErr error) {
	debug("EndInvoke()")
	if mc.Ended {
		return
	}
	mc.Ended = true
	if exitErr != nil {
		debug(exitErr)
		mc.SetError(exitErr)
	} else if (mc.Reply == nil || mc.Reply.Error == nil) && mc.HasExpired() {
		mc.Reply = &invokeResponse{
			Error: &lambdaError{
				Message: mc.TimeoutErr().Error(),
			},
		}
	}
	if mc.InitEnd.IsZero() {
		mc.LogStartRequest()
	}

	mc.LogEndRequest()

	if exitErr == nil {
		mc.Done <- true
	}
}

func (mc *mockLambdaContext) LogStartRequest() {
	mc.InitEnd = time.Now()
	systemLog("START RequestId: " + mc.RequestID + " Version: " + mc.Version)
}

func (mc *mockLambdaContext) LogEndRequest() {
	maxMem, _ := allProcsMemoryInMb()
	if maxMem > mc.MaxMem {
		mc.MaxMem = maxMem
	}

	diffMs := math.Min(float64(time.Now().Sub(mc.InitEnd).Nanoseconds()),
		float64(mc.TimeoutDuration.Nanoseconds())) / float64(time.Millisecond)

	initStr := ""
	if !initPrinted {
		proc1stat, _ := os.Stat("/proc/1")
		processStartTime := proc1stat.ModTime()
		if mc.InvokeWait.IsZero() {
			mc.InvokeWait = serverInitEnd
		}
		if mc.InvokeWait.Before(processStartTime) {
			mc.InvokeWait = processStartTime
		}
		initDiffNs := mc.InvokeWait.Sub(proc1stat.ModTime()).Nanoseconds() + mc.InitEnd.Sub(mc.Start).Nanoseconds()
		initDiffMs := math.Min(float64(initDiffNs), float64(mc.TimeoutDuration.Nanoseconds())) / float64(time.Millisecond)
		initStr = fmt.Sprintf("Init Duration: %.2f ms\t", initDiffMs)
		initPrinted = true
	}

	systemLog("END RequestId: " + mc.RequestID)
	systemLog(fmt.Sprintf(
		"REPORT RequestId: %s\t"+
			initStr+
			"Duration: %.2f ms\t"+
			"Billed Duration: %.f ms\t"+
			"Memory Size: %s MB\t"+
			"Max Memory Used: %d MB\t",
		mc.RequestID, diffMs, math.Ceil(diffMs/100)*100, mc.MemSize, mc.MaxMem))
}

type invokeResponse struct {
	Payload []byte
	Error   *lambdaError
}

type replaceWriter struct {
	writer io.Writer
	old    []byte
	new    []byte
}

func (r *replaceWriter) Write(p []byte) (n int, err error) {
	return r.writer.Write(bytes.ReplaceAll(p, r.old, r.new))
}
