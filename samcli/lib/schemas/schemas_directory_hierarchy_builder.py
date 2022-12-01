""" Responsible for building schema code directory hierarchy based on schema name """

import re


# To sanitize schema package name and root name. During code generation schema service follows
# convention to replace all the special character except [a-zA-Z0-9_@] via _.
CHARACTER_TO_SANITIZE = "[^a-zA-Z0-9_@]"
POTENTIAL_PACKAGE_SEPARATOR = "[@]"


def get_package_hierarchy(schema_name):  # type: ignore[no-untyped-def]
    path = "schema"
    if schema_name.startswith("aws.partner-"):
        path = path + "." "aws.partner"
        tail = schema_name[len("aws.partner-") :]
        path = path + "." + sanitize_name(tail)  # type: ignore[no-untyped-call]
        return path.lower()
    if schema_name.startswith("aws."):
        parts = schema_name.split(".")
        for part in parts:
            path = path + "."
            path = path + sanitize_name(part)  # type: ignore[no-untyped-call]
        return path.lower()
    return f"{path}.{sanitize_name(schema_name)}".lower()  # type: ignore[no-untyped-call]


def sanitize_name(name):  # type: ignore[no-untyped-def]
    name = re.sub(CHARACTER_TO_SANITIZE, "_", name)
    return re.sub(POTENTIAL_PACKAGE_SEPARATOR, ".", name)
