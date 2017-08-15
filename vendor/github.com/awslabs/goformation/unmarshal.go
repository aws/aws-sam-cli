package goformation

import (
	"regexp"

	. "github.com/awslabs/goformation/resources"
	"github.com/awslabs/goformation/util"
	"gopkg.in/yaml.v2"
)

func unmarshal(input []byte) (Template, error) {
	util.LogDebug(-1, "Unmarshalling", "Unmarshalling process started")

	var source = input
	var error error
	template := &unmarshalledTemplate{}

	if err := yaml.Unmarshal(source, template); err != nil {
		util.LogError(-1, "Unmarshalling", "There was a problem when unmarshalling the template")
		util.LogError(-1, "Unmarshalling", "%s", err.Error())
		return nil, err
	}

	util.LogDebug(-1, "Unmarshalling", "Storing line numbers for the components")

	// Process and store line numbers for giving comprehensive error messages.
	lineAnalysis := ProcessLineNumbers(source)
	template._lineNumbers = lineAnalysis

	return template, error
}

// BEGIN unmarshalledTemplate definition - and sons
type unmarshalledTemplate struct {
	_version                string                           `yaml:"AWSTemplateFormatVersion"`
	_transform              []string                         `yaml:"Transform"`
	_unmarshalledParameters map[string]unmarshalledParameter `yaml:"Parameters"`
	_resources              map[string]*unmarshalledResource `yaml:"Resources"`
	_outputs                map[string]output                `yaml:"Outputs"`
	_lineNumbers            LineDictionary
}

func (t *unmarshalledTemplate) UnmarshalYAML(unmarshal func(interface{}) error) (err error) {

	var aux map[string]interface{}
	if err = unmarshal(&aux); err != nil {
		return err
	}

	for key, value := range aux {
		switch key {
		case "AWSTemplateFormatVersion":
			t._version = util.ParsePrimitive(value).(string)
		case "Transform":
			if valueArray, ok := value.([]string); ok {
				t._transform = valueArray
			} else {
				stringTransform := util.ParsePrimitive(value).(string)
				t._transform = []string{stringTransform}
			}
		case "Resources":
			util.ParseComplex(value, &t._resources)
		}
	}

	return nil
}

func (t *unmarshalledTemplate) Version() string {
	return t._version
}
func (t *unmarshalledTemplate) Transform() []string {
	return t._transform
}
func (t *unmarshalledTemplate) Parameters() map[string]Parameter {
	ret := make(map[string]Parameter)
	for key, value := range t._unmarshalledParameters {
		ret[key] = &value
	}
	return ret
}
func getResourceAddr(input Resource) Resource {
	return input
}
func (t *unmarshalledTemplate) Resources() map[string]Resource {
	ret := make(map[string]Resource)
	for key, value := range t._resources {
		if value == nil {
			value = &unmarshalledResource{}
		}
		ret[key] = getResourceAddr(value)
	}
	return ret
}
func (t *unmarshalledTemplate) Outputs() map[string]Output {
	ret := make(map[string]Output)
	for key, value := range t._outputs {
		ret[key] = &value
	}
	return ret
}

func (t *unmarshalledTemplate) GetResourcesByType(resourceType string) map[string]Resource {
	return nil
}

type unmarshalledParameter struct {
	PAllowedPattern        string   `yaml:"AllowedPattern"`
	PAllowedValues         []string `yaml:"AllowedValues"`
	PConstraintDescription string   `yaml:"ConstraintDescription"`
	PDefault               string   `yaml:"Default"`
	PDescription           string   `yaml:"Description"`
	PMaxLength             string   `yaml:"MaxLength"`
	PMaxValue              string   `yaml:"MaxValue"`
	PMinLength             string   `yaml:"MinLength"`
	PMinValue              string   `yaml:"MinValue"`
	PNoEcho                string   `yaml:"NoEcho"`
	PType                  string   `yaml:"Type"`
}

func (p *unmarshalledParameter) AllowedPattern() string {
	return p.PAllowedPattern
}
func (p *unmarshalledParameter) AllowedValues() []string {
	return p.PAllowedValues
}
func (p *unmarshalledParameter) ConstraintDescription() string {
	return p.PConstraintDescription
}
func (p *unmarshalledParameter) Default() string {
	return p.PDefault
}
func (p *unmarshalledParameter) Description() string {
	return p.PDescription
}
func (p *unmarshalledParameter) MaxLength() string {
	return p.PMaxLength
}
func (p *unmarshalledParameter) MaxValue() string {
	return p.PMaxValue
}
func (p *unmarshalledParameter) MinLength() string {
	return p.PMinLength
}
func (p *unmarshalledParameter) MinValue() string {
	return p.PMinValue
}
func (p *unmarshalledParameter) NoEcho() string {
	return p.PNoEcho
}
func (p *unmarshalledParameter) Type() string {
	return p.PType
}

type unmarshalledResource struct {
	RType       string                           `yaml:"Type"`
	RProperties map[string]*unmarshalledProperty `yaml:"Properties"`
}

func (r *unmarshalledResource) UnmarshalYAML(unmarshal func(interface{}) error) (err error) {

	var aux map[string]interface{}
	if err = unmarshal(&aux); err != nil {

		return err
	}

	r.RType = util.ParsePrimitive(aux["Type"]).(string)
	util.ParseComplex(aux["Properties"], &r.RProperties)

	return nil
}

func (r *unmarshalledResource) Type() string {
	return r.RType
}

