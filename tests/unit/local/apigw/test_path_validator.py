from unittest import TestCase

from parameterized import parameterized

from samcli.local.apigw.path_validator import PathValidator


class TestPathValidator(TestCase):

    @parameterized.expand([("/{resource+}"),
                           ("/a/{id}/b/{resource+}"),
                           ("/a/b/{proxy}/{resource+}"),
                           ("/{id}/{something+}"),
                           ("/{a}/{b}/{c}/{d+}"),
                           ("/totally/static/path"),
                           ("/something/{dynamic}"),
                           ("/strange-chars/H3ll0_World.1234")
                           ])
    def test_is_valid_path(self, path):
        is_valid = PathValidator.is_valid(path)

        self.assertTrue(is_valid)

    @parameterized.expand([("/~route-with-tilde"),
                           ("/path/to/~route"),
                           ("/~path/{id}")
                           ])
    def test_is_not_valid_path(self, path):
        is_valid = PathValidator.is_valid(path)

        self.assertFalse(is_valid)
