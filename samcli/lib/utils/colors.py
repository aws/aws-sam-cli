
import click


class Colored(object):

    def __init__(self, colorize=True):
        self.colorize = colorize

    def red(self, msg):
        self._color(msg, 'red')

    def green(self, msg):
        self._color(msg, 'green')

    def blue(self, msg):
        self._color(msg, 'blue')

    def white(self, msg):
        self._color(msg, 'white')

    def _color(self, msg, color):
        click.style(msg, fg=color) if self.colorize else msg
