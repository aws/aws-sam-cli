package main

import (
	"flag"
	"os"
	"net/http"
	"strings"
	"text/template"

	"github.com/fvbock/endless"
	log "github.com/mgutz/logxi/v1"
)

var host = flag.String("host", "0.0.0.0", "Host")
var port = flag.String("port", "8080", "Port")
var staticContent = flag.String("staticPath", "./swagger-ui", "Path to folder with Swagger UI")
var apiurl = flag.String("api", "http://127.0.0.1", "The base path URI of the API service")

func IndexHandler(w http.ResponseWriter, r *http.Request) {
	isJsonRequest := false

	if acceptHeaders, ok := r.Header["Accept"]; ok {
		for _, acceptHeader := range acceptHeaders {
			if strings.Contains(acceptHeader, "json") {
				isJsonRequest = true
				break
			}
		}
	}

	if isJsonRequest {
		w.Write([]byte(resourceListingJson))
	} else {
		http.Redirect(w, r, "/swagger-ui/", http.StatusFound)
	}
}

func ApiDescriptionHandler(w http.ResponseWriter, r *http.Request) {
	apiKey := strings.Trim(r.RequestURI, "/")

	if json, ok := apiDescriptionsJson[apiKey]; ok {
		t, e := template.New("desc").Parse(json)
		if e != nil {
			w.WriteHeader(http.StatusInternalServerError)
			return
		}
		t.Execute(w, *apiurl)
	} else {
		w.WriteHeader(http.StatusNotFound)
	}
}

func main() {
	flag.Parse()

	// To serve a directory on disk (/tmp) under an alternate URL
	// path (/tmpfiles/), use StripPrefix to modify the request
	// URL's path before the FileServer sees it:
	http.HandleFunc("/", IndexHandler)
	http.Handle("/swagger-ui/", http.StripPrefix("/swagger-ui/", http.FileServer(http.Dir(*staticContent))))

	for apiKey, _ := range apiDescriptionsJson {
		http.HandleFunc("/"+apiKey+"/", ApiDescriptionHandler)
	}

	listenTo := *host + ":" + *port
	log.Info("Star listen to %s", listenTo)

	err := endless.ListenAndServe(listenTo, http.DefaultServeMux)
	if err != nil {
		log.Error(err.Error())
	}
	log.Info("Server on %s stopped", listenTo)
	os.Exit(0)
}
