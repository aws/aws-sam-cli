package resources

// TODO Document
type ResourceDefinition interface {
	ResourceType() string
	Template(interface{}) Resource
	Resource() (Resource, error)
	ClassConstructor(input Resource) (Resource, error)
}

// TODO Document
type LineDictionary interface {
	Line() int
	Level() int
	IndentLevel() int
	Key() string
	Value() string
	Type() string
	Parent() LineDictionary
	Children() []LineDictionary
	End() bool
	SetChildren(input []LineDictionary)
}

// TODO Document
type Scaffoldable interface {
	Scaffold(input Resource, propName string) (Resource, error)
}
