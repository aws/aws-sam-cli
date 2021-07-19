from .TemplateResource import TemplateResource


class LambdaFunction(TemplateResource):
    def __init__(self, resource_object, resource_type, resource_name):
        super().__init__(resource_object, resource_type, resource_name)
        self.duration = None
        self.tps = None
        self.parents = []
        self.children = []
        self.permission = None

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
