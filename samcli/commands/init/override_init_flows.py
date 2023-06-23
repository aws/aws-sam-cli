"""
Module containing interfaces and implementations for override workflows
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional, Type

import click

from samcli.commands._utils.options import generate_next_command_recommendation
from samcli.commands.exceptions import InvalidInitOptionException
from samcli.commands.init.init_flow_helpers import generate_summary_message
from samcli.commands.init.init_generator import do_generate
from samcli.commands.init.init_templates import InitTemplates
from samcli.lib.utils.packagetype import ZIP

NOT_APPLICABLE = "N/A"
APPSYNC_OVERRIDE_USE_CASE = "GraphQLApi Hello World Example"


class OverrideFlow(ABC):
    """
    Interface for overriding the default init workflow for app templates that don't conform to the standard flow
    e.g if an app template doesn't include a Lambda function,
    many of the questions asked in the default flow are not relevant and can be skipped
    """

    def __init__(
        self,
        templates: InitTemplates,
        use_case: str,
        preprocessed_options: dict,
        name: Optional[str],
        output_dir: Optional[str],
    ):
        self._name = name
        self._templates = templates
        self._use_case = use_case
        self._preprocessed_options = preprocessed_options
        self._output_dir = output_dir

    @abstractmethod
    def generate_project(self):
        """
        Generate a project from an app template with a guided
        workflow that deviates from the steps in the default workflow

        This method should call `do_generate` to create the project
        """

    @abstractmethod
    def print_summary_message(self):
        """
        Display the summary message based on the override workflow
        """

    @abstractmethod
    def print_next_command_recommendation(self):
        """ "
        Display the next command recommendations based on the override workflow
        """

    def get_project_name(self):
        """
        Helper method to get the project name if not provided.
        This is a common prompt that should be applicable to any project.
        """
        if not self._name:
            self._name = click.prompt("\nProject name", type=str, default="sam-app")


class GraphQlInitFlow(OverrideFlow):
    APPSYNC_IDENTIFIER = "appsync_js1.x"

    def generate_project(self):
        """
        Perform the relevant guided flow steps to initialize an AppSync app template
        """
        self.get_project_name()
        template = self._preprocessed_options.get(self._use_case, {})
        matched_appsync_templates = template.get(self.APPSYNC_IDENTIFIER, {}).get(ZIP)
        if len(matched_appsync_templates) > 1:
            raise InvalidInitOptionException(
                "Matched more than one AppSync template. Additional "
                "identifiers required for determining the correct template."
            )
        app_template = matched_appsync_templates[0].get("appTemplate", "")
        location = self._templates.location_from_app_template(None, self.APPSYNC_IDENTIFIER, None, None, app_template)
        extra_context = {
            "project_name": self._name,
        }
        do_generate(
            location=location,
            runtime=None,
            dependency_manager=None,
            package_type=None,
            output_dir=self._output_dir,
            name=self._name,
            no_input=True,
            extra_context=extra_context,
            tracing=False,
            application_insights=False,
        )

    def print_summary_message(self):
        """
        Display the summary message for a GraphQL app template
        """
        summary_msg = generate_summary_message(
            package_type=ZIP,
            runtime=NOT_APPLICABLE,
            base_image=NOT_APPLICABLE,
            dependency_manager=NOT_APPLICABLE,
            output_dir=self._output_dir,
            name=self._name,
            app_template=self._use_case,
            architecture=[NOT_APPLICABLE],
        )
        click.echo(summary_msg)

    def print_next_command_recommendation(self):
        """
        Display the next command recommendations for a GraphQL app template
        """
        command_suggestions = generate_next_command_recommendation(
            [
                ("Create pipeline", f"cd {self._name} && sam pipeline init --bootstrap"),
                ("Validate SAM template", f"cd {self._name} && sam validate"),
                (
                    "Test GraqhQL resolvers in the Cloud",
                    f"cd {self._name} && sam sync --stack-name {{stack-name}} --watch",
                ),
            ]
        )
        click.secho(command_suggestions, fg="yellow")


class OverrideWorkflowExecutor:
    """
    Class to handle execution of an override workflow
    """

    _override_workflow: OverrideFlow

    def __init__(self, override_workflow: OverrideFlow):
        self._override_workflow = override_workflow

    def execute(self):
        """
        Execute the relevant steps of an override workflow interface
        """
        self._override_workflow.generate_project()
        self._override_workflow.print_summary_message()
        self._override_workflow.print_next_command_recommendation()


NON_LAMBDA_WORKFLOWS: Dict[str, Type[OverrideFlow]] = {APPSYNC_OVERRIDE_USE_CASE: GraphQlInitFlow}


def get_override_workflow(use_case: str) -> Optional[Type[OverrideFlow]]:
    """
    Get an init workflow to override the default workflow based on a particular use-case
    Parameters
    ----------
    use_case: str
        App template use case

    Returns
    -------
    The override workflow to be passed to the override workflow executor
    """
    return NON_LAMBDA_WORKFLOWS.get(use_case, None)
