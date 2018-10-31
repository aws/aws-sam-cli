"""Request mapping and helper functions"""

from airspeed import Template


class VelocityTemplateRenderer(object):
    @staticmethod
    def render(template, event):
        return Template(template).merge(event.to_model())
