from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.resources.TemplateResource import TemplateResource


class TestTemplateResource(TestCase):
    def test_class(self):
        object_mock = Mock()
        type_mock = Mock()

        resource = TemplateResource(object_mock, type_mock)

        self.assertEqual(resource.resource_object, object_mock)
        self.assertEqual(resource.resource_type, type_mock)
        with self.assertRaises(NotImplementedError):
            resource.resource_name
