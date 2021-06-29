from copy import deepcopy
from samcli.lib.utils.packagetype import IMAGE, ZIP
from unittest import TestCase
from unittest.mock import patch, Mock, MagicMock

from samcli.lib.iac.interface import (
    DictSection,
    DictSectionItem,
    Environment,
    Destination,
    Asset,
    Parameter,
    S3Asset,
    ImageAsset,
    Section,
    SectionItem,
    SimpleSection,
    SimpleSectionItem,
    Resource,
    Stack,
)


class TestEnvironment(TestCase):
    def test_properties(self):
        env = Environment(region="ap-southeast-1", account_id="012345")
        self.assertEqual(env.region, "ap-southeast-1")
        self.assertEqual(env.account_id, "012345")
        env.region = "us-east-1"
        env.account_id = "543210"
        self.assertEqual(env.region, "us-east-1")
        self.assertEqual(env.account_id, "543210")


class TestDestination(TestCase):
    def test_properties(self):
        destination = Destination(path="path", value="val")
        self.assertEqual(destination.path, "path")
        self.assertEqual(destination.value, "val")
        destination.path = "another_path"
        destination.value = "another_val"
        self.assertEqual(destination.path, "another_path")
        self.assertEqual(destination.value, "another_val")


class TestAsset(TestCase):
    def test_properties(self):
        asset = Asset()
        self.assertIsNotNone(asset.asset_id)
        self.assertEqual(asset.destinations, [])
        self.assertIsNone(asset.source_property)
        self.assertEqual(asset.extra_details, {})

        asset.asset_id = "asset_id"
        destionation = Destination(path="path", value="val")
        asset.destinations = [destionation]
        asset.source_property = "Code"
        asset.extra_details = {"foo": "bar"}
        self.assertEqual(asset.asset_id, "asset_id")
        self.assertEqual(asset.destinations, [destionation])
        self.assertEqual(asset.source_property, "Code")
        self.assertEqual(asset.extra_details, {"foo": "bar"})


class TestS3Asset(TestCase):
    def test_properties(self):
        s3_asset = S3Asset()
        self.assertIsNone(s3_asset.bucket_name)
        self.assertIsNone(s3_asset.object_key)
        self.assertIsNone(s3_asset.object_version)
        self.assertIsNone(s3_asset.source_path)
        self.assertIsNone(s3_asset.updated_source_path)

        self.assertIsInstance(s3_asset, Asset)
        self.assertIsNotNone(s3_asset.asset_id)
        self.assertEqual(s3_asset.destinations, [])
        self.assertIsNone(s3_asset.source_property)
        self.assertEqual(s3_asset.extra_details, {})

        s3_asset.bucket_name = "bucket"
        s3_asset.object_key = "key"
        s3_asset.object_version = "v1"
        s3_asset.source_path = "path"
        s3_asset.updated_source_path = "updated_path"
        self.assertEqual(s3_asset.bucket_name, "bucket")
        self.assertEqual(s3_asset.object_key, "key")
        self.assertEqual(s3_asset.object_version, "v1")
        self.assertEqual(s3_asset.source_path, "path")
        self.assertEqual(s3_asset.updated_source_path, "updated_path")


class TestImageAsset(TestCase):
    def test_properties(self):
        image_asset = ImageAsset()
        self.assertIsNone(image_asset.repository_name)
        self.assertIsNone(image_asset.registry)
        self.assertIsNone(image_asset.image_tag)
        self.assertIsNone(image_asset.source_local_image)
        self.assertIsNone(image_asset.source_path)
        self.assertIsNone(image_asset.docker_file_name)
        self.assertIsNone(image_asset.build_args)
        self.assertIsNone(image_asset.target)

        self.assertIsInstance(image_asset, Asset)
        self.assertIsNotNone(image_asset.asset_id)
        self.assertEqual(image_asset.destinations, [])
        self.assertIsNone(image_asset.source_property)
        self.assertEqual(image_asset.extra_details, {})

        image_asset.repository_name = "repo"
        image_asset.registry = "registry"
        image_asset.image_tag = "tag"
        image_asset.source_local_image = "repo:tag"
        image_asset.source_path = "path"
        image_asset.docker_file_name = "Dockerfile"
        image_asset.build_args = {"foo": "bar"}
        image_asset.target = "target"
        self.assertEqual(image_asset.repository_name, "repo")
        self.assertEqual(image_asset.registry, "registry")
        self.assertEqual(image_asset.image_tag, "tag")
        self.assertEqual(image_asset.source_local_image, "repo:tag")
        self.assertEqual(image_asset.source_path, "path")
        self.assertEqual(image_asset.docker_file_name, "Dockerfile")
        self.assertEqual(image_asset.build_args, {"foo": "bar"})
        self.assertEqual(image_asset.target, "target")


