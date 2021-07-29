from .TemplateResource import TemplateResource


class LambdaFunction(TemplateResource):
    def __init__(self, resource_object, resource_type, resource_name):
        super().__init__(resource_object, resource_type, resource_name)
        self.duration = None
        self.tps = None
        self.parents = []
        self.children = []
        self.permission = None
        self.entry_point_resource = None

    def copy_data(self):
        old_resource_object = self.get_resource_object()
        old_resource_type = self.get_resource_type()
        old_resource_name = self.get_name()
        old_duration = self.get_duration()
        old_tps = self.get_tps()
        old_parents = self.get_parents()
        old_children = self.get_children()
        old_permission = self.get_permission()
        old_entry_point_resource = self.entry_point_resource

        new_lambda_function = LambdaFunction(old_resource_object, old_resource_type, old_resource_name)

        new_lambda_function.duration = int(old_duration)
        new_lambda_function.tps = old_tps
        new_lambda_function.parents = old_parents
        new_lambda_function.children = old_children
        new_lambda_function.permission = old_permission
        new_lambda_function.entry_point_resource = old_entry_point_resource

        return new_lambda_function

    def add_child(self, child_node):
        self.children.append(child_node)

    def get_children(self):
        return self.children

    def add_parent(self, parent_node):
        self.parents.append(parent_node)

    def get_parents(self):
        return self.parents

    def set_tps(self, tps):
        self.tps = tps

    def get_tps(self):
        return self.tps

    def set_duration(self, duration):
        self.duration = duration

    def get_duration(self):
        return self.duration

    def get_permission(self):
        return self.permission

    def set_permission(self, permission):
        self.permission = permission
