package parser

import (
	"fmt"
	"go/ast"
	"log"
	"reflect"
	"regexp"
	"strings"
)

type Model struct {
	Id         string                    `json:"id"`
	Required   []string                  `json:"required,omitempty"`
	Properties map[string]*ModelProperty `json:"properties"`
	parser     *Parser
}

func NewModel(p *Parser) *Model {
	return &Model{
		parser: p,
	}
}

// modelName is something like package.subpackage.SomeModel or just "subpackage.SomeModel"
func (m *Model) ParseModel(modelName string, currentPackage string, knownModelNames map[string]bool) (error, []*Model) {
	knownModelNames[modelName] = true
	//log.Printf("Before parse model |%s|, package: |%s|\n", modelName, currentPackage)

	astTypeSpec, modelPackage := m.parser.FindModelDefinition(modelName, currentPackage)

	modelNameParts := strings.Split(modelName, ".")
	m.Id = strings.Join(append(strings.Split(modelPackage, "/"), modelNameParts[len(modelNameParts)-1]), ".")

	var innerModelList []*Model
	if astTypeDef, ok := astTypeSpec.Type.(*ast.Ident); ok {
		typeDefTranslations[astTypeSpec.Name.String()] = astTypeDef.Name
	} else if astStructType, ok := astTypeSpec.Type.(*ast.StructType); ok {
		m.ParseFieldList(astStructType.Fields.List, modelPackage)
		usedTypes := make(map[string]bool)

		for _, property := range m.Properties {
			typeName := property.Type
			if typeName == "array" {
				if property.Items.Type != "" {
					typeName = property.Items.Type
				} else {
					typeName = property.Items.Ref
				}
			}
			if translation, ok := typeDefTranslations[typeName]; ok {
				typeName = translation
			}
			if IsBasicType(typeName) || m.parser.IsImplementMarshalInterface(typeName) {
				continue
			}
			if _, exists := knownModelNames[typeName]; exists {
				continue
			}

			usedTypes[typeName] = true
		}

		//log.Printf("Before parse inner model list: %#v\n (%s)", usedTypes, modelName)
		innerModelList = make([]*Model, 0, len(usedTypes))

		for typeName, _ := range usedTypes {
			typeModel := NewModel(m.parser)
			if err, typeInnerModels := typeModel.ParseModel(typeName, modelPackage, knownModelNames); err != nil {
				//log.Printf("Parse Inner Model error %#v \n", err)
				return err, nil
			} else {
				for _, property := range m.Properties {
					if property.Type == "array" {
						if property.Items.Ref == typeName {
							property.Items.Ref = typeModel.Id
						}
					} else {
						if property.Type == typeName {
							property.Type = typeModel.Id
						}
					}
				}
				//log.Printf("Inner model %v parsed, parsing %s \n", typeName, modelName)
				if typeModel != nil {
					innerModelList = append(innerModelList, typeModel)
				}
				if typeInnerModels != nil && len(typeInnerModels) > 0 {
					innerModelList = append(innerModelList, typeInnerModels...)
				}
				//log.Printf("innerModelList: %#v\n, typeInnerModels: %#v, usedTypes: %#v \n", innerModelList, typeInnerModels, usedTypes)
			}
		}
		//log.Printf("After parse inner model list: %#v\n (%s)", usedTypes, modelName)
		// log.Fatalf("Inner model list: %#v\n", innerModelList)

	}

	//log.Printf("ParseModel finished %s \n", modelName)
	return nil, innerModelList
}

func (m *Model) ParseFieldList(fieldList []*ast.Field, modelPackage string) {
	if fieldList == nil {
		return
	}
	//log.Printf("ParseFieldList\n")

	m.Properties = make(map[string]*ModelProperty)
	for _, field := range fieldList {
		m.ParseModelProperty(field, modelPackage)
	}
}