class TestSectionItem(TestCase):
    def test_properties(self):
        section_item = SectionItem()
        self.assertIsNone(section_item.key)
        self.assertIsNone(section_item.item_id)

        section_item.key = "key"
        section_item.item_id = "item_id"
        self.assertEqual(section_item.key, "key")
        self.assertEqual(section_item.item_id, "item_id")


class TestSimpleSectionItem(TestCase):
    def test_properties(self):
        simple_section_item = SimpleSectionItem()
        self.assertIsNone(simple_section_item.value)
        self.assertFalse(bool(simple_section_item))

        self.assertIsInstance(simple_section_item, SectionItem)
        self.assertIsNone(simple_section_item.key)
        self.assertIsNone(simple_section_item.item_id)

        simple_section_item.value = "some_val"
        self.assertEqual(simple_section_item.value, "some_val")
        self.assertTrue(bool(simple_section_item))


class TestDictSectionItem(TestCase):
    def test_properties(self):
        dict_section_item = DictSectionItem()
        self.assertEqual(dict_section_item.body, {})
        self.assertEqual(dict_section_item.assets, [])
        self.assertEqual(dict_section_item.extra_details, {})

        self.assertIsInstance(dict_section_item, SectionItem)
        self.assertIsNone(dict_section_item.key)
        self.assertIsNone(dict_section_item.item_id)

        assets = [Mock()]
        dict_section_item.assets = assets
        dict_section_item.extra_details = {"foo": "bar"}
        self.assertEqual(dict_section_item.assets, assets)
        self.assertEqual(dict_section_item.extra_details, {"foo": "bar"})

    def test_setitem(self):
        dict_section_item = DictSectionItem(body={})
        dict_section_item["foo"] = "bar"
        self.assertEqual(dict_section_item.body["foo"], "bar")

    def test_delitem(self):
        dict_section_item = DictSectionItem(body={"foo": "bar"})
        del dict_section_item["foo"]
        self.assertEqual(dict_section_item.body, {})

    def test_getitem(self):
        dict_section_item = DictSectionItem(body={"foo": "bar"})
        self.assertEqual(dict_section_item["foo"], "bar")

    def test_other_mapping_methods(self):
        body = {"foo": "bar", "baz": "bax"}
        dict_section_item = DictSectionItem(body=body)
        self.assertEqual(len(dict_section_item), 2)
        for key, val in dict_section_item.items():
            self.assertIn(key, body)
            self.assertEqual(val, body[key])
        self.assertTrue(bool(dict_section_item))


class TestSection(TestCase):
    def test_properties(self):
        section = Section(section_name="name")
        self.assertEqual(section.section_name, "name")


class TestSimpleSection(TestCase):
    def test_properties(self):
        simple_section = SimpleSection(section_name="name", value="val")
        self.assertEqual(simple_section.section_name, "name")
        self.assertEqual(simple_section.value, "val")
        simple_section.value = "another_val"
        self.assertEqual(simple_section.value, "another_val")
        self.assertTrue(bool(simple_section))
        simple_section.value = None
        self.assertFalse(bool(simple_section))


class TestDictSection(TestCase):
    def test_properties(self):
        dict_section_item = DictSectionItem(key="key", body={"foo": "bar"})
        dict_section = DictSection(section_name="name", items=[dict_section_item])
        self.assertEqual(dict_section.section_items, [dict_section_item])

    @patch("samcli.lib.iac.interface.deepcopy")
    def test_copy(self, deepcopy_mock):
        expected = Mock()
        deepcopy_mock.return_value = expected
        dict_section = DictSection(section_name="name", items=[])
        actual = dict_section.copy()
        self.assertEqual(actual, expected)


