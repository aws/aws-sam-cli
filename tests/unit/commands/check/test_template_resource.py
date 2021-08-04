from unittest import TestCase
from unittest.mock import Mock, patch

from samcli.commands.check.resources.template_resource import TemplateResource


class TestTemplateResource(TestCase):
    def test_class(self):
        object_mock = Mock()
        type_mock = Mock()
        name_mock = Mock()

        resource = TemplateResource(object_mock, type_mock, name_mock)

        self.assertEqual(resource.resource_object, object_mock)
        self.assertEqual(resource.resource_type, type_mock)
        self.assertEqual(resource.resource_name, name_mock)
