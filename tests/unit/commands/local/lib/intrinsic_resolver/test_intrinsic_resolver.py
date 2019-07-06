from unittest import TestCase

from parameterized import parameterized

from samcli.commands.local.lib.intrinsic_resolver.invalid_intrinsic_exception import InvalidIntrinsicException
from samcli.commands.local.lib.intrinsic_resolver.intrinsic_property_resolver import IntrinsicResolver


class TestIntrinsicFnJoinResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(symbol_resolver={})

    def test_basic_fn_join(self):
        intrinsic = {
            "Fn::Join": [",", ["a", "b", "c", "d"]]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "a,b,c,d")

    def test_nested_fn_join(self):
        intrinsic_base_1 = {
            "Fn::Join": [",", ["a", "b", "c", "d"]]
        }
        intrinsic_base_2 = {
            "Fn::Join": [";", ["g", "h", "i", intrinsic_base_1]]
        }
        intrinsic = {
            "Fn::Join": [":", [intrinsic_base_1, "e", "f", intrinsic_base_2]]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "a,b,c,d:e:f:g;h;i;a,b,c,d")

    def test_delimiter_fn_join(self):
        intrinsic_base_1 = {
            "Fn::Join": ["", ["t", "e", "s", "t"]]
        }
        intrinsic = {
            "Fn::Join": [intrinsic_base_1, ["a", "e", "f", "d"]]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "atestetestftestd")

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, "Test", {}, 42, object, None]
    ])
    def test_fn_join_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Join": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the first list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None]
    ])
    def test_fn_join_delimiter_invalid_type(self, name, delimiter):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Join": [delimiter, []]
            })

    @parameterized.expand([
        ("Invalid Types to the listOfObjects for Fn::Join with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, "t", None]
    ])
    def test_fn_list_of_objects_invalid_type(self, name, list_of_objects):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Join": ["", list_of_objects]
            })

    @parameterized.expand([
        ("Invalid Types to the listOfObjects for Fn::Join with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None]
    ])
    def test_fn_join_items_all_str(self, name, single_obj):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Join": ["", ["test", single_obj, "abcd"]]
            })


class TestIntrinsicFnSplitResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(symbol_resolver={})

    def test_basic_fn_split(self):
        intrinsic = {
            "Fn::Split": ["|", "a|b|c"]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, ["a", "b", "c"])

    def test_nested_fn_split(self):
        intrinsic_base_1 = {
            "Fn::Split": [";", {"Fn::Join": [";", ["a", "b", "c"]]}]
        }

        intrinsic_base_2 = {
            "Fn::Join": [",", intrinsic_base_1]
        }
        intrinsic = {
            "Fn::Split": [",", {"Fn::Join": [",", [intrinsic_base_2, ",e", ",f,", intrinsic_base_2]]}]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, ['a', 'b', 'c', '', 'e', '', 'f', '', 'a', 'b', 'c'])

    def test_delimiter_fn_split(self):
        intrinsic_base_1 = {
            "Fn::Join": ["", [","]]
        }
        intrinsic = {
            "Fn::Split": [intrinsic_base_1, {"Fn::Join": [",", ["a", "e", "f", "d"]]}]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, ['a', 'e', 'f', 'd'])

    @parameterized.expand([
        ("Invalid Types to the argument of Fn::Split with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, "Test", {}, 42, object]
    ])
    def test_fn_split_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Split": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the first argument of Fn::Split with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object]
    ])
    def test_fn_split_delimiter_invalid_type(self, name, delimiter):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Split": [delimiter, []]
            })

    @parameterized.expand([
        ("Invalid Types to the source_string for Fn::Split with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object]
    ])
    def test_fn_split_source_string_invalid_type(self, name, source_string):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Split": ["", source_string]
            })


class TestIntrinsicFnBase64Resolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(symbol_resolver={})

    def test_basic_fn_split(self):
        intrinsic = {
            "Fn::Base64": "AWS CloudFormation"
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, 'QVdTIENsb3VkRm9ybWF0aW9u')

    def test_nested_fn_base64(self):
        intrinsic_base_1 = {
            "Fn::Base64": "AWS CloudFormation"
        }

        intrinsic_base_2 = {
            "Fn::Base64": intrinsic_base_1
        }
        intrinsic = {
            "Fn::Base64": {"Fn::Join": [",", [intrinsic_base_2, ",e", ",f,", intrinsic_base_2]]}
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "VVZaa1ZFbEZUbk5pTTFaclVtMDVlV0pYUmpCaFZ6bDEsLGUsLGYsLFVWWmtWRWxGVG5OaU0xWnJ"
                                  "VbTA1ZVdKWFJqQmhWemwx")

    @parameterized.expand([
        ("Invalid Types to the argument of Fn::Base64 with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, 42, object, None]
    ])
    def test_fn_base64_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Base64": intrinsic
            })


class TestIntrinsicFnSelectResolver(TestCase):
    def setUp(self):
        self.resolver = IntrinsicResolver(symbol_resolver={})

    def test_basic_fn_select(self):
        intrinsic = {
            "Fn::Select": [2, ["a", "b", "c", "d"]]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "c")

    def test_nested_fn_select(self):
        intrinsic_base_1 = {
            "Fn::Select": [0, ["a", "b", "c", "d"]]
        }
        intrinsic_base_2 = {
            "Fn::Join": [";", ["g", "h", "i", intrinsic_base_1]]
        }
        intrinsic = {
            "Fn::Select": [3, [intrinsic_base_2, "e", "f", intrinsic_base_2]]
        }
        result = self.resolver.intrinsic_property_resolver(intrinsic)
        self.assertEquals(result, "g;h;i;a")

    @parameterized.expand([
        ("Invalid Types to the list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, "Test", {}, 42, object, None]
    ])
    def test_fn_select_arguments_invalid_formats(self, name, intrinsic):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Select": intrinsic
            })

    @parameterized.expand([
        ("Invalid Types to the first list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, object, "3", None]
    ])
    def test_fn_select_index_invalid_index_type(self, name, index):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Select": [index, [0]]
            })

    @parameterized.expand([
        ("Invalid Types to the for Fn::Select with type {} should fail".format(number), number)
        for number in
        [-2, 7]
    ])
    def test_fn_select_invalid_index(self, name, index):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Select": [index, []]
            })

    @parameterized.expand([
        ("Invalid Types to the second list argument with type {} should fail".format(primitive), primitive)
        for primitive in
        [True, False, {}, object, "3", 33, None]
    ])
    def test_fn_select_objects_invalid_type(self, name, argument):
        with self.assertRaises(InvalidIntrinsicException, msg=name):
            self.resolver.intrinsic_property_resolver({
                "Fn::Select": [0, argument]
            })