func (m *Model) ParseModelProperty(field *ast.Field, modelPackage string) {
	var name string
	var innerModel *Model

	property := NewModelProperty()

	typeAsString := property.GetTypeAsString(field.Type)
	//log.Printf("Get type as string %s \n", typeAsString)

	// Sometimes reflection reports an object as "&{foo Bar}" rather than just "foo.Bar"
	// The next 2 lines of code normalize them to foo.Bar
	reInternalRepresentation := regexp.MustCompile("&\\{(\\w*) (\\w*)\\}")
	typeAsString = string(reInternalRepresentation.ReplaceAll([]byte(typeAsString), []byte("$1.$2")))

	if strings.HasPrefix(typeAsString, "[]") {
		property.Type = "array"
		property.SetItemType(typeAsString[2:])
	} else if typeAsString == "time.Time" {
		property.Type = "Time"
	} else {
		property.Type = typeAsString
	}

	if len(field.Names) == 0 {

		if astSelectorExpr, ok := field.Type.(*ast.SelectorExpr); ok {
			packageName := modelPackage
			if astTypeIdent, ok := astSelectorExpr.X.(*ast.Ident); ok {
				packageName = astTypeIdent.Name
			}

			name = packageName + "." + strings.TrimPrefix(astSelectorExpr.Sel.Name, "*")
		} else if astTypeIdent, ok := field.Type.(*ast.Ident); ok {
			name = astTypeIdent.Name
		} else if astStarExpr, ok := field.Type.(*ast.StarExpr); ok {
			if astIdent, ok := astStarExpr.X.(*ast.Ident); ok {
				name = astIdent.Name
			}
		} else {
			log.Fatalf("Something goes wrong: %#v", field.Type)
		}
		innerModel = NewModel(m.parser)
		//log.Printf("Try to parse embeded type %s \n", name)
		//log.Fatalf("DEBUG: field: %#v\n, selector.X: %#v\n selector.Sel: %#v\n", field, astSelectorExpr.X, astSelectorExpr.Sel)
		knownModelNames := map[string]bool{}
		innerModel.ParseModel(name, modelPackage, knownModelNames)

		for innerFieldName, innerField := range innerModel.Properties {
			m.Properties[innerFieldName] = innerField
		}

		//log.Fatalf("Here %#v\n", field.Type)
		return
	} else {
		name = field.Names[0].Name
	}

	//log.Printf("ParseModelProperty: %s, CurrentPackage %s, type: %s \n", name, modelPackage, property.Type)
	//Analyse struct fields annotations
	if field.Tag != nil {
		structTag := reflect.StructTag(strings.Trim(field.Tag.Value, "`"))
		var tagText string
		if thriftTag := structTag.Get("thrift"); thriftTag != "" {
			tagText = thriftTag
		}
		if tag := structTag.Get("json"); tag != "" {
			tagText = tag
		}

		tagValues := strings.Split(tagText, ",")
		var isRequired = false

		for _, v := range tagValues {
			if v != "" && v != "required" && v != "omitempty" {
				name = v
			}
			if v == "required" {
				isRequired = true
			}
			// We will not document at all any fields with a json tag of "-"
			if v == "-" {
				return
			}
		}
		if required := structTag.Get("required"); required != "" || isRequired {
			m.Required = append(m.Required, name)
		}
		if desc := structTag.Get("description"); desc != "" {
			property.Description = desc
		}
	}
	m.Properties[name] = property
}

type ModelProperty struct {
	Type        string             `json:"type"`
	Description string             `json:"description"`
	Items       ModelPropertyItems `json:"items,omitempty"`
	Format      string             `json:"format"`
}
type ModelPropertyItems struct {
	Ref  string `json:"$ref,omitempty"`
	Type string `json:"type,omitempty"`
}

func NewModelProperty() *ModelProperty {
	return &ModelProperty{}
}

// refer to builtin.go
var basicTypes = map[string]bool{
	"bool":       true,
	"uint":       true,
	"uint8":      true,
	"uint16":     true,
	"uint32":     true,
	"uint64":     true,
	"int":        true,
	"int8":       true,
	"int16":      true,
	"int32":      true,
	"int64":      true,
	"float32":    true,
	"float64":    true,
	"string":     true,
	"complex64":  true,
	"complex128": true,
	"byte":       true,
	"rune":       true,
	"uintptr":    true,
	"error":      true,
	"Time":       true,
	"file":       true,
}

var typeDefTranslations = map[string]string{}

func IsBasicType(typeName string) bool {
	_, ok := basicTypes[typeName]
	return ok || strings.Contains(typeName, "interface")
}

func (p *ModelProperty) SetItemType(itemType string) {
	p.Items = ModelPropertyItems{}
	if IsBasicType(itemType) {
		p.Items.Type = itemType
	} else {
		p.Items.Ref = itemType
	}
}
func (p *ModelProperty) GetTypeAsString(fieldType interface{}) string {
	var realType string
	if astArrayType, ok := fieldType.(*ast.ArrayType); ok {
		//		log.Printf("arrayType: %#v\n", astArrayType)
		realType = fmt.Sprintf("[]%v", p.GetTypeAsString(astArrayType.Elt))
	} else if astMapType, ok := fieldType.(*ast.MapType); ok {
		//		log.Printf("arrayType: %#v\n", astArrayType)
		realType = fmt.Sprintf("[]%v", p.GetTypeAsString(astMapType.Value))
	} else if _, ok := fieldType.(*ast.InterfaceType); ok {
		realType = "interface"
	} else {
		if astStarExpr, ok := fieldType.(*ast.StarExpr); ok {
			realType = fmt.Sprint(astStarExpr.X)
			//			log.Printf("Get type as string (star expression)! %#v, type: %s\n", astStarExpr.X, fmt.Sprint(astStarExpr.X))
		} else if astSelectorExpr, ok := fieldType.(*ast.SelectorExpr); ok {
			packageNameIdent, _ := astSelectorExpr.X.(*ast.Ident)
			realType = packageNameIdent.Name + "." + astSelectorExpr.Sel.Name

			//			log.Printf("Get type as string(selector expression)! X: %#v , Sel: %#v, type %s\n", astSelectorExpr.X, astSelectorExpr.Sel, realType)
		} else {
			//			log.Printf("Get type as string(no star expression)! %#v , type: %s\n", fieldType, fmt.Sprint(fieldType))
			realType = fmt.Sprint(fieldType)
		}
	}
	return realType
}
