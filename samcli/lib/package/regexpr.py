"""
Regular Expressions for Resources.
"""
# Regex derived from https://docs.aws.amazon.com/AmazonECR/latest/APIReference/API_Repository.html
ECR_URL = (
    r"(^[a-zA-Z0-9][a-zA-Z0-9-_]*)\.dkr\.ecr\.([a-zA-Z0-9][a-zA-Z0-9-_]*)\.amazonaws\.com(\.cn)?"
    r"\/(?:[a-z0-9]+(?:[._-][a-z0-9]+)*\/)*[a-z0-9]+(?:[._-][a-z0-9]+)*"
)
