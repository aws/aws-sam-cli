package resources

import "fmt"

// ListOrString defines an ambiguous type for YAML document, which can take
// a list of strings by default but also a single string literal.
type ListOrString []string

// UnmarshalYAML defines a way to unmarshal variables of ListOrString.
func (e *ListOrString) UnmarshalYAML(unmarshal func(interface{}) error) (err error) {

	var aux interface{}
	if err = unmarshal(&aux); err != nil {
		return
	}

	switch raw := aux.(type) {
	case string:
		*e = []string{raw}

	case []interface{}:
		list := make([]string, len(raw))
		for i, r := range raw {
			v, ok := r.(string)
			if !ok {
				return fmt.Errorf("An item in evn cannot be converted to a string: %v", aux)
			}
			list[i] = v
		}
		*e = list

	}
	return

}
