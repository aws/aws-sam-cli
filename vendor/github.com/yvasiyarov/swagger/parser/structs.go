package parser

import (
	"errors"
)

const SwaggerVersion = "1.2"
const (
	ContentTypeJson              = "application/json"
	ContentTypeXml               = "application/xml"
	ContentTypePlain             = "text/plain"
	ContentTypeHtml              = "text/html"
	ContentTypeMultiPartFormData = "multipart/form-data"
)

var CommentIsEmptyError = errors.New("Comment is empty")

type ResourceListing struct {
	ApiVersion     string     `json:"apiVersion"`
	SwaggerVersion string     `json:"swaggerVersion"`
	BasePath       string     `json:"basePath,omitempty"`
	Apis           []*ApiRef  `json:"apis"`
	Infos          Infomation `json:"info"`
}

type ApiRef struct {
	Path        string `json:"path"` // relative or absolute, must start with /
	Description string `json:"description"`
}

type Infomation struct {
	Title             string `json:"title,omitempty"`
	Description       string `json:"description,omitempty"`
	Contact           string `json:"contact,omitempty"`
	TermsOfServiceUrl string `json:"termsOfServiceUrl,omitempty"`
	License           string `json:"license,omitempty"`
	LicenseUrl        string `json:"licenseUrl,omitempty"`
}

type Api struct {
	Path        string       `json:"path"` // relative or absolute, must start with /
	Description string       `json:"description"`
	Operations  []*Operation `json:"operations,omitempty"`
}

func NewApi() *Api {
	return &Api{
		Operations: make([]*Operation, 0),
	}
}

type Protocol struct {
}

type ResponseMessage struct {
	Code          int    `json:"code"`
	Message       string `json:"message"`
	ResponseType  string `json:"responseType"`
	ResponseModel string `json:"responseModel"`
}

type Parameter struct {
	ParamType     string `json:"paramType"` // path,query,body,header,form
	Name          string `json:"name"`
	Description   string `json:"description"`
	DataType      string `json:"dataType"` // 1.2 needed?
	Type          string `json:"type"`     // integer
	Format        string `json:"format"`   // int64
	AllowMultiple bool   `json:"allowMultiple"`
	Required      bool   `json:"required"`
	Minimum       int    `json:"minimum"`
	Maximum       int    `json:"maximum"`
}

type ErrorResponse struct {
	Code   int    `json:"code"`
	Reason string `json:"reason"`
}

// https://github.com/wordnik/swagger-core/wiki/authorizations
type Authorization struct {
	LocalOAuth OAuth  `json:"local-oauth"`
	ApiKey     ApiKey `json:"apiKey"`
}

// https://github.com/wordnik/swagger-core/wiki/authorizations
type OAuth struct {
	Type       string               `json:"type"`   // e.g. oauth2
	Scopes     []string             `json:"scopes"` // e.g. PUBLIC
	GrantTypes map[string]GrantType `json:"grantTypes"`
}

// https://github.com/wordnik/swagger-core/wiki/authorizations
type GrantType struct {
	LoginEndpoint        Endpoint `json:"loginEndpoint"`
	TokenName            string   `json:"tokenName"` // e.g. access_code
	TokenRequestEndpoint Endpoint `json:"tokenRequestEndpoint"`
	TokenEndpoint        Endpoint `json:"tokenEndpoint"`
}

// https://github.com/wordnik/swagger-core/wiki/authorizations
type Endpoint struct {
	Url              string `json:"url"`
	ClientIdName     string `json:"clientIdName"`
	ClientSecretName string `json:"clientSecretName"`
	TokenName        string `json:"tokenName"`
}

// https://github.com/wordnik/swagger-core/wiki/authorizations
type ApiKey struct {
	Type   string `json:"type"`   // e.g. apiKey
	PassAs string `json:"passAs"` // e.g. header
}
