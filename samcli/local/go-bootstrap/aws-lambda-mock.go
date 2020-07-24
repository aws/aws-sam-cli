package main

import (
	"bytes"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"io/ioutil"
	"log"
	"math/rand"
	"net"
	"net/http"
	"net/rpc"
	"net/url"
	"os"
	"os/exec"
	"os/signal"
	"reflect"
	"regexp"
	"strconv"
	"syscall"
	"time"

	"github.com/aws/aws-lambda-go/lambda/messages"
)

var apiBase = "http://127.0.0.1:9001/2018-06-01"

func main() {
	rand.Seed(time.Now().UTC().UnixNano())

	debugMode := flag.Bool("debug", false, "enables delve debugging")
	delvePath := flag.String("delvePath", "/tmp/lambci_debug_files/dlv", "path to delve")
	delvePort := flag.String("delvePort", "5985", "port to start delve server on")
	delveAPI := flag.String("delveAPI", "1", "delve api version")
	flag.Parse()
	positionalArgs := flag.Args()

	var handler string
	if len(positionalArgs) > 0 {
		handler = positionalArgs[0]
	} else {
		handler = getEnv("AWS_LAMBDA_FUNCTION_HANDLER", getEnv("_HANDLER", "handler"))
	}

	var eventBody string
	if len(positionalArgs) > 1 {
		eventBody = positionalArgs[1]
	} else {
		eventBody = os.Getenv("AWS_LAMBDA_EVENT_BODY")
		if eventBody == "" {
			if os.Getenv("DOCKER_LAMBDA_USE_STDIN") != "" {
				stdin, _ := ioutil.ReadAll(os.Stdin)
				eventBody = string(stdin)
			} else {
				eventBody = "{}"
			}
		}
	}

	stayOpen := os.Getenv("DOCKER_LAMBDA_STAY_OPEN") != ""

	mockContext := &mockLambdaContext{
		RequestID: fakeGUID(),
		EventBody: eventBody,
		FnName:    getEnv("AWS_LAMBDA_FUNCTION_NAME", "test"),
		Version:   getEnv("AWS_LAMBDA_FUNCTION_VERSION", "$LATEST"),
		MemSize:   getEnv("AWS_LAMBDA_FUNCTION_MEMORY_SIZE", "1536"),
		Timeout:   getEnv("AWS_LAMBDA_FUNCTION_TIMEOUT", "300"),
		Region:    getEnv("AWS_REGION", getEnv("AWS_DEFAULT_REGION", "us-east-1")),
		AccountID: getEnv("AWS_ACCOUNT_ID", strconv.FormatInt(int64(rand.Int31()), 10)),
		Start:     time.Now(),
	}
	mockContext.ParseTimeout()

	awsAccessKey := getEnv("AWS_ACCESS_KEY", getEnv("AWS_ACCESS_KEY_ID", "SOME_ACCESS_KEY_ID"))
	awsSecretKey := getEnv("AWS_SECRET_KEY", getEnv("AWS_SECRET_ACCESS_KEY", "SOME_SECRET_ACCESS_KEY"))
	awsSessionToken := getEnv("AWS_SESSION_TOKEN", os.Getenv("AWS_SECURITY_TOKEN"))
	port := getEnv("_LAMBDA_SERVER_PORT", "54321")

	os.Setenv("AWS_LAMBDA_FUNCTION_NAME", mockContext.FnName)
	os.Setenv("AWS_LAMBDA_FUNCTION_VERSION", mockContext.Version)
	os.Setenv("AWS_LAMBDA_FUNCTION_MEMORY_SIZE", mockContext.MemSize)
	os.Setenv("AWS_LAMBDA_LOG_GROUP_NAME", "/aws/lambda/"+mockContext.FnName)
	os.Setenv("AWS_LAMBDA_LOG_STREAM_NAME", logStreamName(mockContext.Version))
	os.Setenv("AWS_REGION", mockContext.Region)
	os.Setenv("AWS_DEFAULT_REGION", mockContext.Region)
	os.Setenv("_HANDLER", handler)

	var err error
	var errored bool

	var mockServerCmd = exec.Command("/var/rapid/init") // <-- This is our mount point for RAPID server.
	mockServerCmd.Env = append(os.Environ(),
		"DOCKER_LAMBDA_NO_BOOTSTRAP=1",
		"DOCKER_LAMBDA_USE_STDIN=1",
	)
	mockServerCmd.Stdout = os.Stdout
	mockServerCmd.Stderr = os.Stderr
	stdin, _ := mockServerCmd.StdinPipe()
	if err = mockServerCmd.Start(); err != nil {
		log.Fatalf("Error starting mock server: %s", err.Error())
		return
	}
	stdin.Write([]byte(eventBody))
	stdin.Close()

	defer mockServerCmd.Wait()

	pingTimeout := time.Now().Add(1 * time.Second)

	for {
		resp, err := http.Get(apiBase + "/ping")
		if err != nil {
			if time.Now().After(pingTimeout) {
				log.Fatal("Mock server did not start in time")
				return
			}
			time.Sleep(5 * time.Millisecond)
			continue
		}
		if resp.StatusCode != 200 {
			log.Fatal("Non 200 status code from local server")
			return
		}
		resp.Body.Close()
		break
	}

	var cmd *exec.Cmd
	if *debugMode == true {
		delveArgs := []string{
			"--listen=:" + *delvePort,
			"--headless=true",
			"--api-version=" + *delveAPI,
			"--log",
			"exec",
			"/var/task/" + handler,
		}
		cmd = exec.Command(*delvePath, delveArgs...)
	} else {
		cmd = exec.Command("/var/task/" + handler)
	}

	cmd.Env = append(os.Environ(),
		"_LAMBDA_SERVER_PORT="+port,
		"AWS_ACCESS_KEY="+awsAccessKey,
		"AWS_ACCESS_KEY_ID="+awsAccessKey,
		"AWS_SECRET_KEY="+awsSecretKey,
		"AWS_SECRET_ACCESS_KEY="+awsSecretKey,
	)
	if len(awsSessionToken) > 0 {
		cmd.Env = append(cmd.Env,
			"AWS_SESSION_TOKEN="+awsSessionToken,
			"AWS_SECURITY_TOKEN="+awsSessionToken,
		)
	}

	var logsBuf bytes.Buffer

	if stayOpen {
		cmd.Stdout = io.MultiWriter(os.Stdout, &logsBuf)
		cmd.Stderr = io.MultiWriter(os.Stderr, &logsBuf)
	} else {
		cmd.Stdout = os.Stderr
		cmd.Stderr = os.Stderr
	}

	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}

	if err = cmd.Start(); err != nil {
		defer abortInit(mockContext, err)
		return
	}

	defer syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)

	var conn net.Conn
	for {
		conn, err = net.Dial("tcp", ":"+port)
		if mockContext.HasExpired() {
			defer abortInit(mockContext, mockContext.TimeoutErr())
			return
		}
		if err == nil {
			break
		}
		if oerr, ok := err.(*net.OpError); ok {
			// Connection refused, try again
			if oerr.Op == "dial" && oerr.Net == "tcp" {
				time.Sleep(5 * time.Millisecond)
				continue
			}
		}
		defer abortInit(mockContext, err)
		return
	}

	client := rpc.NewClient(conn)

	for {
		err = client.Call("Function.Ping", messages.PingRequest{}, &messages.PingResponse{})
		if mockContext.HasExpired() {
			defer abortInit(mockContext, mockContext.TimeoutErr())
			return
		}
		if err == nil {
			break
		}
		time.Sleep(5 * time.Millisecond)
	}

	sighupReceiver := make(chan os.Signal, 1)
	signal.Notify(sighupReceiver, syscall.SIGHUP)
	go func() {
		<-sighupReceiver
		fmt.Fprintln(os.Stderr, ("SIGHUP received, exiting runtime..."))
		os.Exit(2)
	}()

	var initEndSent bool
	var invoked bool
	var receivedInvokeAt time.Time

	for {
		if !invoked {
			receivedInvokeAt = time.Now()
			invoked = true
		} else {
			logsBuf.Reset()
		}

		resp, err := http.Get(apiBase + "/runtime/invocation/next")
		if err != nil {
			if uerr, ok := err.(*url.Error); ok {
				if uerr.Unwrap().Error() == "EOF" {
					if stayOpen {
						os.Exit(2)
					} else if errored {
						os.Exit(1)
					} else {
						os.Exit(0)
					}
					return
				}
			}
			log.Fatal(err)
			return
		}
		if resp.StatusCode != 200 {
			log.Fatal("Non 200 status code from local server")
			return
		}
		body, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			log.Fatal(err)
			return
		}
		resp.Body.Close()

		deadlineMs, _ := strconv.ParseInt(resp.Header.Get("Lambda-Runtime-Deadline-Ms"), 10, 64)
		deadline := time.Unix(0, deadlineMs*int64(time.Millisecond))

		var invokeRequest = &messages.InvokeRequest{
			Payload:            body,
			RequestId:          resp.Header.Get("Lambda-Runtime-Aws-Request-Id"),
			XAmznTraceId:       resp.Header.Get("Lambda-Runtime-Trace-Id"),
			InvokedFunctionArn: resp.Header.Get("Lambda-Runtime-Invoked-Function-Arn"),
			Deadline: messages.InvokeRequest_Timestamp{
				Seconds: deadline.Unix(),
				Nanos:   int64(deadline.Nanosecond()),
			},
			ClientContext: []byte(resp.Header.Get("Lambda-Runtime-Client-Context")),
		}

		cognitoIdentityHeader := []byte(resp.Header.Get("Lambda-Runtime-Cognito-Identity"))
		if len(cognitoIdentityHeader) > 0 {
			var identityObj *cognitoIdentity
			err := json.Unmarshal(cognitoIdentityHeader, &identityObj)
			if err != nil {
				log.Fatal(err)
				return
			}
			invokeRequest.CognitoIdentityId = identityObj.IdentityID
			invokeRequest.CognitoIdentityPoolId = identityObj.IdentityPoolID
		}

		logTail := resp.Header.Get("Docker-Lambda-Log-Type") == "Tail"

		var initEnd time.Time
		if !initEndSent {
			initEnd = time.Now()
		}

		errored = false

		var reply *messages.InvokeResponse
		err = client.Call("Function.Invoke", invokeRequest, &reply)

		suffix := "/response"
		payload := reply.Payload
		if err != nil || reply.Error != nil {
			errored = true
			suffix = "/error"
			var lambdaErr lambdaError
			if err != nil {
				lambdaErr = toLambdaError(mockContext, err)
			} else if reply.Error != nil {
				lambdaErr = convertInvokeResponseError(reply.Error)
			}
			payload, _ = json.Marshal(lambdaErr)
		}
		req, err := http.NewRequest("POST", apiBase+"/runtime/invocation/"+invokeRequest.RequestId+suffix, bytes.NewBuffer(payload))
		if err != nil {
			log.Fatal(err)
			return
		}

		if logTail {
			// This is very annoying but seems to be necessary to ensure we get all the stdout/stderr from the process
			time.Sleep(1 * time.Millisecond)

			logs := logsBuf.Bytes()

			if len(logs) > 0 {
				if len(logs) > 4096 {
					logs = logs[len(logs)-4096:]
				}
				req.Header.Add("Docker-Lambda-Log-Result", base64.StdEncoding.EncodeToString(logs))
			}
		}

		if !initEndSent {
			req.Header.Add("Docker-Lambda-Invoke-Wait", strconv.FormatInt(receivedInvokeAt.UnixNano()/int64(time.Millisecond), 10))
			req.Header.Add("Docker-Lambda-Init-End", strconv.FormatInt(initEnd.UnixNano()/int64(time.Millisecond), 10))
			initEndSent = true
		}

		resp, err = http.DefaultClient.Do(req)
		if err != nil {
			log.Fatal(err)
			return
		}
		if resp.StatusCode != 202 {
			log.Printf("Non 202 status code from local server: %d\n", resp.StatusCode)
			body, _ = ioutil.ReadAll(resp.Body)
			log.Println(string(body))
			log.Println("When trying to send payload:")
			log.Println(string(payload))
			if resp.StatusCode >= 300 {
				os.Exit(1)
				return
			}
		}
		resp.Body.Close()
	}
}