class TestResource(TestCase):
    def test_properties(self):
        stack = Stack()
        body = {}
        resource = Resource(key="key", body=body)
        self.assertIsNone(resource.nested_stack)
        resource.nested_stack = stack
        self.assertEqual(resource.nested_stack, stack)

    @patch("samcli.lib.iac.interface.deepcopy")
    def test_copy(self, deepcopy_mock):
        expected = Mock()
        deepcopy_mock.return_value = deepcopy_mock.return_value = expected
        resource = Resource(key="key")
        actual = resource.copy()
        self.assertEqual(actual, expected)

    def test_packageable(self):
        resource = Resource(key="key")
        resource["Type"] = "AWS::Serverless::Function"
        self.assertTrue(resource.is_packageable())

    def test_not_packageable(self):
        resource = Resource(key="key")
        resource["Type"] = "AWS::APIGateway::Stage"
        self.assertFalse(resource.is_packageable())

        resource = Resource(key="key")
        resource["Properties"] = {"InlineCode": "inline_code"}
        self.assertFalse(resource.is_packageable())


class TestParamater(TestCase):
    def test_properties(self):
        parameter = Parameter()
        self.assertFalse(parameter.added_by_iac)
        parameter.added_by_iac = True
        self.assertTrue(parameter.added_by_iac)

    @patch("samcli.lib.iac.interface.deepcopy")
    def test_copy(self, deepcopy_mock):
        expected = Mock()
        deepcopy_mock.return_value = deepcopy_mock.return_value = expected
        parameter = Parameter()
        actual = parameter.copy()
        self.assertEqual(actual, expected)


class TestStack(TestCase):
    def setUp(self):
        asset = S3Asset()

    @patch("samcli.lib.iac.interface.deepcopy")
    def test_copy(self, deepcopy_mock):
        expected = Mock()
        deepcopy_mock.return_value = deepcopy_mock.return_value = expected
        stack = Stack()
        actual = stack.copy()
        self.assertEqual(actual, expected)

    def test_has_assets_of_package_type_zip_true(self):
        stack = Stack(assets=[S3Asset()])
        self.assertTrue(stack.has_assets_of_package_type(ZIP))

    def test_has_assets_of_package_type_zip_false(self):
        stack = Stack(assets=[ImageAsset()])
        self.assertFalse(stack.has_assets_of_package_type(ZIP))

    def test_has_assets_of_package_type_image_true(self):
        stack = Stack(assets=[ImageAsset()])
        self.assertTrue(stack.has_assets_of_package_type(IMAGE))

    def test_has_assets_of_package_type_image_false(self):
        stack = Stack(assets=[S3Asset()])
        self.assertFalse(stack.has_assets_of_package_type(IMAGE))

    def test_find_function_resources_of_package_type_zip(self):
        zip_function_resource = Resource(key="zip_function", assets=[S3Asset()])
        zip_function_resource["Type"] = "AWS::Serverless::Function"
        image_function_resource = Resource(key="image_function", assets=[ImageAsset()])
        image_function_resource["Type"] = "AWS::Serverless::Function"
        resources = DictSection("Resources", items=[zip_function_resource, image_function_resource])
        stack = Stack()
        stack["Resources"] = resources
        self.assertEqual(stack.find_function_resources_of_package_type(ZIP), [zip_function_resource])

    def test_find_function_resources_of_package_type_image(self):
        zip_function_resource = Resource(key="zip_function", assets=[S3Asset()])
        zip_function_resource["Type"] = "AWS::Serverless::Function"
        image_function_resource = Resource(key="image_function", assets=[ImageAsset()])
        image_function_resource["Type"] = "AWS::Serverless::Function"
        resources = DictSection("Resources", items=[zip_function_resource, image_function_resource])
        stack = Stack()
        stack["Resources"] = resources
        self.assertEqual(stack.find_function_resources_of_package_type(IMAGE), [image_function_resource])
