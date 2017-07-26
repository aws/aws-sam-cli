
![alt text]( https://s3.amazonaws.com/tw-chat/attach/579528d6e2f2c2aebfe7f957e4572ca0/1.png  "Logo Title Text 1")


##Swagger UI Generator for Go



###About

This is a utility for automatically generating API documentation from annotations in Go code. It generates the documentation as JSON, according to the [Swagger Spec](https://github.com/wordnik/swagger-spec), and then displays it using [Swagger UI](https://github.com/swagger-api/swagger-ui).

This tool was inspired by [Beego](http://beego.me/docs/advantage/docs.md), and follows the same annotation standards set by Beego.
The main difference between this tool and Beego is that this generator doesn't depend on the Beego framework. You can use any framework to implement your API (or don't use a framework at all). You just add declarative comments to your API controllers, then run this generator and your documentation is ready! For an example of what such documentation looks like when presented via Swagger UI, see the Swagger [pet store example](http://petstore.swagger.wordnik.com/).

<br>


####Project Status : [Alpha](https://github.com/yvasiyarov/swagger/wiki/Declarative-Comments-Format)
####Declarative Comments Format : [Read more ](https://github.com/yvasiyarov/swagger/wiki/Declarative-Comments-Format)
####Technical Notes : [Read More ](https://github.com/yvasiyarov/swagger/wiki/Technical-Notes)
####Known Limitations : [Read More ](https://github.com/yvasiyarov/swagger/wiki/Known-Limitations)

<br>
#### Quick Start Guide


1. Add comments to your API source code, [see Declarative Comments Format ](https://github.com/yvasiyarov/swagger/wiki/Declarative-Comments-Format)

2. Download Swagger for Go by using ````go get github.com/yvasiyarov/swagger````

3. Or, compile the Swagger generator from sources.
    `go install`

    This will create a binary in your $GOPATH/bin folder called swagger (Mac/Unix) or swagger.exe (Windows).

3. Run the Swagger generator.
    Be in the folder with your annotated API source code and run the swagger binary:

    `./$GOPATH/bin/swagger -apiPackage="my_cool_api" -mainApiFile="my_cool_api/web/main.go"`

    Command line switches are:
    * **-apiPackage**  - package with API controllers implementation
    * **-mainApiFile** - main API file. We will look for "General API info" in this file. If the mainApiFile command-line switch is left blank, then main.go is assumed (in the location specified by apiPackage).
    * **-format**       - One of: go|swagger|asciidoc|markdown|confluence. Default is -format="go". See below.
    * **-output**       - Output specification. Default varies according to -format. See below.
    * **-controllerClass**  - Speed up parsing by specifying which receiver objects have the controller methods. The default is to search all methods. The argument can be a regular expression. For example, `-controllerClass="(Context|Controller)$"` means the receiver name must end in Context or Controller.
    * **-contentsTable**       - Generate 'Table of Contents' section, default value is true, if set '-contentsTable=false' it will not generate the section.
    * **-models**       - Generate 'Models' section, default value is true, if set '-models=false' it will not generate the section.
    * **-vendoringPath** - Specify the vendoring directory instead of using current working directory

 [**You can Generate different formats** ](https://github.com/yvasiyarov/swagger/wiki/Generate-Different-Formats)

   <br>

4. To run the generated swagger UI (assuming you used -format="go"), copy/move the generated docs.go file to a new folder under GOPATH/src. Also bring in the web.go-example file, renaming it to web.go. Then: **go run web.go docs.go**

5. Enjoy it :-)
