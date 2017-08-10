package util

import (
	"fmt"
	"strconv"
	"strings"

	"regexp"

	"github.com/pkg/errors"
)

var (
	// ErrFailedToReadTemplate is thrown when the provided template
	// file cannot be opened (e.g. filesystem permissions/non-existant)
	ErrFailedToReadTemplate = errors.New("failed to open template")

	// ErrFailedToParseTemplate is thrown when the provided template
	// is not valid (e.g. bad YAML syntax)
	ErrFailedToParseTemplate = errors.New("ERROR: Failed to parse template")

	// ErrUnsupportedTemplateVersion is thrown when trying to parse a
	// template that has a version of AWS SAM we haven't seen before
	ErrUnsupportedTemplateVersion = errors.New("unsupported template version")

	// ErrFailedToUnmarshalTemplate is thrown when the unmarshalling process fails.
	ErrFailedToUnmarshalTemplate = errors.New("ERROR: Failed to unmarshal template")

	// ErrFailedToScaffoldTemplate is thrown when the scaffolding process fails.
	ErrFailedToScaffoldTemplate = errors.New("ERROR: Failed to scaffold template")
)

var yamlErrorRegex = regexp.MustCompile(`yaml:\s+line\s+(\d+):(.+)`)

// GetUnmarshallingErrorMessage Converts an error from the unmarshaller into a common format.
func GetUnmarshallingErrorMessage(error error) string {
	errorMessage := error.Error()
	if !yamlErrorRegex.MatchString(errorMessage) {
		return errorMessage
	}

	parsedErrorMessage := yamlErrorRegex.FindStringSubmatch(errorMessage)

	lineNumber := 0
	lineNumber, err := strconv.Atoi(parsedErrorMessage[1])
	if err != nil {
		lineNumber = 0
	}

	innerErrorMessage := parsedErrorMessage[2]

	// Let's have a nicer error message
	if innerErrorMessage == " did not find expected key" {
		lineNumber++
		innerErrorMessage = "Invalid indentation in template"
	}

	finalErrorMessage := fmt.Sprintf("ERROR: %s (line: %d; col: 0)", innerErrorMessage, lineNumber)
	return finalErrorMessage
}

var unvalidLineRegex = regexp.MustCompile(`\(line: \-1:`)
var trimMessageRegex = regexp.MustCompile(`:\s$`)
var errorSubstitutionRegex = regexp.MustCompile(`###`)

func GetFinalErrorMessage(error error) string {
	finalErrorMessage := "ERROR: "
	parsedMessage := recursivelyLookupErrorMessage(error, "")

	trimmedMessage := trimMessageRegex.ReplaceAllString(parsedMessage, "")
	finalErrorMessage += trimmedMessage

	return finalErrorMessage
}

func recursivelyLookupErrorMessage(error error, previousMessage string) string {
	errorMsg := error.Error()
	if errorMsg == previousMessage {
		return errorMsg
	}

	errorCause := errors.Cause(error)
	causeMessage := errorCause.Error()
	if causeMessage == errorMsg {
		return errorMsg
	}

	previousStack := recursivelyLookupErrorMessage(errorCause, errorMsg)

	matchErrorMessage := ": " + previousStack
	originalMessage := strings.Replace(errorMsg, matchErrorMessage, "", 1)

	var messageToReturn = originalMessage
	if unvalidLineRegex.MatchString(originalMessage) {
		messageToReturn = previousStack
	} else if len(originalMessage) < 3 {
		messageToReturn = previousStack
	}

	var parsedMessage = messageToReturn
	if errorSubstitutionRegex.MatchString(messageToReturn) {
		parsedMessage = errorSubstitutionRegex.ReplaceAllString(messageToReturn, previousStack)
	}

	return parsedMessage
}
