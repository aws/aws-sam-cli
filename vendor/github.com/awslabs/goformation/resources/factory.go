package resources

// TODO Document
type ResourceFactoryInterface interface {
	AddResourceDefinition(resourceDefinition ResourceDefinition) error
	GetResourceDefinition(logicalID string) ResourceDefinition
	GetResourceByType(_type string) ResourceDefinition
}

// TODO Document
var resourceFactory ResourceFactoryInterface

// TODO Document
func GetResourceFactory() ResourceFactoryInterface {
	if resourceFactory == nil {
		resourceFactory = &factory{}

		resourceFactory.AddResourceDefinition(&awsServerlessFunction{})
	}

	return resourceFactory
}

type factory struct {
	_definitions []ResourceDefinition
}

func (f *factory) AddResourceDefinition(resourceDefinition ResourceDefinition) error {
	if f._definitions == nil {
		f._definitions = []ResourceDefinition{}
	}

	f._definitions = append(f._definitions, resourceDefinition)

	return nil
}

func (f *factory) GetResourceDefinition(logicalID string) ResourceDefinition {
	return nil
}

func (f *factory) GetResourceByType(_type string) ResourceDefinition {
	for _, value := range f._definitions {
		resourceType := value.ResourceType()

		if _type == resourceType {
			return value
		}
	}

	return nil
}
