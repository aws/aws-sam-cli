"""
Lambda Builders-speicific utils
"""


def patch_runtime(runtime: str) -> str:
    # NOTE: provided runtimes (provided, provided.al2, etc) are all recognized as "provided" in Lambda Builders
    if runtime.startswith("provided"):
        runtime = "provided"
    return runtime.replace(".al2", "")
