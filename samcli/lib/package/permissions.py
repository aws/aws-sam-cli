"""
Classes which will change permissions on a ZipInfo object
"""
import platform
import zipfile


class FilePermissionMapper:
    def __init__(self, permissions: int):
        self.permissions = permissions

    def apply(self, zip_info: zipfile.ZipInfo):
        if platform.system().lower() != "windows":
            return zip_info
        zip_info.external_attr = self.permissions << 16 if not zip_info.is_dir() else zip_info.external_attr
        return zip_info


class DirPermissionMapper:
    def __init__(self, permissions: int):
        self.permissions = permissions

    def apply(self, zip_info: zipfile.ZipInfo):
        if platform.system().lower() != "windows":
            return zip_info
        zip_info.external_attr = self.permissions << 16 if zip_info.is_dir() else zip_info.external_attr
        return zip_info


class AdditiveDirPermissionMapper:
    def __init__(self, permissions: int):
        self.permissions = permissions

    def apply(self, zip_info: zipfile.ZipInfo):
        if zip_info.is_dir():
            zip_info.external_attr |= self.permissions << 16
        return zip_info


class AdditiveFilePermissionMapper:
    def __init__(self, permissions: int):
        self.permissions = permissions

    def apply(self, zip_info: zipfile.ZipInfo):
        if not zip_info.is_dir():
            zip_info.external_attr |= self.permissions << 16
        return zip_info
