# Sample Events

This folder contains a collection of currently available event templates from the Lambda console, and includes the file that defines the mapping between the event file names and their cli commands, descriptions, and flags.

##Usage

All events here are available via the generate-event command

## Adding / Modifying events
Due to the inability for go to package raw asset files in the compiled binary, it is necessary to generate a go file that packages the data.

Whenever anything is modified in this folder, the `generated-event-binary.go` file will need to be re-generated to reflect the latest changes. This is done by using the [go-bindata](github.com/jteeuwen/go-bindata) tool.

To generate the new `generated-event-binary.go` file, you first need the go-bindata tool:

`go get -u github.com/jteeuwen/go-bindata/...`

After installing the tool, simply run

`go generate` in the root directory of the project. This will update the `generated-event-binary.go` file.


