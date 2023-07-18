import os
import logging

LOG = logging.getLogger(__name__)

def default_handler(event, context):
    print("value1 = " + event["key1"])
    print("value2 = " + event["key2"])
    print("value3 = " + event["key3"])

    return {
        "message": f'{event["key1"]} {event["key3"]}'
    }

def custom_env_var_echo_handler(event, context):
    return os.environ.get("CustomEnvVar")

def echo_client_context_data(event, context):
    custom_dict = context.client_context.custom
    return custom_dict

def write_to_stderr(event, context):
    LOG.error("Lambda Function is writing to stderr")

    return "wrote to stderr"

def echo_event(event, context):
    return event

def raise_exception(event, context):
    raise Exception("Lambda is raising an exception")

def stock_transaction_recommender(event, context):
    stock_price = int(event["stock_price"])
    balance = event["balance"]
    qty = event["qty"]
    if qty*stock_price < 100:
        stock_action = "Buy"
    else:
        stock_action = "Sell"
    return {"stock_price": stock_price, "action": stock_action, "balance": balance, "qty": qty}

def stock_buyer(event, context):
    current_balance = event["balance"]
    new_balance = current_balance - (event["qty"]*event["stock_price"])
    return {
        "balance": new_balance
    }

def stock_seller(event, context):
    current_balance = event["balance"]
    new_balance = current_balance + (event["qty"]*event["stock_price"])
    return {
        "balance": new_balance
    }