This is a very simple Hello World application written in Golang.

### Instructions

1. Build the binary to be compatible with Linux: `GOOS=linux go build main.go`
2. Zip up the binary: `zip main.zip ./main`
3. Invoke locally
```bash
$ echo '"world"' | sam local invoke

2018/01/23 16:00:46 Successfully parsed template.yaml
2018/01/23 16:00:46 Connected to Docker 1.30
2018/01/23 16:00:46 Fetching lambci/lambda:go1.x image for go1.x runtime...
....
"Hello world!"

```

