"""
Utilities for Deploy
"""

from samcli.lib.utils.colors import Colored


class DeployColor:
    def __init__(self):
        self._color = Colored()
        self.changeset_color_map = {"Add": "green", "Modify": "yellow", "Remove": "red"}
        self.status_color_map = {
            "CREATE_COMPLETE": "green",
            "CREATE_FAILED": "red",
            "CREATE_IN_PROGRESS": "yellow",
            "DELETE_COMPLETE": "green",
            "DELETE_FAILED": "red",
            "DELETE_IN_PROGRESS": "red",
            "REVIEW_IN_PROGRESS": "yellow",
            "ROLLBACK_COMPLETE": "red",
            "ROLLBACK_IN_PROGRESS": "red",
            "UPDATE_COMPLETE": "green",
            "UPDATE_COMPLETE_CLEANUP_IN_PROGRESS": "yellow",
            "UPDATE_IN_PROGRESS": "yellow",
            "UPDATE_ROLLBACK_COMPLETE_CLEANUP_IN_PROGRESS": "red",
            "UPDATE_ROLLBACK_FAILED": "red",
            "UPDATE_ROLLBACK_IN_PROGRESS": "red",
        }

    def get_stack_events_status_color(self, status):
        return self.status_color_map.get(status, "yellow")

    def get_changeset_action_color(self, action):
        return self.changeset_color_map.get(action, "yellow")
