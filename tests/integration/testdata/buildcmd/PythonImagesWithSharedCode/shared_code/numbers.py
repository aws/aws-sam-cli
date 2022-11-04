import numpy


def _format_2dp(number):
    return "{0:.2f}".format(number)


def get_pi_2dp():
    return _format_2dp(numpy.pi)


def get_phi_2dp():
    # Golden ratio
    return _format_2dp((1 + 5 ** 0.5) / 2)
