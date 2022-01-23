""" Responsible for building schema code directory hierarchy based on schema name """

import re


# To sanitize schema package name and root name. During code generation schema service follows
# convention to replace all the special character except [a-zA-Z0-9_@] via _.
CHARACTER_TO_SANITIZE = "[^a-zA-Z0-9_@]"
POTENTIAL_PACKAGE_SEPARATOR = "[@]"


def get_package_hierarchy(schema_name):
    path = "schema"
    if schema_name.startswith("aws.partner-"):
        path = path + "." "aws.partner"
        tail = schema_name[len("aws.partner-") :]
        path = path + "." + sanitize_name(tail)
        return path.lower()
    if schema_name.startswith("aws."):
        parts = schema_name.split(".")
        for part in parts:
            path = path + "."
            path = path + sanitize_name(part)
        return path.lower()
    return f"{path}.{sanitize_name(schema_name)}".lower()


def sanitize_name(name):
    name = re.sub(CHARACTER_TO_SANITIZE, "_", name)
    return re.sub(POTENTIAL_PACKAGE_SEPARATOR, ".", name)
