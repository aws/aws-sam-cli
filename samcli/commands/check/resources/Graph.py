from logging import warn


class Graph:
    def __init__(self):
        self.entry_points = []
        self.resources_to_analyze = []
        self.green_warnings = []
        self.yellow_warnings = []
        self.red_warnings = []
        self.red_burst_warnings = []
        self.lambda_function_pricing_info = None

    def add_entry_point(self, node):
        self.entry_points.append(node)

    def get_entry_points(self):
        return self.entry_points

    def get_resources_to_analyze(self):
        return self.resources_to_analyze

    def add_resource_to_analyze(self, resource):
        self.resources_to_analyze.append(resource)

    def add_green_warning(self, warning):
        self.green_warnings.append(warning)

    def get_green_warnings(self):
        return self.green_warnings

    def add_yellow_warning(self, warning):
        self.yellow_warnings.append(warning)

    def get_yellow_warnings(self):
        return self.yellow_warnings

    def add_red_warning(self, warning):
        self.red_warnings.append(warning)

    def get_red_warnings(self):
        return self.red_warnings

    def add_red_burst_warning(self, warning):
        self.red_burst_warnings.append(warning)

    def get_red_burst_warnings(self):
        return self.red_burst_warnings

    def get_lambda_function_pricing_info(self):
        return self.lambda_function_pricing_info

    def set_lambda_function_pricing_info(self, info):
        self.lambda_function_pricing_info = info
