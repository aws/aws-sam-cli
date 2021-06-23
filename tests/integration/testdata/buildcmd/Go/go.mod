// if encountered a build error:  missing go.sum entry;
// cd to this directory and run the command `GOPROXY=direct go mod tidy`
// which will generate a cleaned up go.sum file

require github.com/aws/aws-lambda-go v1.13.3

module hello-world

go 1.13
