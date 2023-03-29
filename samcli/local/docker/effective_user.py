"""
Representation of an effective user
"""
import os
from dataclasses import dataclass
from typing import Optional

# constant for root user id
ROOT_USER_ID = "0"


@dataclass(frozen=True)
class EffectiveUser:
    user_id: Optional[str]
    group_id: Optional[str]

    def to_effective_user_str(self) -> Optional[str]:
        """
        Return String representation of the posix effective user, or None for non posix systems
        """
        if not self.user_id:
            # Return None for non-posix systems
            return None

        if self.user_id == ROOT_USER_ID or not self.group_id:
            # Return only user id if root or no group id
            return str(self.user_id)

        return f"{self.user_id}:{self.group_id}"

    @staticmethod
    def get_current_effective_user():
        """
        Get the posix effective user and group id for current user
        """
        if os.name.lower() == "posix":
            user_id = os.getuid()
            group_ids = os.getgroups()
            return EffectiveUser(str(user_id), str(group_ids[0]) if len(group_ids) > 0 else None)

        return EffectiveUser(None, None)
