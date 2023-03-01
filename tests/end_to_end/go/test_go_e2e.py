from tests.end_to_end.end_to_end_base import EndToEndBase


class TestGoEndToEnd(EndToEndBase):
    runtime = "go1.x"
    dependency_manager = "mod"
    app_template = "hello-world"

    def test_go_hello_world_default_workflow(self):
        self.default_workflow()
