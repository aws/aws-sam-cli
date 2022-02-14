"""
Starts an elasticmq container and invokes lambda runner when poller receives messages.
"""
import asyncio
import io
import json
import logging
import signal
import sys
import threading

from time import sleep
from dataclasses import dataclass
from typing import List, Dict, Callable, Optional, Any
from pyhocon.converter import HOCONConverter  # type: ignore

import boto3
import pyhocon  # type: ignore
import docker
import docker.errors

from samcli.commands.local.cli_common.invoke_context import InvokeContext, ContainersMode
from samcli.commands.local.lib.local_lambda import LocalLambdaRunner
from samcli.lib.providers.provider import Stack

from samcli.lib.utils.stream_writer import StreamWriter
from samcli.local.lambdafn.exceptions import FunctionNotFound
from samcli.local.services.base_local_service import LambdaOutputParser

LOG = logging.getLogger(__name__)

TYPE_AWS_SERVERLESS_FUNCTION = "AWS::Serverless::Function"
TYPE_AWS_SQS_QUEUE = "AWS::SQS::Queue"


@dataclass
class SqsEventMap:
    function_name: str
    batch_size: int


@dataclass
class MessagePayload:
    function_name: str
    lambda_runner: LocalLambdaRunner
    stderr: StreamWriter
    message_list: List
    queue_arn: str

    def delete(self):
        for message in self.message_list:
            message.delete()

    def get_event(self) -> str:
        event: Dict[str, List[Dict]] = {"Records": []}

        for message in self.message_list:
            event["Records"].append(
                {
                    "messageId": "00000000-0000-0000-0000-000000000000",
                    "eventSource": "local:elasticmq",
                    "eventSourceARN": self.queue_arn,
                    "awsRegion": "local",
                    "body": message.body,
                }
            )

        return json.dumps(event)

    def send_event(self):
        stdout_stream = io.BytesIO()
        stdout_stream_writer = StreamWriter(stdout_stream, auto_flush=True)
        event = self.get_event()

        LOG.info("Sending Payload: %s", event)

        try:
            self.lambda_runner.invoke(
                function_identifier=self.function_name,
                event=event,
                stdout=stdout_stream_writer,
                stderr=self.stderr,
            )
        except FunctionNotFound:
            LOG.warning("Function %s not found.", self.function_name)

        lambda_response, _, _ = LambdaOutputParser.get_lambda_output(stdout_stream)
        LOG.info(lambda_response)
        self.delete()


@dataclass
class SqsResource:
    content_based_deduplication: bool
    delay_seconds: int
    fifo_queue: bool
    queue_name: str
    receive_message_wait_time_seconds: int
    tags: Dict[str, str]
    visibility_timeout: int
    event_map_list: List[SqsEventMap]
    lambda_runner: LocalLambdaRunner
    stderr: StreamWriter
    queue: Optional[Any] = None

    def get_config(self) -> Dict:
        return {
            self.queue_name: {
                "defaultVisibilityTimeout": f"{self.visibility_timeout} seconds",
                "delay": f"{self.delay_seconds} seconds",
                "receiveMessageWait": f"{self.receive_message_wait_time_seconds} seconds",
                "fifo": self.fifo_queue,
                "contentBasedDeduplication": self.content_based_deduplication,
                "tags": self.tags,
            }
        }

    def get_call_list(self) -> List[Callable]:
        # Don't think assigning a SQS queue to trigger multiple lambda ARNs is very practical
        # but it's possible to deploy such a configuration.
        # Just going to collect messages for each event mapping synchronously.
        call_list: List[Callable] = []

        for event_map in self.event_map_list:
            if self.queue:
                message_list = self.queue.receive_messages(MaxNumberOfMessages=event_map.batch_size)
            else:
                raise Exception("Queue not found!")

            if not message_list:
                continue

            message_payload = MessagePayload(
                message_list=message_list,
                queue_arn=self.queue.attributes["QueueArn"],
                function_name=event_map.function_name,
                lambda_runner=self.lambda_runner,
                stderr=self.stderr,
            )

            call_list.append(message_payload.send_event)

        return call_list


