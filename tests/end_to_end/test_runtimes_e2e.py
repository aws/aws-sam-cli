from parameterized import parameterized_class

from tests.end_to_end.end_to_end_base import EndToEndBase


@parameterized_class(
    ("runtime", "dependency_manager"),
    [
        ("go1.x", "mod"),
        ("python3.9", "pip"),
    ],
)
class TestHelloWorldDefaultEndToEnd(EndToEndBase):
    app_template = "hello-world"

    def test_go_hello_world_default_workflow(self):
        self.default_workflow()


@parameterized_class(
    ("runtime", "dependency_manager"),
    [
        ("go1.x", "mod"),
        ("python3.9", "pip"),
    ],
)
class TestHelloWorldDefaultSyncEndToEnd(EndToEndBase):
    app_template = "hello-world"

    def test_go_hello_world_default_workflow(self):
        self.default_sync_workflow()
