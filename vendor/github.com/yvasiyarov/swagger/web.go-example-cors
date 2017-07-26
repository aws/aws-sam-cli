package main

import (
	"flag"
	//	"fmt"
	"log"
	"net/http"
	"strings"
	"github.com/rs/cors"
)

var host = flag.String("host", "0.0.0.0", "Host")
var port = flag.String("port", "8080", "Port")
var staticContent = flag.String("staticPath", "./swagger-ui", "Path to folder with Swagger UI")

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
		w.Write([]byte(json))
	} else {
		w.WriteHeader(http.StatusNotFound)
	}
}

func main() {
	flag.Parse()

	//Add the url orgins to access from
	c := cors.New(cors.Options{
		AllowedOrigins: []string{"http://www.example.com/"},
	})
	// To serve a directory on disk (/tmp) under an alternate URL
	// path (/tmpfiles/), use StripPrefix to modify the request
	// URL's path before the FileServer sees it:
	http.HandleFunc("/", IndexHandler)
	http.Handle("/swagger-ui/", http.StripPrefix("/swagger-ui/", http.FileServer(http.Dir(*staticContent))))

	for apiKey, _ := range apiDescriptionsJson {
		http.HandleFunc("/"+apiKey+"/", ApiDescriptionHandler)
	}

	listenTo := *host + ":" + *port
	log.Printf("Star listen to %s", listenTo)

	http.ListenAndServe(listenTo, http.DefaultServeMux)
	//http.ListenAndServe(listenTo, c.Handler(http.DefaultServeMux)) Allows cors to be used.
	//http.ListenAndServe(":8080", http.StripPrefix("/swagger-ui/", http.FileServer(http.Dir("./swagger-ui")) )
}
