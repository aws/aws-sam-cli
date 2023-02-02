"""
Classes which will change permissions on a ZipInfo object
"""
import platform
import zipfile


class WindowsFilePermissionMapper:
    """
    Windows specific Permission Mapper onto a zipfile.ZipInfo object to
    set explicit permissions onto `external_attr` attribute if the given object
    is of type `file`
    """

    def __init__(self, permissions: int):
        """

        Parameters
        ----------
        permissions: int
            Base permissions.
        """
        self.permissions = permissions

    def apply(self, zip_info: zipfile.ZipInfo):
        """

        Parameters
        ----------
        zip_info: zipfile.ZipInfo
            object of zipfile.ZipInfo

        Returns
        -------
        zipfile.ZipInfo
            modified object with `external_attr` set to member permissions.

        """
        if platform.system().lower() != "windows":
            return zip_info
        zip_info.external_attr = self.permissions << 16 if not zip_info.is_dir() else zip_info.external_attr
        return zip_info


class WindowsDirPermissionMapper:
    """
    Windows specific Permission Mapper onto a zipfile.ZipInfo object to
    set explicit permissions onto `external_attr` attribute if the given object
    is of type `directory`
    """

    def __init__(self, permissions: int):
        """

        Parameters
        ----------
        permissions: int
            Base permissions.
        """
        self.permissions = permissions

    def apply(self, zip_info: zipfile.ZipInfo):
        """

        Parameters
        ----------
        zip_info: zipfile.ZipInfo
            object of zipfile.ZipInfo

        Returns
        -------
        zipfile.ZipInfo
            modified object with `external_attr` set to member permissions.

        """
        if platform.system().lower() != "windows":
            return zip_info
        zip_info.external_attr = self.permissions << 16 if zip_info.is_dir() else zip_info.external_attr
        return zip_info


class AdditiveDirPermissionMapper:
    """
    Additive Permission Mapper onto a zipfile.ZipInfo object to
    set additive permissions onto `external_attr` attribute if the given object
    is of type `directory`
    """

    def __init__(self, permissions: int):
        """

        Parameters
        ----------
        permissions: int
            Base permissions.
        """
        self.permissions = permissions

    def apply(self, zip_info: zipfile.ZipInfo):
        """

        Parameters
        ----------
        zip_info: zipfile.ZipInfo
            object of zipfile.ZipInfo

        Returns
        -------
        zipfile.ZipInfo
            modified object with `external_attr` added with member permissions
            if conditions are satisfied.

        """
        if zip_info.is_dir():
            zip_info.external_attr |= self.permissions << 16
        return zip_info


class AdditiveFilePermissionMapper:
    """
    Additive Permission Mapper onto a zipfile.ZipInfo object to
    set additive permissions onto `external_attr` attribute if the given object
    is of type `file`
    """

    def __init__(self, permissions: int):
        """

        Parameters
        ----------
        permissions: int
            Base permissions.
        """
        self.permissions = permissions

    def apply(self, zip_info: zipfile.ZipInfo):
        """

        Parameters
        ----------
        zip_info: zipfile.ZipInfo
            object of zipfile.ZipInfo

        Returns
        -------
        zipfile.ZipInfo
            modified object with `external_attr` added with member permissions
            if conditions are satisfied.

        """
        if not zip_info.is_dir():
            zip_info.external_attr |= self.permissions << 16
        return zip_info
