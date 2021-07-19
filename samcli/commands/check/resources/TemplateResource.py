from types import resolve_bases


class TemplateResource:
    def __init__(self, resource_object, resource_type, resource_name):
        self.resource_object = resource_object
        self.resource_type = resource_type
        self.resource_name = resource_name

    def get_resource_object(self):
        return self.resource_object

    def get_name(self):
        return self.resource_name

    def get_resource_type(self):
        return self.resource_type