# Generate an S3 notification delivered through SQS

## Problem

[Issue #7252](https://github.com/aws/aws-sam-cli/issues/7252) asks for sample
events representing common service chains. A Lambda function consuming an S3
notification through SQS receives an SQS event whose message body is a JSON
string containing the S3 notification. Generating either service's event alone
does not produce this payload.

## Proposed change and user experience

Add one sample event to the existing `generate-event` command:

```sh
sam local generate-event sqs receive-message-from-s3
sam local generate-event sqs receive-message-from-s3 \
  --bucket example-uploads --key incoming/example.json --queue-name object-events
sam local generate-event sqs receive-message-from-s3 | sam local invoke -e -
```

The command accepts `--bucket`, `--key`, `--queue-name`, `--account-id`,
`--region`, and `--partition`. Region and partition apply to both services.
The inner notification represents `ObjectCreated:Put`. The message body is
generated from the existing S3 Put sample, and `md5OfBody` matches its exact
UTF-8 contents.

## Implementation

The new event mapping reuses the existing `Sqs.json` envelope and references
`s3` / `put` through optional `body-event` metadata. Once the envelope is
rendered, the event generator renders the referenced source with a copy of
the supplied values, assigns the resulting JSON string to each SQS record's
`body`, and calculates `md5OfBody`. Final JSON serialization escapes the body.
Only the source generator encodes the object key, preventing double encoding.

The CLI discovers the new sample and its options from the mapping. Existing
sample events retain their rendering path. No new configuration format,
dependencies, containers, network calls, temporary files, or AWS credentials
are required. Existing `samconfig.toml` parameter handling also applies to
the new sample.

Arbitrary service chains, other S3 event types, SNS envelopes, FIFO queues,
and changes to existing S3 key encoding are outside this contribution.

## Testing and success criteria

- Unit tests parse both JSON layers, verify the event sources and S3 operation,
  and check queue and bucket ARNs, shared region and partition, checksum, and
  object keys containing quotes, plus signs, and Unicode.
- CLI integration tests exercise default and customized options through the
  executable without AWS access or a container runtime.
- Help output includes an example of the new command.
- Existing event generators produce unchanged payloads for the same inputs.
- Run the repository's schema, formatting, lint, type, and unit checks, plus
  the event-generator integration tests.

## Documentation and review

The generated `sqs --help` listing describes the new event. The root
`generate-event --help` includes a usage example. This design and prototype
are submitted together for review of the command name and initial scope.
