def convert_table_string_to_regex(entry: str) -> str:
    """
    Converts the first line of a table entry to a regex string

    Parameters
    ----------
    entry: str
        The first line of the table entry. May need to remove some sections that would vary too much with line wrapping
        For example: https://123physicalID.execute-api.us- can become https://#.# when inputted to prevent errors
        due to the way the table handles minimum width and line wrapping

    Returns
    -------
    expression: str
        The regex string that will match to the table entry
    """

    expression = ""

    # Generate the string to match the first line of the table entry.
    for character in entry:
        if character == " ":
            expression += f"( |\\n)*"

        # Currently, a '#' is used to mark areas where we just want to match anything
        # Ex. arn:aws:iam::9876543210:role..., replace the account number with # -> arn:aws:iam::#:role since
        # these are constantly changing every time the integration tests are run
        elif character == "#":
            expression += f".*"
        else:
            expression += f"{character}\\n*"
    return expression


def convert_table_name_and_header_to_regex(table_name: str, header: str) -> str:
    """
    Converts the table name and header to a regex string that can be matched regardless of the table layout
    based on terminal size

    Parameters
    ----------
    table_name: str
        Name of the table (ex. Stack Outputs)
    header: str
        Header of the table. Ex. for Stack Outputs, it would be: 'OutputKey OutputValue Description '. A space is
        needed at the end to match trailing spaces found at the end of the header in the table

    Returns
    -------
    expression: str
        The regex string that will match to the table name and header of the table
    """
    expression = ""
    count = 1

    # Generate the string to match the table name
    for character in table_name:
        # Add \n* after each character to match the string regardless of where the line wraps
        if character == " ":
            expression += f"( )\\n*"

        # Match a single newline at the end of the table title
        elif count == len(table_name):
            expression += f"{character}\\n"
        else:
            expression += f"{character}\\n*"
        count += 1

    # Match the dashes around the table header
    expression += "-+(-|\\n)+"
    expression += convert_table_string_to_regex(header)
    expression += "-+(-|\\n)+"
    return expression
