
from samcli.lib.build.workflows import CONFIG as WorkflowConfig

class RuntimeBase:
    name: str
    build_workflow: WorkflowConfig
    layer_subfolder: str
    # workflow_selector: ???
    
