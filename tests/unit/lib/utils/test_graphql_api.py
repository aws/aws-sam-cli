from unittest import TestCase
from samcli.lib.utils.graphql_api import CODE_ARTIFACT_PROPERTY, find_all_paths_and_values


class Test_find_all_paths_and_values(TestCase):
    def test_finds_all_paths_with_CODE_ARTIFACT_PROPERTY(self):
        resource = {
            "SchemaUri": "schema.graphql",
            "Functions": {
                "Func1": {"CodeUri": "foo/bar"},
                "Func2": {"InlineCode": "supercode"},
            },
            "Resolvers": {"Mutation": {"Resolver1": {"CodeUri": "foo/baz"}, "Resolver2": {}}},
        }
        paths_values = find_all_paths_and_values(CODE_ARTIFACT_PROPERTY, resource)
        self.assertEqual(
            paths_values,
            [
                ("Functions.Func1.CodeUri", "foo/bar"),
                ("Resolvers.Mutation.Resolver1.CodeUri", "foo/baz"),
            ],
        )

    def test_finds_nothing_when_no_CODE_ARTIFACT_PROPERTY(self):
        resource = {
            "SchemaUri": "schema.graphql",
            "Functions": {
                "Func1": {"InlineCode": "supercode"},
                "Func2": {"InlineCode": "supercode"},
            },
            "Resolvers": {"Mutation": {"Resolver1": {}, "Resolver2": {}}},
        }
        paths_values = find_all_paths_and_values(CODE_ARTIFACT_PROPERTY, resource)
        self.assertEqual(
            paths_values,
            [],
        )

    def test_finds_nothing_when_no_resolvers_or_functions(self):
        resource = {
            "SchemaUri": "schema.graphql",
        }
        paths_values = find_all_paths_and_values(CODE_ARTIFACT_PROPERTY, resource)
        self.assertEqual(
            paths_values,
            [],
        )
