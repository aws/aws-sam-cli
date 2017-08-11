package resources

// TODO Document
type Template interface {
	Version() string
	Transform() []string
	Parameters() map[string]Parameter
	Resources() map[string]Resource
	Outputs() map[string]Output

	GetResourcesByType(resourceType string) map[string]Resource
}

// TODO Document
type Parameter interface {
	AllowedPattern() string
	AllowedValues() []string
	ConstraintDescription() string
	Default() string
	Description() string
	MaxLength() string
	MaxValue() string
	MinLength() string
	MinValue() string
	NoEcho() string
	Type() string
}

// TODO Document
type Resource interface {
	Type() string
	Properties() map[string]Property
	ReturnValues() map[string]string
}

// TODO Document
type Property interface {
	Value() interface{}
	Original() interface{}
	HasFn() bool
}

// TODO Outputs
type Output interface {
	Description() string
	Value() string
	Export() ExportParam
}

// TODO Document
type ExportParam interface {
	Name() string
}
