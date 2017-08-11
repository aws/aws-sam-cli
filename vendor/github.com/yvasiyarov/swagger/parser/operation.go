package parser

import (
	"errors"
	"fmt"
	//"go/ast"
	"regexp"
	"strconv"
	"strings"
)

type Operation struct {
	HttpMethod       string            `json:"httpMethod"`
	Nickname         string            `json:"nickname"`
	Type             string            `json:"type"`
	Items            OperationItems    `json:"items,omitempty"`
	Summary          string            `json:"summary,omitempty"`
	Notes            string            `json:"notes,omitempty"`
	Parameters       []Parameter       `json:"parameters,omitempty"`
	ResponseMessages []ResponseMessage `json:"responseMessages,omitempty"`
	Consumes         []string          `json:"-"`
	Produces         []string          `json:"produces,omitempty"`
	Authorizations   []Authorization   `json:"authorizations,omitempty"`
	Protocols        []Protocol        `json:"protocols,omitempty"`
	Path             string            `json:"-"`
	ForceResource    string            `json:"-"`
	parser           *Parser
	Models           []*Model `json:"-"`
	packageName      string
}
type OperationItems struct {
	Ref  string `json:"$ref,omitempty"`
	Type string `json:"type,omitempty"`
}

func NewOperation(p *Parser, packageName string) *Operation {
	return &Operation{
		parser:      p,
		Models:      make([]*Model, 0),
		packageName: packageName,
	}
}

func (operation *Operation) SetItemsType(itemsType string) {
	operation.Items = OperationItems{}
	if IsBasicType(itemsType) {
		operation.Items.Type = itemsType
	} else {
		operation.Items.Ref = itemsType
	}
}

func (operation *Operation) ParseComment(comment string) error {
	commentLine := strings.TrimSpace(strings.TrimLeft(comment, "//"))
	if len(commentLine) == 0 {
		return nil
	}
	attribute := strings.Fields(commentLine)[0]
	switch strings.ToLower(attribute) {
	case "@router":
		if err := operation.ParseRouterComment(commentLine); err != nil {
			return err
		}
	case "@resource":
		resource := strings.TrimSpace(commentLine[len(attribute):])
		if resource[0:1] == "/" {
			resource = resource[1:]
		}
		operation.ForceResource = resource
	case "@title":
		operation.Nickname = strings.TrimSpace(commentLine[len(attribute):])
	case "@description":
		operation.Summary = strings.TrimSpace(commentLine[len(attribute):])
	case "@success", "@failure":
		if err := operation.ParseResponseComment(strings.TrimSpace(commentLine[len(attribute):])); err != nil {
			return err
		}
	case "@param":
		if err := operation.ParseParamComment(strings.TrimSpace(commentLine[len(attribute):])); err != nil {
			return err
		}
	case "@accept", "@consume":
		if err := operation.ParseAcceptComment(strings.TrimSpace(commentLine[len(attribute):])); err != nil {
			return err
		}
	case "@produce":
		if err := operation.ParseProduceComment(strings.TrimSpace(commentLine[len(attribute):])); err != nil {
			return err
		}
	}

	operation.Models = operation.getUniqueModels()

	return nil
}

func (operation *Operation) getUniqueModels() []*Model {

	uniqueModels := make([]*Model, 0, len(operation.Models))
	modelIds := map[string]bool{}

	for _, model := range operation.Models {
		if _, exists := modelIds[model.Id]; exists {
			continue
		}
		uniqueModels = append(uniqueModels, model)
		modelIds[model.Id] = true
	}

	return uniqueModels
}

func (operation *Operation) registerType(typeName string) (string, error) {
	registerType := ""

	if translation, ok := typeDefTranslations[typeName]; ok {
		registerType = translation
	} else if IsBasicType(typeName) {
		registerType = typeName
	} else {
		model := NewModel(operation.parser)
		knownModelNames := map[string]bool{}

		err, innerModels := model.ParseModel(typeName, operation.parser.CurrentPackage, knownModelNames)
		if err != nil {
			return registerType, err
		}
		if translation, ok := typeDefTranslations[typeName]; ok {
			registerType = translation
		} else {
			registerType = model.Id

			operation.Models = append(operation.Models, model)
			operation.Models = append(operation.Models, innerModels...)
		}
	}

	return registerType, nil
}

