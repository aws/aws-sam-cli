package cloudformation

import (
	"encoding/json"

	"github.com/mitchellh/mapstructure"
)

// AWSServerlessFunction_StringOrListOfString is a helper struct that can hold either a String or String value
type AWSServerlessFunction_StringOrListOfString struct {
	String *string

	StringArray *[]string
}

func (r AWSServerlessFunction_StringOrListOfString) value() interface{} {

	if r.String != nil {
		return r.String
	}

	if r.String != nil {
		return r.String
	}

	return nil

}

func (r *AWSServerlessFunction_StringOrListOfString) MarshalJSON() ([]byte, error) {
	return json.Marshal(r.value())
}

// Hook into the marshaller
func (r *AWSServerlessFunction_StringOrListOfString) UnmarshalJSON(b []byte) error {

	// Unmarshal into interface{} to check it's type
	var typecheck interface{}
	if err := json.Unmarshal(b, &typecheck); err != nil {
		return err
	}

	switch val := typecheck.(type) {

	case string:
		r.String = &val

	case []string:
		r.StringArray = &val

	case map[string]interface{}:

	case []interface{}:

		mapstructure.Decode(val, &r.StringArray)

	}

	return nil
}
