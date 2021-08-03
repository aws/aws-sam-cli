from samcli.commands.check.resources.template_resource import TemplateResource


class ApiGateway(TemplateResource):
    def __init__(self, resource_object, resource_type, resource_name):
        super().__init__(resource_object, resource_type, resource_name)
        self.tps = None
        self.parents = []
        self.children = []

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