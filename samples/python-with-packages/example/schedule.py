import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

def lambda_sandbox_down_handler(event: dict, context):
    log.info('running DOWN handler with event: %s and context: %s', event, context)

