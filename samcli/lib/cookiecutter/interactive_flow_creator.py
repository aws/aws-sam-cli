""" This module parses a json/yaml file that defines a flow of questions to fulfill the cookiecutter context"""

from typing import Dict, Optional, Tuple

import yaml

from samcli.commands.exceptions import UserException
from samcli.yamlhelper import parse_yaml_file

from .interactive_flow import InteractiveFlow
from .question import Question, QuestionFactory


class QuestionsNotFoundException(UserException):
    pass


class QuestionsFailedParsingException(UserException):
    pass


class InteractiveFlowCreator:
    @staticmethod
    def create_flow(flow_definition_path: str, extra_context: Optional[Dict] = None) -> InteractiveFlow:
        """
        This method parses the given json/yaml file to create an InteractiveFLow. It expects the file to define
        a list of questions. It parses the questions and add it to the flow in the same order they are defined
        in the file, i.e. the default next-question of a given question will be the next one defined in the file,
        while also respecting the question-defined _next_question map if provided.

        Parameters:
        ----------
        flow_definition_path: str
            A path to a json/yaml file that defines the questions of the flow. the file is expected to be in the
            following format:
            {
                "questions": [
                    {
                      "key": "key of the corresponding cookiecutter config",
                      "question": "the question to prompt to the user",
                      "kind": "the kind of the question, for example: confirm",
                      "isRequired": true/false,
                      # optional branching logic to jump to a particular question based on the answer. if not given
                      # will automatically go to next question
                      "nextQuestion": {
                        "True": "key of the question to jump to if the user answered 'Yes'",
                        "False": "key of the question to jump to if the user answered 'Yes'",
                      }
                      "default": "default_answer",
                      # the default value can also be loaded from cookiecutter context
                      # with a key path whose key path item can be loaded from cookiecutter as well.
                      "default": {
                        "keyPath": [
                            {
                                "valueOf": "key-of-another-question"
                            },
                            "pipeline_user"
                        ]
                      }
                      # assuming the answer of "key-of-another-question" is "ABC"
                      # the default value will be load from cookiecutter context with key "['ABC', 'pipeline_user]"
                    },
                    ...
                ]
            }
        extra_context: Dict
            if the template contains variable($variableName) this parameter provides the values for those variables.

        Returns: InteractiveFlow(questions={k1: q1, k2: q2, ...}, first_question_key="first question's key")
        """
        questions, first_question_key = InteractiveFlowCreator._load_questions(flow_definition_path, extra_context)
        return InteractiveFlow(questions=questions, first_question_key=first_question_key)

    @staticmethod
    def _load_questions(
        flow_definition_path: str, extra_context: Optional[Dict] = None
    ) -> Tuple[Dict[str, Question], str]:
        previous_question: Optional[Question] = None
        first_question_key: str = ""
        questions: Dict[str, Question] = {}
        questions_definition = InteractiveFlowCreator._parse_questions_definition(flow_definition_path, extra_context)

        try:
            for question in questions_definition.get("questions", []):
                q = QuestionFactory.create_question_from_json(question)
                if not first_question_key:
                    first_question_key = q.key
                elif previous_question and not previous_question.default_next_question_key:
                    previous_question.set_default_next_question_key(q.key)
                questions[q.key] = q
                previous_question = q
            return questions, first_question_key
        except (KeyError, ValueError, AttributeError, TypeError) as ex:
            raise QuestionsFailedParsingException(f"Failed to parse questions: {str(ex)}") from ex

    @staticmethod
    def _parse_questions_definition(file_path: str, extra_context: Optional[Dict] = None) -> Dict:
        """
        Read the questions definition file, do variable substitution, parse it as JSON/YAML

        Parameters
        ----------
        file_path : string
            Path to the questions definition to read
        extra_context : Dict
            if the file contains variable($variableName) this parameter provides the values for those variables.

        Raises
        ------
        QuestionsNotFoundException: if the file_path doesn't exist
        QuestionsFailedParsingException: if any error occurred during variables substitution or content parsing

        Returns
        -------
        questions data as a dictionary
        """

        try:
            return parse_yaml_file(file_path=file_path, extra_context=extra_context)
        except FileNotFoundError as ex:
            raise QuestionsNotFoundException(f"questions definition file not found at {file_path}") from ex
        except (KeyError, ValueError, yaml.YAMLError) as ex:
            raise QuestionsFailedParsingException(f"Failed to parse questions: {str(ex)}") from ex
