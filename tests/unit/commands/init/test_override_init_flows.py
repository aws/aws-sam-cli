from unittest import TestCase
from unittest.mock import patch, Mock

from parameterized import parameterized

from samcli.commands.exceptions import InvalidInitOptionException
from samcli.commands.init.init_templates import InitTemplates
from samcli.commands.init.override_init_flows import GraphQlInitFlow, OverrideWorkflowExecutor, get_override_workflow


class TestGraphQLInitFlow(TestCase):
    def setUp(self) -> None:
        self.init_templates = InitTemplates()
        preprocessed_options = self.init_templates.get_preprocessed_manifest()
        self.graphql_flow = GraphQlInitFlow(
            name="my-app",
            templates=self.init_templates,
            preprocessed_options=preprocessed_options,
            use_case="GraphQLApi Hello World Example",
            output_dir="outdir/",
        )

    @patch("samcli.commands.init.override_init_flows.click")
    def test_print_next_command_recommendation(self, mock_click):
        self.graphql_flow.print_next_command_recommendation()
        mock_click.secho.assert_called_with(
            "\nCommands you can use next\n=========================\n"
            "[*] Create pipeline: cd my-app && sam pipeline init --bootstrap\n"
            "[*] Validate SAM template: cd my-app && sam validate\n"
            "[*] Test GraqhQL resolvers in the Cloud: cd my-app && sam sync --stack-name {stack-name} --watch\n",
            fg="yellow",
        )

    @patch("samcli.commands.init.override_init_flows.click")
    def test_print_summary_message(self, mock_click):
        self.graphql_flow.print_summary_message()
        mock_click.echo.assert_called_with(
            "\n    -----------------------\n    "
            "Generating application:\n    -----------------------\n"
            "    Name: my-app\n"
            "    Runtime: N/A\n"
            "    Architectures: N\n"
            "    Dependency Manager: N/A\n"
            "    Application Template: GraphQLApi Hello World Example\n"
            "    Output Directory: outdir/\n"
            "    Configuration file: outdir/my-app/samconfig.toml\n\n"
            "    Next steps can be found in the README file at outdir/my-app/README.md\n        "
        )

    @patch("samcli.commands.init.override_init_flows.do_generate")
    def test_generate_project(self, mock_do_generate):
        preprocessed_options = {
            "GraphQLApi Hello World Example": {
                "appsync_js1.x": {
                    "Zip": [
                        {
                            "directory": "appsync_js1.x",
                            "displayName": "GraphQLApi Hello World Example",
                            "dependencyManager": "npm",
                            "appTemplate": "hello-world",
                            "packageType": "Zip",
                            "useCaseName": "GraphQLApi Hello World Example",
                        }
                    ]
                }
            }
        }
        init_templates = Mock()
        init_templates.location_from_app_template.return_value = (
            "/home/.aws-sam/aws-sam-cli-app-templates/appsync_js1.x/hello-world"
        )
        graphql_init_flow = GraphQlInitFlow(
            name="my-app",
            templates=init_templates,
            preprocessed_options=preprocessed_options,
            use_case="GraphQLApi Hello World Example",
            output_dir="outdir/",
        )
        graphql_init_flow.generate_project()
        mock_do_generate.assert_called_once_with(
            location="/home/.aws-sam/aws-sam-cli-app-templates/appsync_js1.x/hello-world",
            runtime=None,
            dependency_manager=None,
            package_type=None,
            output_dir="outdir/",
            name="my-app",
            no_input=True,
            extra_context={"project_name": "my-app"},
            tracing=False,
            application_insights=False,
        )

    @patch("samcli.commands.init.override_init_flows.do_generate")
    def test_generate_project_invalid_manifest(self, mock_do_generate):
        preprocessed_options = {
            "GraphQLApi Hello World Example": {
                "appsync_js1.x": {
                    "Zip": [
                        {
                            "directory": "appsync_js1.x",
                            "displayName": "GraphQLApi Hello World Example",
                            "dependencyManager": "npm",
                            "appTemplate": "hello-world",
                            "packageType": "Zip",
                            "useCaseName": "GraphQLApi Hello World Example",
                        },
                        {
                            "directory": "appsync_js2.x",
                            "displayName": "GraphQLApi Hello World Example",
                            "dependencyManager": "npm",
                            "appTemplate": "hello-world",
                            "packageType": "Zip",
                            "useCaseName": "GraphQLApi Hello World Example",
                        },
                    ]
                }
            },
        }
        graphql_init_flow = GraphQlInitFlow(
            name="my-app",
            templates=Mock(),
            preprocessed_options=preprocessed_options,
            use_case="GraphQLApi Hello World Example",
            output_dir="outdir/",
        )
        with self.assertRaises(InvalidInitOptionException) as ex:
            graphql_init_flow.generate_project()
        self.assertEqual(
            ex.exception.message,
            "Matched more than one AppSync template. Additional "
            "identifiers required for determining the correct template.",
        )


class TestOverrideWorkflowExecutor(TestCase):
    def test_execute(self):
        override_workflow = Mock()
        workflow_executor = OverrideWorkflowExecutor(override_workflow)
        workflow_executor.execute()
        override_workflow.generate_project.assert_called_once_with()
        override_workflow.generate_project.print_summary_message()
        override_workflow.generate_project.print_next_command_recommendation()

    @parameterized.expand(
        [
            (
                "GraphQLApi Hello World Example",
                GraphQlInitFlow,
            ),
            ("Hello World", None),
            ("", None),
        ]
    )
    def test_get_override_workflow(self, use_case, expected):
        response = get_override_workflow(use_case)
        self.assertEqual(response, expected)
