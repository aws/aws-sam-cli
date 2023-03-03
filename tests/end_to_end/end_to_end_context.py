from pathlib import Path

from tempfile import TemporaryDirectory


class EndToEndTestContext:
    def __init__(self, app_name):
        super().__init__()
        self.temporary_directory = TemporaryDirectory()
        self.app_name = app_name
        self.working_directory = ""
        self.project_directory = ""
        self.template_path = ""

    def __enter__(self):
        temporary_directory = self.temporary_directory.__enter__()
        self.working_directory = temporary_directory
        self.project_directory = str(Path(temporary_directory) / self.app_name)
        self.template_path = str(Path(self.project_directory) / "template.yaml")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.temporary_directory.__exit__(exc_type, exc_val, exc_tb)
