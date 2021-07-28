

FROM golang:1.15.6-alpine3.12 AS builder
WORKDIR /
##
## Do not look for C libs on the system.
## Disable cgo to create a static binary.
##
env CGO_ENABLED="0"

##
## Compile for 64-bit Linux
##
env GOOS="linux"
env GOARCH="amd64"

##
## -a : Rebuild all packages
##      All imported libs will be rebuilt with CGO disabled.
##
COPY application.go .
RUN apk add --no-cache git
RUN go get "github.com/aws/aws-lambda-go/lambda"
RUN go build -a -o application application.go





FROM   scratch
WORKDIR /
EXPOSE 5000
COPY --from=builder /application /

CMD    ["/application"]





