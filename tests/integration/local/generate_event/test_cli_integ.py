from unittest import TestCase
from subprocess import Popen, PIPE
import os
import json

from tests.testing_utils import get_sam_command


class Test_EventGeneration_Integ(TestCase):
    def test_generate_event_substitution(self):
        process = Popen([get_sam_command(), "local", "generate-event", "s3", "put"])
        process.communicate()
        self.assertEqual(process.returncode, 0)

    def test_generate_event_with_dict_value(self):
        """Test that dictionary values are properly handled in generate-event"""
        process = Popen(
            [
                get_sam_command(),
                "local",
                "generate-event",
                "apigateway",
                "aws-proxy",
                "--method",
                "GET",
                "--path",
                "document",
                "--body",
                "",
                "--querystringparameters",
                '{"documentId": "1044", "versionId": "v_1"}',
            ],
            stdout=PIPE,
            stderr=PIPE,
        )
        stdout, stderr = process.communicate()
        self.assertEqual(process.returncode, 0)

        # Parse the output JSON
        result = json.loads(stdout.decode("utf-8"))

        # Verify that queryStringParameters is a dict, not a string
        self.assertIsInstance(result["queryStringParameters"], dict)
        self.assertEqual(result["queryStringParameters"]["documentId"], "1044")
        self.assertEqual(result["queryStringParameters"]["versionId"], "v_1")

        # Verify other fields are still properly substituted
        self.assertEqual(result["httpMethod"], "GET")
        self.assertEqual(result["path"], "/document")
