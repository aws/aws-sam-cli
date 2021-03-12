""" This module parses a json/yaml file that defines a flow of questions to fulfill the cookiecutter context"""
from typing import Dict, Optional, Tuple
from samcli.commands._utils.template import get_template_data
from .interactive_flow import InteractiveFlow
from .question import Question, QuestionKind


class InteractiveFlowCreator:
    @staticmethod
    def create_flow(flow_definition_path: str):
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
                "Questions": [
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
                    },
                    ...
                ]
            }

        Returns: InteractiveFlow(questions={k1: q1, k2: q2, ...}, first_question_key="first question's key")
        """
        questions, first_question_key = InteractiveFlowCreator._load_questions(flow_definition_path)
        return InteractiveFlow(questions=questions, first_question_key=first_question_key)

    @staticmethod
    def _load_questions(flow_definition_path: str) -> Tuple[Dict[str, Question], str]:
        previous_question: Optional[Question] = None
        first_question_key: str = ""
        questions: Dict[str, Question] = {}
        template_data = get_template_data(flow_definition_path)

        for question in template_data.get("Questions"):
            q = InteractiveFlowCreator._create_question_from_json(question)
            if not first_question_key:
                first_question_key = q.key
            elif previous_question and not previous_question.get_default_next_question_key():
                previous_question.set_default_next_question_key(q.key)
            questions[q.key] = q
            previous_question = q
        return questions, first_question_key

    @staticmethod
    def _create_question_from_json(question_json: Dict) -> Question:
        key = question_json["key"]
        text = question_json["question"]
        options = question_json.get("options")
        default = question_json.get("default")
        is_required = question_json.get("isRequired")
        next_question_map = question_json.get("nextQuestion")
        kind_str = question_json.get("kind")
        kind = QuestionKind[kind_str] if kind_str else None
        return Question(
            key=key,
            text=text,
            options=options,
            default=default,
            is_required=is_required,
            next_question_map=next_question_map,
            kind=kind,
        )
