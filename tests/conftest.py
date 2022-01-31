import os

from typing import List

from pytest import Session, Item
from _pytest.config import Config


if "__SAM_CLI_TELEMETRY_ENDPOINT_URL" not in os.environ:
    os.environ["__SAM_CLI_TELEMETRY_ENDPOINT_URL"] = ""

WORKER_COUNT = int(os.environ.get("WORKER_COUNT", "1"))
WORKER_ID = int(os.environ.get("WORKER_ID", "0"))


def pytest_collection_modifyitems(session: Session, config: Config, items: List[Item]) -> None:
    selected_items = list()
    for i in range(len(items)):
        if i % WORKER_COUNT == WORKER_ID:
            selected_items.append(items[i])

    for item in items.copy():
        if item not in selected_items:
            items.remove(item)
