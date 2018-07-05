
import click


class Colored(object):

    def __init__(self, colorize=True):
        self.colorize = colorize

    def red(self, msg):
        return self._color(msg, 'red')

    def green(self, msg):
        return self._color(msg, 'green')

    def cyan(self, msg):
        return self._color(msg, 'cyan')

    def white(self, msg):
        return self._color(msg, 'white')

    def yellow(self, msg):
        return self._color(msg, 'yellow')

    def bold(self, msg):
        return click.style(msg, underline=True) if self.colorize else msg

    def _color(self, msg, color, bg=False):
        kwargs = {}

        if bg:
            # Set the background color
            kwargs['bg'] = color
        else:
            # Set text color
            kwargs['fg'] = color

        return click.style(msg, **kwargs) if self.colorize else msg
