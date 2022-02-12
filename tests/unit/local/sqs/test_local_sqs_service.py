from collections import OrderedDict
from unittest import TestCase
from unittest.mock import Mock, ANY, patch

from samcli.lib.providers.provider import Stack
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.local.sqs.local_sqs_service import MessagePayload, SqsResource, SqsEventMap, LocalSqsService


class TestMessagePayload(TestCase):
    def setUp(self):
        self.stderr = Mock()
        self.message = Mock()
        self.message.body = "test"
        self.lambda_runner = Mock()
        self.message_payload = MessagePayload(
            function_name="FunctionName",
            lambda_runner=self.lambda_runner,
            stderr=self.stderr,
            message_list=[self.message, self.message],
            queue_arn="arn:QueueName",
        )

    def test_delete(self):
        self.message_payload.delete()
        self.assertTrue(self.message.delete.call_count == 2)

    def test_get_event(self):
        event = self.message_payload.get_event()
        self.assertTrue(
            event
            == (
                '{"Records": [{"messageId": "00000000-0000-0000-0000-000000000000", '
                '"eventSource": "local:elasticmq", "eventSourceARN": "arn:QueueName", '
                '"awsRegion": "local", "body": "test"}, {"messageId": '
                '"00000000-0000-0000-0000-000000000000", "eventSource": "local:elasticmq", '
                '"eventSourceARN": "arn:QueueName", "awsRegion": "local", "body": "test"}]}'
            )
        )

    def test_send_event(self):
        self.message_payload.delete = Mock()
        self.message_payload.send_event()
        self.lambda_runner.invoke.assert_called_once_with(
            function_identifier=self.message_payload.function_name,
            event=self.message_payload.get_event(),
            stdout=ANY,
            stderr=self.stderr,
        )

        self.message_payload.delete.assert_called_once()

    def test_send_event_no_function(self):
        self.message_payload.delete = Mock()
        self.lambda_runner.invoke.side_effect = FunctionNotFound("Nope")
        self.message_payload.send_event()
        self.message_payload.delete.assert_called_once()


class TestSqsResource(TestCase):
    def setUp(self):
        self.message = Mock()
        self.queue = Mock()
        self.queue.attributes = {"QueueArn": "arn:QueueName"}
        self.queue.receive_messages.return_value = [self.message]
        self.stderr = Mock()
        self.lambda_runner = Mock()
        self.sqs_event_map = SqsEventMap(function_name="FunctionName", batch_size=10)

        self.sqs_resource = SqsResource(
            content_based_deduplication=False,
            delay_seconds=60,
            fifo_queue=False,
            queue_name="Queue",
            receive_message_wait_time_seconds=0,
            tags={},
            visibility_timeout=900,
            event_map_list=[self.sqs_event_map],
            lambda_runner=self.lambda_runner,
            stderr=self.stderr,
            queue=self.queue,
        )

    def test_get_config(self):
        self.assertTrue(
            self.sqs_resource.get_config()
            == {
                "Queue": {
                    "contentBasedDeduplication": False,
                    "defaultVisibilityTimeout": "900 seconds",
                    "delay": "60 seconds",
                    "fifo": False,
                    "receiveMessageWait": "0 seconds",
                    "tags": {},
                }
            }
        )

    @patch("samcli.local.sqs.local_sqs_service.MessagePayload")
    def test_get_call_list(self, message_payload):
        call_list = self.sqs_resource.get_call_list()

        message_payload.assert_called_once_with(
            message_list=[self.message],
            queue_arn="arn:QueueName",
            function_name="FunctionName",
            lambda_runner=self.lambda_runner,
            stderr=self.stderr,
        )

        self.assertTrue(call_list == [message_payload().send_event])

    def test_get_call_list_no_queue(self):
        self.sqs_resource.queue = None

        with self.assertRaises(Exception) as context:
            self.sqs_resource.get_call_list()
            self.assertTrue("Queue not found!" in context.exception)

    def test_get_call_list_no_messages(self):
        self.queue.receive_messages.return_value = []
        self.assertTrue(self.sqs_resource.get_call_list() == [])


