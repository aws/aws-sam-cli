from unittest import TestCase

from samcli.lib.samlib.resource_metadata_normalizer import ResourceMetadataNormalizer


class TestResourceMeatadataNormalizer(TestCase):
    def test_replace_property_with_path(self):
        template_data = {
            "Resources": {
                "Function1": {
                    "Properties": {"Code": "some value"},
                    "Metadata": {"aws:asset:path": "new path", "aws:asset:property": "Code"},
                }
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("new path", template_data["Resources"]["Function1"]["Properties"]["Code"])

    def test_replace_all_resources_that_contain_metadata(self):
        template_data = {
            "Resources": {
                "Function1": {
                    "Properties": {"Code": "some value"},
                    "Metadata": {"aws:asset:path": "new path", "aws:asset:property": "Code"},
                },
                "Resource2": {
                    "Properties": {"SomeRandomProperty": "some value"},
                    "Metadata": {"aws:asset:path": "super cool path", "aws:asset:property": "SomeRandomProperty"},
                },
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("new path", template_data["Resources"]["Function1"]["Properties"]["Code"])
        self.assertEqual("super cool path", template_data["Resources"]["Resource2"]["Properties"]["SomeRandomProperty"])

    def test_tempate_without_metadata(self):
        template_data = {"Resources": {"Function1": {"Properties": {"Code": "some value"}}}}

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("some value", template_data["Resources"]["Function1"]["Properties"]["Code"])

    def test_template_without_asset_property(self):
        template_data = {
            "Resources": {
                "Function1": {"Properties": {"Code": "some value"}, "Metadata": {"aws:asset:path": "new path"}}
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("some value", template_data["Resources"]["Function1"]["Properties"]["Code"])

    def test_tempalte_without_asset_path(self):
        template_data = {
            "Resources": {
                "Function1": {"Properties": {"Code": "some value"}, "Metadata": {"aws:asset:property": "Code"}}
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("some value", template_data["Resources"]["Function1"]["Properties"]["Code"])

    def test_template_with_empty_metadata(self):
        template_data = {"Resources": {"Function1": {"Properties": {"Code": "some value"}, "Metadata": {}}}}

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("some value", template_data["Resources"]["Function1"]["Properties"]["Code"])

    def test_replace_of_property_that_does_not_exist(self):
        template_data = {
            "Resources": {
                "Function1": {
                    "Properties": {},
                    "Metadata": {"aws:asset:path": "new path", "aws:asset:property": "Code"},
                }
            }
        }

        ResourceMetadataNormalizer.normalize(template_data)

        self.assertEqual("new path", template_data["Resources"]["Function1"]["Properties"]["Code"])