// Parse params return []string of param properties
// @Param	queryText		form	      string	  true		        "The email for login"
// 			[param name]    [param type] [data type]  [is mandatory?]   [Comment]
func (operation *Operation) ParseParamComment(commentLine string) error {
	swaggerParameter := Parameter{}
	paramString := commentLine

	re := regexp.MustCompile(`([-\w]+)[\s]+([\w]+)[\s]+([\S.]+)[\s]+([\w]+)[\s]+"([^"]+)"`)

	if matches := re.FindStringSubmatch(paramString); len(matches) != 6 {
		return fmt.Errorf("Can not parse param comment \"%s\", skipped.", paramString)
	} else {
		typeName, err := operation.registerType(matches[3])
		if err != nil {
			return err
		}

		swaggerParameter.Name = matches[1]
		swaggerParameter.ParamType = matches[2]
		swaggerParameter.Type = typeName
		swaggerParameter.DataType = typeName
		requiredText := strings.ToLower(matches[4])
		swaggerParameter.Required = (requiredText == "true" || requiredText == "required")
		swaggerParameter.Description = matches[5]

		operation.Parameters = append(operation.Parameters, swaggerParameter)
	}

	return nil
}

// @Accept  json
func (operation *Operation) ParseAcceptComment(commentLine string) error {
	accepts := strings.Split(commentLine, ",")
	for _, a := range accepts {
		switch a {
		case "json", "application/json":
			operation.Consumes = append(operation.Consumes, ContentTypeJson)
		case "xml", "text/xml":
			operation.Consumes = append(operation.Consumes, ContentTypeXml)
		case "plain", "text/plain":
			operation.Consumes = append(operation.Consumes, ContentTypePlain)
		case "html", "text/html":
			operation.Consumes = append(operation.Consumes, ContentTypeHtml)
		case "mpfd", "multipart/form-data":
			operation.Consumes = append(operation.Consumes, ContentTypeMultiPartFormData)
		}
	}
	return nil
}

// @Produce  json
func (operation *Operation) ParseProduceComment(commentLine string) error {
	produces := strings.Split(commentLine, ",")
	for _, a := range produces {
		switch a {
		case "json", "application/json":
			operation.Produces = append(operation.Produces, ContentTypeJson)
		case "xml", "text/xml":
			operation.Produces = append(operation.Produces, ContentTypeXml)
		case "plain", "text/plain":
			operation.Produces = append(operation.Produces, ContentTypePlain)
		case "html", "text/html":
			operation.Produces = append(operation.Produces, ContentTypeHtml)
		case "mpfd", "multipart/form-data":
			operation.Produces = append(operation.Produces, ContentTypeMultiPartFormData)
		}
	}
	return nil
}

// @Router /customer/get-wishlist/{wishlist_id} [get]
func (operation *Operation) ParseRouterComment(commentLine string) error {
	sourceString := strings.TrimSpace(commentLine[len("@Router"):])

	re := regexp.MustCompile(`([\w\.\/\-{}]+)[^\[]+\[([^\]]+)`)
	var matches []string

	if matches = re.FindStringSubmatch(sourceString); len(matches) != 3 {
		return fmt.Errorf("Can not parse router comment \"%s\", skipped.", commentLine)
	}

	operation.Path = matches[1]
	operation.HttpMethod = strings.ToUpper(matches[2])
	return nil
}

// @Success 200 {object} model.OrderRow "Error message, if code != 200"
func (operation *Operation) ParseResponseComment(commentLine string) error {
	re := regexp.MustCompile(`([\d]+)[\s]+([\w\{\}]+)[\s]+([\w\-\.\/]+)[^"]*(.*)?`)
	var matches []string

	if matches = re.FindStringSubmatch(commentLine); len(matches) != 5 {
		return fmt.Errorf("Can not parse response comment \"%s\", skipped.", commentLine)
	}

	response := ResponseMessage{}
	if code, err := strconv.Atoi(matches[1]); err != nil {
		return errors.New("Success http code must be int")
	} else {
		response.Code = code
	}
	response.Message = strings.Trim(matches[4], "\"")

	typeName, err := operation.registerType(matches[3])
	if err != nil {
		return err
	}

	response.ResponseType = strings.Trim(matches[2], "{}")

	response.ResponseModel = typeName
	if response.Code == 200 {
		if matches[2] == "{array}" {
			operation.SetItemsType(typeName)
			operation.Type = "array"
		} else {
			operation.Type = typeName
		}
	}

	operation.ResponseMessages = append(operation.ResponseMessages, response)
	return nil
}
