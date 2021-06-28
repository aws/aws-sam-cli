from unittest import TestCase

from samcli.lib.delete.utils import get_cf_template_name

class TestCfUtils(TestCase):

    def test_utils(self):
        self.assertEqual(get_cf_template_name("hello world!", "template"), "fc3ff98e8c6a0d3087d515c0473f8677.template")