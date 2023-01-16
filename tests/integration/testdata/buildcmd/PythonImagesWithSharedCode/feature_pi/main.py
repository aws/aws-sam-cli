from shared_code import numbers


def handler(event, context):
    return {"pi": numbers.get_pi_2dp()}
