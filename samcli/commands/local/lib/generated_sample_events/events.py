"""
Methods to expose the event types and generate the event jsons for use in SAM CLI generate-event
"""

import os
import json
import base64
from requests.utils import quote

import pystache


class Events(object):

    """
    Events library class that loads and customizes event json files

    Methods
    ---------------
    expose_event_metadata(self):
        return the event mapping file
    generate-event(self, service_name, event_type, values_to_sub):
        load in and substitute values into json file (if necessary)
    """

    def __init__(self):
        """
        Constructor for event library
        """

        this_folder = os.path.dirname(os.path.abspath(__file__))
        file_name = os.path.join(this_folder, "event-mapping.json")
        with open(file_name) as f:
            self.event_mapping = json.load(f)

    def encode(self, tags, encoding, values_to_sub):
        """
        reads the encoding type from the event-mapping.json
        and determines whether a value needs encoding

        Parameters
        ----------
        tags: dict
            the values of a particular event that can be substituted
            within the event json
        encoding: string
            string that helps navigate to the encoding field of the json
        values_to_sub: dict
            key/value pairs that will be substituted into the json
        Returns
        -------
        values_to_sub: dict
            the encoded (if need be) values to substitute into the json.
        """

        for tag in tags:
            if tags[tag].get(encoding) != "None":
                if tags[tag].get(encoding) == "url":
                    values_to_sub[tag] = self.url_encode(values_to_sub[tag])
                if tags[tag].get(encoding) == "base64":
                    values_to_sub[tag] = self.base64_utf_encode(values_to_sub[tag])
        return values_to_sub

    def url_encode(self, value):
        """
        url encodes the value passed in

        Parameters
        ----------
        value: string
            the value that needs to be encoded in the json
        Returns
        -------
        string: the url encoded value
        """

        return quote(value)

    def base64_utf_encode(self, value):
        """
        base64 utf8 encodes the value passed in

        Parameters
        ----------
        value: string
            value that needs to be encoded in the json
        Returns
        -------
        string: the base64_utf encoded value
        """

        return base64.b64encode(value.encode('utf8')).decode('utf-8')

    def generate_event(self, service_name, event_type, values_to_sub):
        """
        opens the event json, substitutes the values in, and
        returns the customized event json

        Parameters
        ----------
        service_name: string
            name of the top level service (S3, apigateway, etc)
        event_type: string
            name of the event underneath the service
        values_to_sub: dict
            key/value pairs to substitute into the json
        Returns
        -------
        renderer.render(): string
            string version of the custom event json
        """

        # set variables for easy calling
        tags = self.event_mapping[service_name][event_type]['tags']
        values_to_sub = self.encode(tags, 'encoding', values_to_sub)

        # construct the path to the Events json file
        this_folder = os.path.dirname(os.path.abspath(__file__))
        file_name = self.event_mapping[service_name][event_type]['filename'] + ".json"
        file_path = os.path.join(this_folder, "events", service_name, file_name)

        # open the file
        with open(file_path) as f:
            data = json.load(f)

        data = json.dumps(data, indent=2)

        # return the substituted file
        renderer = pystache.Renderer()
        return renderer.render(data, values_to_sub)
