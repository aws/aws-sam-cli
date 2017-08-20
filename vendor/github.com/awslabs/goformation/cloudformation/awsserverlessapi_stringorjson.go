package cloudformation

import (
	"encoding/json"
)

// AWSServerlessApi_StringOrJson is a helper struct that can hold either a String or Json value
type AWSServerlessApi_StringOrJson struct {
	String *string
	Json   *interface{}
}

func (r AWSServerlessApi_StringOrJson) value() interface{} {

	if r.String != nil {
		return r.String
	}

	if r.Json != nil {
		return r.Json
	}

	return nil

}

func (r *AWSServerlessApi_StringOrJson) MarshalJSON() ([]byte, error) {
	return json.Marshal(r.value())
}

// Hook into the marshaller
func (r *AWSServerlessApi_StringOrJson) UnmarshalJSON(b []byte) error {

	// Unmarshal into interface{} to check it's type
	var typecheck interface{}
	if err := json.Unmarshal(b, &typecheck); err != nil {
		return err
	}

	switch val := typecheck.(type) {

	case string:
		r.String = &val

	case interface{}:
		r.Json = &val

	case map[string]interface{}:

	case []interface{}:

	}

	return nil
}