func setPropertyKey(props map[string]Property, key string, value Property) {
	props[key] = value
}
func (r *unmarshalledResource) Properties() map[string]Property {
	props := make(map[string]Property)
	for key, value := range r.RProperties {
		setPropertyKey(props, key, value)
	}
	return props
}

func (r *unmarshalledResource) ReturnValues() map[string]string {
	return nil
}

type unmarshalledProperty struct {
	PValue interface{}
}

func (p *unmarshalledProperty) UnmarshalYAML(unmarshal func(interface{}) error) (err error) {

	var aux interface{}
	if err = unmarshal(&aux); err != nil {
		return err
	}

	p.PValue = aux

	return nil
}

func (p *unmarshalledProperty) Value() interface{} {
	return p.PValue
}
func (p *unmarshalledProperty) Original() interface{} {
	if p == nil {
		return nil
	}
	return p.PValue
}
func (p *unmarshalledProperty) HasFn() bool {
	return false
}

// TODO Implement outputs
type output struct {
	_description string       `yaml:"Description"`
	_value       string       `yaml:"Value"`
	_export      outputExport `yaml:"Export"`
}

func (o *output) Description() string {
	return o._description
}
func (o *output) Value() string {
	return o._value
}
func (o *output) Export() ExportParam {
	return &o._export
}

type outputExport struct {
	_name string `yaml:"Name"`
}

func (oe *outputExport) Name() string {
	return oe._name
}

// END unmarshalledTemplate definition - and sons

func processIntrinsicFunctions(input []byte) (source []byte, error error) {
	var okRegular = true
	var okComplexSub = true

	// var stringTpl string = string(input)
	// // Find inline Intrinsic Functions:
	// XXX This does not accept double-quoted stuff inside intrinsic functions - special look at Fn::Sub...
	var inlineFnRegex = `[\n\t\s]*!(Base64|FindInMap|GetAtt|GetAZs|ImportValue|Join|Select|Split|Sub|Ref) ([\'\"]?([a-zA-Z0-9_\.:\-$\{\}\/])+[\'\"]?|\[?((?:::|[a-zA-Z0-9_\.:\-$\{\}\/\[\],\'\" !])+)\]?)`
	hasInlineFn, error := regexp.Match(inlineFnRegex, input)
	if error != nil {
		util.LogError(-1, "Unmarshalling", "%s", error.Error())
		return nil, error
	} else if hasInlineFn {
		regex := regexp.MustCompile(inlineFnRegex)
		tmpSource := regex.ReplaceAllString(string(input), ` [ "Fn::$1",T3mpqu0T35Start $2 T3mPQu0T35End ]`)
		quotesWithQuotesMsgStartRegex := regexp.MustCompile(`T3mpqu0T35Start \"`)
		quotesWithQuotesMsgEndRegex := regexp.MustCompile(`\" T3mPQu0T35End`)
		quotesWithArrayMsgStartRegex := regexp.MustCompile(`T3mpqu0T35Start \[`)
		quotesWithArrayMsgEndRegex := regexp.MustCompile(`\] T3mPQu0T35End`)
		quotesWithoutQuotesMsgStartRegex := regexp.MustCompile(`T3mpqu0T35Start `)
		quotesWithoutQuotesMsgEndRegex := regexp.MustCompile(` T3mPQu0T35End`)
		fakeQuoteRegex := regexp.MustCompile(`F4k3Qu0T3`)

		// Replace with quotes first
		tmpSource = quotesWithQuotesMsgStartRegex.ReplaceAllString(tmpSource, "F4k3Qu0T3")
		tmpSource = quotesWithQuotesMsgEndRegex.ReplaceAllString(tmpSource, "F4k3Qu0T3")

		// Now replace instances with an array
		tmpSource = quotesWithArrayMsgStartRegex.ReplaceAllString(tmpSource, "[")
		tmpSource = quotesWithArrayMsgEndRegex.ReplaceAllString(tmpSource, "]")

		// And now without quotes
		tmpSource = quotesWithoutQuotesMsgStartRegex.ReplaceAllString(tmpSource, "F4k3Qu0T3")
		tmpSource = quotesWithoutQuotesMsgEndRegex.ReplaceAllString(tmpSource, "F4k3Qu0T3")

		// Replace fake quotes
		tmpSource = fakeQuoteRegex.ReplaceAllString(tmpSource, "\"")

		// Assign back to real source
		source = []byte(tmpSource)
	} else {
		okRegular = false
	}

	// Try to find for Sub with array
	var subArrayFnRegex = `[\n\t\s]*!Sub\s*\n\s+\t*\-\s*\[\'\"]?([a-zA-Z0-9:_\.\-\$\{\}\/]+)\[\'\"]?\s*\n\s+\t*\-\s*(\{\s*[\"\-\$\:\{\}\,\sa-zA-Z0-9]+\s*\})`
	hasSubFn, error := regexp.Match(subArrayFnRegex, source)
	if error != nil {
		util.LogError(-1, "Unmarshalling", "Error trying to find Array !Sub")
		return nil, error
	} else if hasSubFn {
		compiledRegex := regexp.MustCompile(subArrayFnRegex)
		source = compiledRegex.ReplaceAll(source, []byte(` [ "Fn::Sub",$1,$2 ]`))
	} else {
		okComplexSub = false
	}

	if !okRegular && !okComplexSub {
		return source, ErrNoIntrinsicFunctionFound
	}

	return source, error
}
