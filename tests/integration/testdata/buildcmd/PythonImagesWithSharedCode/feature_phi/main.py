from shared_code import numbers


def handler(event, context):
    return {"phi": numbers.get_phi_2dp()}
