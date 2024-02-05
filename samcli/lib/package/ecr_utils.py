"""
ECR Packaging Utils
"""

import re

"""
Regular Expressions for Resources.
"""
# Regex derived from https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_Repository.html
HOSTNAME_ECR_AWS = r"(?:[a-zA-Z0-9][\w-]*)\.dkr\.ecr\.(?:[a-zA-Z0-9][\w-]*)\.amazonaws\.com(\.cn)?"
HOSTNAME_LOCALHOST = r"localhost(?::\d{1,5})?"
HOSTNAME_127_0_0_1 = r"127\.0\.0\.1(?::\d{1,5})?"
ECR_URL = (
    rf"^(?:{HOSTNAME_ECR_AWS}|{HOSTNAME_LOCALHOST}|{HOSTNAME_127_0_0_1})\/"
    r"(?:[a-z0-9]+(?:[._-][a-z0-9]+)*\/)*[a-z0-9]+(?:[._-][a-z0-9]+)*"
)


def is_ecr_url(url: str) -> bool:
    return bool(re.match(ECR_URL, url)) if url else False