class TestLocalSqsService(TestCase):
    def setUp(self):
        self.invoke_context = Mock()
        self.stack = Stack(
            parent_stack_path="",
            name="",
            location="template.yaml",
            parameters={},
            template_dict=OrderedDict(
                [
                    ("AWSTemplateFormatVersion", "2010-09-09"),
                    ("Transform", ["AWS::Serverless-2016-10-31"]),
                    ("Description", "python3.8\nSAM Template\n"),
                    ("Globals", OrderedDict([("Function", OrderedDict([("Timeout", 300)]))])),
                    ("Parameters", OrderedDict()),
                    ("Conditions", OrderedDict()),
                    (
                        "Resources",
                        OrderedDict(
                            [
                                (
                                    "FunctionOne",
                                    OrderedDict(
                                        [
                                            ("Type", "AWS::Serverless::Function"),
                                            (
                                                "Properties",
                                                OrderedDict(
                                                    [
                                                        (
                                                            "Events",
                                                            OrderedDict(
                                                                [
                                                                    (
                                                                        "InstantEvent",
                                                                        OrderedDict(
                                                                            [
                                                                                ("Type", "SQS"),
                                                                                (
                                                                                    "Properties",
                                                                                    OrderedDict(
                                                                                        [
                                                                                            (
                                                                                                "Queue",
                                                                                                OrderedDict(
                                                                                                    [
                                                                                                        (
                                                                                                            "Fn::GetAtt",
                                                                                                            [
                                                                                                                "Instant",
                                                                                                                "Arn",
                                                                                                            ],
                                                                                                        )
                                                                                                    ]
                                                                                                ),
                                                                                            ),
                                                                                            ("BatchSize", 10),
                                                                                        ]
                                                                                    ),
                                                                                ),
                                                                            ]
                                                                        ),
                                                                    ),
                                                                    (
                                                                        "DelayOneEvent",
                                                                        OrderedDict(
                                                                            [
                                                                                ("Type", "SQS"),
                                                                                (
                                                                                    "Properties",
                                                                                    OrderedDict(
                                                                                        [
                                                                                            (
                                                                                                "Queue",
                                                                                                OrderedDict(
                                                                                                    [
                                                                                                        (
                                                                                                            "Fn::GetAtt",
                                                                                                            [
                                                                                                                "DelayOne",
                                                                                                                "Arn",
                                                                                                            ],
                                                                                                        )
                                                                                                    ]
                                                                                                ),
                                                                                            ),
                                                                                            ("BatchSize", 10),
                                                                                        ]
                                                                                    ),
                                                                                ),
                                                                            ]
                                                                        ),
                                                                    ),
                                                                    (
                                                                        "DelayFifteenEvent",
                                                                        OrderedDict(
                                                                            [
                                                                                ("Type", "SQS"),
                                                                                (
                                                                                    "Properties",
                                                                                    OrderedDict(
                                                                                        [
                                                                                            (
                                                                                                "Queue",
                                                                                                OrderedDict(
                                                                                                    [
                                                                                                        (
                                                                                                            "Fn::GetAtt",
                                                                                                            [
                                                                                                                "DelayFifteen",
                                                                                                                "Arn",
                                                                                                            ],
                                                                                                        )
                                                                                                    ]
                                                                                                ),
                                                                                            ),
                                                                                            ("BatchSize", 10),
                                                                                        ]
                                                                                    ),
                                                                                ),
                                                                            ]
                                                                        ),
                                                                    ),
                                                                ]
                                                            ),
                                                        )
                                                    ]
                                                ),
                                            ),
                                            ("Metadata", OrderedDict([("SamResourceId", "FunctionOne")])),
                                        ]
                                    ),
                                ),
                                (
                                    "FunctionTwo",
                                    OrderedDict(
                                        [
                                            ("Type", "AWS::Serverless::Function"),
                                            ("Properties", OrderedDict()),
                                            ("Metadata", OrderedDict([("SamResourceId", "FunctionTwo")])),
                                        ]
                                    ),
                                ),
                                (
                                    "FunctionThree",
                                    OrderedDict(
                                        [
                                            ("Type", "AWS::Serverless::Function"),
                                            (
                                                "Properties",
                                                OrderedDict(
                                                    [
                                                        (
                                                            "Events",
                                                            OrderedDict(
                                                                [
                                                                    ("Other", OrderedDict([("Type", "SNS")])),
                                                                    (
                                                                        "Orphan",
                                                                        OrderedDict(
                                                                            [
                                                                                ("Type", "SQS"),
                                                                                (
                                                                                    "Properties",
                                                                                    OrderedDict(
                                                                                        [
                                                                                            (
                                                                                                "Queue",
                                                                                                OrderedDict(
                                                                                                    [
                                                                                                        (
                                                                                                            "Fn::GetAtt",
                                                                                                            [
                                                                                                                "Orphan",
                                                                                                                "Arn",
                                                                                                            ],
                                                                                                        )
                                                                                                    ]
                                                                                                ),
                                                                                            ),
                                                                                            ("BatchSize", 10),
                                                                                        ]
                                                                                    ),
                                                                                ),
                                                                            ]
                                                                        ),
                                                                    ),
                                                                    (
                                                                        "DelayFifteenEvent",
                                                                        OrderedDict(
                                                                            [
                                                                                ("Type", "SQS"),
                                                                                (
                                                                                    "Properties",
                                                                                    OrderedDict(
                                                                                        [
                                                                                            (
                                                                                                "Queue",
                                                                                                OrderedDict(
                                                                                                    [
                                                                                                        (
                                                                                                            "Fn::GetAtt",
                                                                                                            [
                                                                                                                "DelayFifteen",
                                                                                                                "Arn",
                                                                                                            ],
                                                                                                        )
                                                                                                    ]
                                                                                                ),
                                                                                            ),
                                                                                            ("BatchSize", 10),
                                                                                        ]
                                                                                    ),
                                                                                ),
                                                                            ]
                                                                        ),
                                                                    ),
                                                                ]
                                                            ),
                                                        )
                                                    ]
                                                ),
                                            ),
                                            ("Metadata", OrderedDict([("SamResourceId", "FunctionThree")])),
                                        ]
                                    ),
                                ),
                                (
                                    "Instant",
                                    OrderedDict(
                                        [
                                            ("Type", "AWS::SQS::Queue"),
                                            (
                                                "Properties",
                                                OrderedDict([("QueueName", "Instant"), ("VisibilityTimeout", 300)]),
                                            ),
                                        ]
                                    ),
                                ),
                                (
                                    "DelayOne",
                                    OrderedDict(
                                        [
                                            ("Type", "AWS::SQS::Queue"),
                                            (
                                                "Properties",
                                                OrderedDict(
                                                    [
                                                        ("QueueName", "DelayOne"),
                                                        ("DelaySeconds", 60),
                                                        ("VisibilityTimeout", 300),
                                                    ]
                                                ),
                                            ),
                                        ]
                                    ),
                                ),
                                (
                                    "DelayFifteen",
                                    OrderedDict(
                                        [
                                            ("Type", "AWS::SQS::Queue"),
                                            (
                                                "Properties",
                                                OrderedDict(
                                                    [
                                                        ("QueueName", "DelayFifteen"),
                                                        ("DelaySeconds", 900),
                                                        ("VisibilityTimeout", 300),
                                                    ]
                                                ),
                                            ),
                                        ]
                                    ),
                                ),
                            ]
                        ),
                    ),
                ]
            ),
            metadata=None,
        )

        self.invoke_context.stacks = [self.stack]

    @patch("samcli.local.sqs.local_sqs_service.LocalSqsService._write_file")
    @patch("samcli.local.sqs.local_sqs_service.docker")
    def test_init(self, docker, _write_file):
        LocalSqsService(invoke_context=self.invoke_context)

    @patch("samcli.local.sqs.local_sqs_service.LocalSqsService._get_resource_type_map")
    def test_no_sqs_resources(self, _get_resource_type_map):
        _get_resource_type_map.return_value = {}
        LocalSqsService(invoke_context=self.invoke_context)