class LocalSqsService:
    def __init__(self, invoke_context: InvokeContext):
        # Emulate Lambda SQS event triggers if the CloudFormation template defines them.
        self._elastic_mq_container = None
        self._cwd = invoke_context.get_cwd()
        self._docker_network = invoke_context.get_docker_network()
        self._stderr = invoke_context.stderr
        self._lambda_runner = invoke_context.get_local_lambda_runner(containers_mode=ContainersMode.COLD)
        self._sqs_resource_map = self._get_sqs_resource_map(stacks=invoke_context.stacks)

        if not self._sqs_resource_map:
            LOG.info("No SQS resources found. Skipping SQS Emulation.")
            return

        # Do not use WARM lambda runtime for event triggers.
        # Can be reconsidered once WARM implements TTL and container lambda execution state is tracked.
        self._docker_client = docker.from_env()
        self._elastic_mq_config = self._write_elastic_mq_config()
        self._start_elasticmq()
        self._start_poller()

    def _stop_elasticmq(self):
        try:
            self._docker_client.containers.get(container_id=self._elastic_mq_container.id).stop()
        except docker.errors.NotFound:
            LOG.debug("ElasticMQ service already stopped.")

    def _start_elasticmq(self):
        LOG.info("Starting ElasticMQ Service.")

        self._elastic_mq_container = self._docker_client.containers.run(
            image="softwaremill/elasticmq:1.3.4",
            remove=True,
            detach=True,
            network=self._docker_network,
            name="elasticmq",
            ports={"9324/tcp": 9324},
            volumes={self._elastic_mq_config: {"bind": "/opt/elasticmq.conf", "mode": "ro"}},
        )

        def signal_handler(signum, sigframe):
            LOG.info("Stopping ElasticMQ Service.")
            self._stop_elasticmq()
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

    def _init_poller(self):
        sqs_client = boto3.resource(
            "sqs",
            endpoint_url="http://127.0.0.1:9324",
            region_name="local",
            aws_access_key_id="none",
            aws_secret_access_key="none",
        )

        # Get queues from elasticmq service.
        queue_list = list(sqs_client.queues.all())

        # Attach queues from elasticmq service to SqsResource class instances.
        for queue in queue_list:
            queue_name = queue.attributes["QueueArn"].split(":")[-1]
            self._sqs_resource_map[queue_name].queue = queue

        while True:
            call_list = []

            for queue_resource in self._sqs_resource_map.values():
                queue_call_list = queue_resource.get_call_list()

                if not queue_call_list:
                    continue

                call_list.append(*queue_call_list)

            if call_list:
                run_async(call_list=call_list)
            else:
                sleep(1)

    def _start_poller(self):
        LOG.info("Starting ElasticMQ Poller.")
        poller_thread = threading.Thread(target=self._init_poller)
        poller_thread.daemon = True
        poller_thread.start()

    def _write_elastic_mq_config(self) -> str:
        path = f"{self._cwd}/elasticmq.conf"
        elastic_mq_config: Dict[str, Dict] = {"queues": {}}
        LOG.info("Writing ElasticMQ config to %s", path)

        for sqs_resource in self._sqs_resource_map.values():
            elastic_mq_config["queues"].update(sqs_resource.get_config())

        json_string = json.dumps(elastic_mq_config)
        factory = pyhocon.ConfigFactory.parse_string(json_string)
        hocon_string = HOCONConverter.convert(factory, "hocon")
        hocon_string = f'include classpath("application.conf")\n\n{hocon_string}'
        self._write_file(path=path, hocon_string=hocon_string)

        return path

    @staticmethod
    def _write_file(path: str, hocon_string: str):
        with open(path, "w") as file:
            file.write(hocon_string)

    def _get_sqs_resource_map(self, stacks) -> Dict[str, SqsResource]:
        # Seek SQS queues that are mapped to a function in the stacks.
        # Only supports SQS mappings declared in AWS::Serverless::Function Events.
        resource_type_map = self._get_resource_type_map(stacks=stacks)
        sqs_resource_map: Dict[str, SqsResource] = {}

        if TYPE_AWS_SQS_QUEUE not in resource_type_map:
            return sqs_resource_map

        LOG.info("SQS resources found. Checking for event source mappings.")
        if TYPE_AWS_SERVERLESS_FUNCTION in resource_type_map:
            for function_name, function_attributes in resource_type_map[TYPE_AWS_SERVERLESS_FUNCTION].items():
                function_properties = function_attributes["Properties"]

                # Only care about Functions with mapped SQS event Sources.
                if "Events" not in function_properties:
                    continue

                for event_properties in function_properties["Events"].values():
                    # Only looking for SQS Events.
                    if event_properties["Type"] != "SQS":
                        continue

                    sqs_event_properties = event_properties["Properties"]
                    sqs_resource_name = sqs_event_properties["Queue"].split(":")[-1]

                    # Does the SQS resource name exist in the stacks?
                    if sqs_resource_name not in resource_type_map[TYPE_AWS_SQS_QUEUE]:
                        LOG.info("SQS Queue %s not defined in stack. Skipping.", sqs_resource_name)
                        continue

                    # Was SqsResource initialized from a previous event source mapping?
                    if sqs_resource_name in sqs_resource_map:
                        LOG.info("Adding %s to %s SQS event map.", function_name, sqs_resource_name)
                        sqs_resource_map[sqs_resource_name].event_map_list.append(
                            SqsEventMap(
                                function_name=function_name,
                                batch_size=sqs_event_properties.get("BatchSize", 10),
                            )
                        )

                        continue

                    LOG.info("Adding %s to %s SQS event map.", function_name, sqs_resource_name)
                    sqs_properties = resource_type_map[TYPE_AWS_SQS_QUEUE][sqs_resource_name]["Properties"]
                    sqs_resource_map[sqs_resource_name] = SqsResource(
                        content_based_deduplication=sqs_properties.get("ContentBasedDeduplication", False),
                        delay_seconds=sqs_properties.get("DelaySeconds", 0),
                        fifo_queue=sqs_properties.get("FifoQueue", False),
                        queue_name=sqs_resource_name,
                        receive_message_wait_time_seconds=sqs_properties.get("ReceiveMessageWaitTimeSeconds", 0),
                        tags=sqs_properties.get("Tags", {}),
                        visibility_timeout=sqs_properties.get("VisibilityTimeout", 30),
                        lambda_runner=self._lambda_runner,
                        event_map_list=[
                            SqsEventMap(
                                function_name=function_name,
                                batch_size=sqs_event_properties.get("BatchSize", 10),
                            )
                        ],
                        stderr=self._stderr,
                    )

        return sqs_resource_map

    @staticmethod
    def _get_resource_type_map(stacks: List[Stack]) -> Dict[str, Dict]:
        # Normalize declared stack resources by type for later processing.
        resource_type_map: Dict[str, Dict] = {}

        for stack in stacks:
            for resource_name, resource_attrs in stack.resources.items():
                resource_type = resource_attrs["Type"]

                if resource_type in resource_type_map:
                    resource_type_map[resource_type][resource_name] = resource_attrs
                else:
                    resource_type_map[resource_type] = {resource_name: resource_attrs}

        return resource_type_map


def run_async(call_list: List[Callable], concurrency: int = 4):
    loop = asyncio.get_event_loop()

    async def call(func: Callable, semaphore):
        async with semaphore:
            return await loop.run_in_executor(None, func)

    async def begin():
        semaphore = asyncio.Semaphore(concurrency)
        return await asyncio.gather(*[call(func, semaphore) for func in call_list])

    return loop.run_until_complete(begin())