func systemLog(msg string) {
	fmt.Fprintln(os.Stderr, "\033[32m"+"####"+msg+"\033[0m")
}

func abortInit(mockContext *mockLambdaContext, err error) {
	lambdaErr := toLambdaError(mockContext, err)
	jsonBytes, _ := json.Marshal(lambdaErr)
	resp, err := http.Post(apiBase+"/runtime/init/error", "application/json", bytes.NewBuffer(jsonBytes))
	if err != nil {
		log.Fatal(err)
		return
	}
	resp.Body.Close()
}

func toLambdaError(mockContext *mockLambdaContext, exitErr error) lambdaError {
	err := &exitError{err: exitErr, context: mockContext}
	responseErr := lambdaError{
		Message: err.Error(),
		Type:    getErrorType(err),
	}
	if responseErr.Type == "errorString" {
		responseErr.Type = ""
		if responseErr.Message == "unexpected EOF" {
			responseErr.Message = "RequestId: " + mockContext.RequestID + " Process exited before completing request"
		}
	} else if responseErr.Type == "ExitError" {
		responseErr.Type = "Runtime.ExitError" // XXX: Hack to add 'Runtime.' to error type
	}
	return responseErr
}

func convertInvokeResponseError(err *messages.InvokeResponse_Error) lambdaError {
	var stackTrace []string
	for _, v := range err.StackTrace {
		stackTrace = append(stackTrace, fmt.Sprintf("%s:%d %s", v.Path, v.Line, v.Label))
	}
	return lambdaError{
		Message:    err.Message,
		Type:       err.Type,
		StackTrace: stackTrace,
	}
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

func getErrorType(err interface{}) string {
	errorType := reflect.TypeOf(err)
	if errorType.Kind() == reflect.Ptr {
		return errorType.Elem().Name()
	}
	return errorType.Name()
}

type lambdaError struct {
	Message    string   `json:"errorMessage"`
	Type       string   `json:"errorType,omitempty"`
	StackTrace []string `json:"stackTrace,omitempty"`
}

type exitError struct {
	err     error
	context *mockLambdaContext
}

func (e *exitError) Error() string {
	return fmt.Sprintf("RequestId: %s Error: %s", e.context.RequestID, e.err.Error())
}

type mockLambdaContext struct {
	RequestID       string
	EventBody       string
	FnName          string
	Version         string
	MemSize         string
	Timeout         string
	Region          string
	AccountID       string
	Start           time.Time
	TimeoutDuration time.Duration
}

func (mc *mockLambdaContext) ParseTimeout() {
	timeoutDuration, err := time.ParseDuration(mc.Timeout + "s")
	if err != nil {
		panic(err)
	}
	mc.TimeoutDuration = timeoutDuration
}

func (mc *mockLambdaContext) Deadline() time.Time {
	return mc.Start.Add(mc.TimeoutDuration)
}

func (mc *mockLambdaContext) HasExpired() bool {
	return time.Now().After(mc.Deadline())
}

func (mc *mockLambdaContext) Request() *messages.InvokeRequest {
	return &messages.InvokeRequest{
		Payload:            []byte(mc.EventBody),
		RequestId:          mc.RequestID,
		XAmznTraceId:       getEnv("_X_AMZN_TRACE_ID", ""),
		InvokedFunctionArn: getEnv("AWS_LAMBDA_FUNCTION_INVOKED_ARN", arn(mc.Region, mc.AccountID, mc.FnName)),
		Deadline: messages.InvokeRequest_Timestamp{
			Seconds: mc.Deadline().Unix(),
			Nanos:   int64(mc.Deadline().Nanosecond()),
		},
	}
}

func (mc *mockLambdaContext) TimeoutErr() error {
	return fmt.Errorf("%s %s Task timed out after %s.00 seconds", time.Now().Format("2006-01-02T15:04:05.999Z"),
		mc.RequestID, mc.Timeout)
}

type cognitoIdentity struct {
	IdentityID     string `json:"identity_id,omitempty"`
	IdentityPoolID string `json:"identity_pool_id,omitempty"`
}
