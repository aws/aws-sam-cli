package cloudformation

import (
	"encoding/json"

	"github.com/mitchellh/mapstructure"
)

// AWSServerlessFunction_StringOrIAMPolicyDocumentOrListOfStringOrListOfIAMPolicyDocument is a helper struct that can hold either a String, String, IAMPolicyDocument, or IAMPolicyDocument value
type AWSServerlessFunction_StringOrIAMPolicyDocumentOrListOfStringOrListOfIAMPolicyDocument struct {
	String *string

	StringArray *[]string

	IAMPolicyDocument *AWSServerlessFunction_IAMPolicyDocument

	IAMPolicyDocumentArray *[]AWSServerlessFunction_IAMPolicyDocument
}

func (r AWSServerlessFunction_StringOrIAMPolicyDocumentOrListOfStringOrListOfIAMPolicyDocument) value() interface{} {

	if r.String != nil {
		return r.String
	}

	if r.String != nil {
		return r.String
	}

	if r.IAMPolicyDocument != nil {
		return r.IAMPolicyDocument
	}

	if r.IAMPolicyDocument != nil {
		return r.IAMPolicyDocument
	}

	return nil

}

func (r *AWSServerlessFunction_StringOrIAMPolicyDocumentOrListOfStringOrListOfIAMPolicyDocument) MarshalJSON() ([]byte, error) {
	return json.Marshal(r.value())
}

// Hook into the marshaller
func (r *AWSServerlessFunction_StringOrIAMPolicyDocumentOrListOfStringOrListOfIAMPolicyDocument) UnmarshalJSON(b []byte) error {

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

		mapstructure.Decode(val, &r.IAMPolicyDocument)

	case []interface{}:

		mapstructure.Decode(val, &r.StringArray)

		mapstructure.Decode(val, &r.IAMPolicyDocumentArray)

	}

	return nil
}
