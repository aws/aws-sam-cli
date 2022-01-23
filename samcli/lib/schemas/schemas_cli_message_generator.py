"""
Contains message used by Schemas paginated CLI.
"""


def construct_cli_display_message_for_schemas(page_to_render, last_page_number=None):
    if last_page_number is None:
        last_page_number = "many"
    single_page = "Event Schemas"
    first_page = "Event Schemas [Page %s/%s] (Enter N for next page)" % (page_to_render, last_page_number)
    middle_page = "Event Schemas [Page %s/%s] (Enter N/P for next/previous page)" % (page_to_render, last_page_number)
    last_page = "Event Schemas [Page %s/%s] (Enter P for previous page)" % (page_to_render, last_page_number)
    return {"single_page": single_page, "first_page": first_page, "middle_page": middle_page, "last_page": last_page}


def construct_cli_display_message_for_registries(page_to_render, last_page_number=None):
    if last_page_number is None:
        last_page_number = "many"
    single_page = "Schema Registry"
    first_page = "Schema Registry [Page %s/%s] (Enter N for next page)" % (page_to_render, last_page_number)
    middle_page = "Schema Registry [Page %s/%s] (Enter N/P for next/previous page)" % (page_to_render, last_page_number)
    last_page = "Schema Registry [Page %s/%s] (Enter P for previous page)" % (page_to_render, last_page_number)
    return {"single_page": single_page, "first_page": first_page, "middle_page": middle_page, "last_page": last_page}
