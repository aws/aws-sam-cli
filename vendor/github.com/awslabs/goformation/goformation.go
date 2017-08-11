package goformation

import (
	"io"
	"io/ioutil"
	"os"
	"path/filepath"

	. "github.com/awslabs/goformation/resources"
	"github.com/awslabs/goformation/util"
	"github.com/pkg/errors"
)

// Open opens a file given and parses it, returning the result
// In the return objects there's also the logs
func Open(filename string) (Template, map[string][]string, []error) {
	util.LogInfo(-1, "GoFormation", "Opening file %s", filename)

	fp, err := filepath.Abs(filename)
	if err != nil {
		return nil, nil, []error{util.ErrFailedToReadTemplate}
	}

	f, err := os.Open(fp)
	if err != nil {
		return nil, nil, []error{util.ErrFailedToReadTemplate}
	}

	return read(f)

}

func read(input io.Reader) (Template, map[string][]string, []error) {
	// Read data
	data, err := ioutil.ReadAll(input)
	if err != nil {
		return nil, nil, []error{util.ErrFailedToReadTemplate}
	}

	return Parse(data)
}

// Parse receives the contents of a template and parses it.
// After parsing, it returns you the parsed template, and the log for the operation.
func Parse(input []byte) (Template, map[string][]string, []error) {
	util.LogInfo(-1, "GoFormation", "Parsing process started")

	util.LogInfo(-1, "GoFormation", "Unmarshalling template")
	unmarshalledTemplate, unmarshallingError := unmarshal(input)
	if unmarshallingError != nil {
		util.LogError(-1, "GoFormation", "Failed to unmarshal the template")
		errorMessage := util.GetUnmarshallingErrorMessage(unmarshallingError)
		return nil, util.GetLogs(), []error{errors.New(errorMessage)}
	}
	util.LogInfo(-1, "GoFormation", "Template unmarshalled successfully")

	util.LogInfo(-1, "GoFormation", "Scaffolding the template")
	scaffoldedTemplate, scaffoldingErrors := scaffold(unmarshalledTemplate)
	if scaffoldingErrors != nil && len(scaffoldingErrors) > 0 {

		parsedScaffoldingErrors := make([]error, len(scaffoldingErrors))
		for i, scaffoldingError := range scaffoldingErrors {
			errorMessage := util.GetFinalErrorMessage(scaffoldingError)
			parsedError := errors.New(errorMessage)
			parsedScaffoldingErrors[i] = parsedError
		}

		util.LogError(-1, "GoFormation", "Failed to scaffold the template due to an error")
		return nil, util.GetLogs(), parsedScaffoldingErrors
	}

	processedTemplate, postProcessingError := postProcess(scaffoldedTemplate)
	if postProcessingError != nil {
		util.LogError(-1, "GoFormation", "Failed to process template")
		return nil, util.GetLogs(), []error{postProcessingError}
	}

	return processedTemplate, util.GetLogs(), nil
}
