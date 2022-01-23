"""
ECR Packaging Utils
"""
import re

from samcli.lib.package.regexpr import ECR_URL


def is_ecr_url(url: str) -> bool:
    return bool(re.match(ECR_URL, url)) if url else False
