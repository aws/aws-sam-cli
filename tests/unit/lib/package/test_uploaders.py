from unittest import TestCase
from unittest.mock import Mock

from parameterized import parameterized

from samcli.lib.package.uploaders import Destination, Uploaders


class TestUploaders(TestCase):
    @parameterized.expand([(Destination.S3,), (Destination.ECR,), (None,)])
    def test_uploader_get(self, destination):
        ecr_uploader = Mock()
        s3_uploader = Mock()

        uploaders = Uploaders(s3_uploader, ecr_uploader)

        if not destination:
            with self.assertRaises(ValueError):
                uploaders.get(destination)
        elif destination == Destination.S3:
            self.assertEqual(uploaders.get(destination), s3_uploader)
        elif destination == Destination.ECR:
            self.assertEqual(uploaders.get(destination), ecr_uploader)

        self.assertEqual(s3_uploader, uploaders.s3)
        self.assertEqual(ecr_uploader, uploaders.ecr)
