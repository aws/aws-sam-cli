package parser

// https://github.com/wordnik/swagger-core/blob/scala_2.10-1.3-RC3/schemas/api-declaration-schema.json
type ApiDeclaration struct {
	ApiVersion     string            `json:"apiVersion"`
	SwaggerVersion string            `json:"swaggerVersion"`
	BasePath       string            `json:"basePath"`
	ResourcePath   string            `json:"resourcePath"` // must start with /
	Consumes       []string          `json:"-"`
	Produces       []string          `json:"produces,omitempty"`
	Apis           []*Api            `json:"apis,omitempty"`
	Models         map[string]*Model `json:"models,omitempty"`
}

func NewApiDeclaration() *ApiDeclaration {
	return &ApiDeclaration{
		Apis:     make([]*Api, 0),
		Models:   make(map[string]*Model),
		Consumes: make([]string, 0),
		Produces: make([]string, 0),
	}
}

func (api *ApiDeclaration) AddConsumedTypes(op *Operation) {
	for _, contextType := range op.Consumes {
		isExists := false
		for _, existType := range api.Consumes {
			if existType == contextType {
				isExists = true
				break
			}
		}
		if !isExists {
			api.Consumes = append(api.Consumes, contextType)
		}
	}
}

func (api *ApiDeclaration) AddProducesTypes(op *Operation) {
	for _, contextType := range op.Produces {
		isExists := false
		for _, existType := range api.Produces {
			if existType == contextType {
				isExists = true
				break
			}
		}
		if !isExists {
			api.Produces = append(api.Produces, contextType)
		}
	}
}
func (api *ApiDeclaration) AddModels(op *Operation) {
	for _, m := range op.Models {
		if m != nil {
			if _, ok := api.Models[m.Id]; !ok {
				api.Models[m.Id] = m
			}
		}
	}
}

func (api *ApiDeclaration) AddSubApi(op *Operation) {
	var subApi *Api
	for _, existsSubApi := range api.Apis {
		if existsSubApi.Path == op.Path {
			subApi = existsSubApi
			break
		}
	}
	if subApi == nil {
		subApi = NewApi()
		subApi.Path = op.Path
		subApi.Description = op.Summary

		api.Apis = append(api.Apis, subApi)
	}
	subApi.Operations = append(subApi.Operations, op)
}

func (api *ApiDeclaration) AddOperation(op *Operation) {
	api.AddProducesTypes(op)
	api.AddConsumedTypes(op)
	api.AddModels(op)
	api.AddSubApi(op)
}
