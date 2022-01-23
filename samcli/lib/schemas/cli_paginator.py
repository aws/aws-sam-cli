"""
Construct one CLI page based on the input provided and returns customer choice
"""

import click


def do_paginate_cli(pages, page_to_be_rendered, items_per_page, is_last_page, cli_display_message):
    """
    Responsible for displaying a generic CLI page with available user choices for pagination/seletion
    :param pages:
    :param page_to_be_rendered:
    :param items_per_page:
    :param is_last_page:
    :param cli_display_message:
    :return: User decision on displayed page
    """
    options = pages.get(page_to_be_rendered)
    choice_num = page_to_be_rendered * items_per_page + 1
    choices = []

    # Track possible user choices (which are unique across all pages)
    for option in options:
        msg = str(choice_num) + " - " + option
        click.echo("\t" + msg)
        choices.append(choice_num)
        choice_num = choice_num + 1

    # Single page is available no pagination
    if len(pages) == 1 and is_last_page:
        message = str.format(cli_display_message["single_page"])
    elif not page_to_be_rendered:
        # (multi) First page
        choices = choices + ["N", "n"]
        message = cli_display_message["first_page"]
    elif is_last_page and page_to_be_rendered == len(pages) - 1:
        # (multi) Last page
        choices = choices + ["P", "p"]
        message = cli_display_message["last_page"]
    else:
        # (multi) Middle page
        choices = choices + ["N", "n", "P", "p"]
        message = cli_display_message["middle_page"]

    final_choices = list(map(str, choices))
    choice = click.prompt(message, type=click.Choice(final_choices), show_choices=False)

    # Return page to be rendered based on the user selection
    if choice in ("N", "n"):
        return {"choice": None, "page_to_render": page_to_be_rendered + 1}
    if choice in ("P", "p"):
        return {"choice": None, "page_to_render": page_to_be_rendered - 1}

    # Recalculate page index based on the global choice ID, and the number of items per page
    # e.g. If user picks choice '11', and we know there are 10 items per page,
    # then we know the user is on page 2
    index = int(choice) % items_per_page
    if index:
        index = index - 1
    else:
        index = items_per_page - 1
    return {"choice": options[index], "page_to_render": None}
