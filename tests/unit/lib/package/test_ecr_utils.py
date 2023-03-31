from unittest import TestCase

from samcli.lib.package.ecr_utils import is_ecr_url


class TestECRUtils(TestCase):
    def test_valid_ecr_url(self):
        url = "000000000000.dkr.ecr.eu-west-1.amazonaws.com/my-repo"
        self.assertTrue(is_ecr_url(url))

    def test_valid_long_ecr_url(self):
        url = "000000000000.dkr.ecr.eu-west-1.amazonaws.com/a/longer/path/my-repo"
        self.assertTrue(is_ecr_url(url))

    def test_valid_long_ecr_url_special_chars(self):
        url = "000000000000.dkr.ecr.eu-west-1.amazonaws.com/a/weird.er/pa_th/my-repo"
        self.assertTrue(is_ecr_url(url))

    def test_valid_localhost_ecr_url(self):
        url = "localhost/my-repo"
        self.assertTrue(is_ecr_url(url))

    def test_valid_localhost_ecr_url_port(self):
        url = "localhost:8084/my-repo"
        self.assertTrue(is_ecr_url(url))

    def test_valid_127_0_0_1_ecr_url(self):
        url = "127.0.0.1/my-repo"
        self.assertTrue(is_ecr_url(url))

    def test_valid_127_0_0_1_ecr_url_port(self):
        url = "127.0.0.1:12345/my-repo"
        self.assertTrue(is_ecr_url(url))

    def test_ecr_url_only_hostname(self):
        url = "000000000000.dkr.ecr.eu-west-1.amazonaws.com"
        self.assertFalse(is_ecr_url(url))

    def test_ecr_url_only_hostname2(self):
        url = "000000000000.dkr.ecr.eu-west-1.amazonaws.com/"  # with slash
        self.assertFalse(is_ecr_url(url))

    def test_ecr_url_non_alphanum_starting_char(self):
        url = "_00000000000.dkr.ecr.eu-west-1.amazonaws.com/my-repo"
        self.assertFalse(is_ecr_url(url))

    def test_localhost_ecr_url_only_hostname(self):
        url = "localhost"
        self.assertFalse(is_ecr_url(url))

    def test_localhost_ecr_url_long_port_name(self):
        url = "localhost:123456/my-repo"
        self.assertFalse(is_ecr_url(url))

    def test_localhost_ecr_url_bad_port_name(self):
        url = "localhost:abc/my-repo"
        self.assertFalse(is_ecr_url(url))

    def test_localhost_ecr_url_malform(self):
        url = "localhost:/my-repo"
        self.assertFalse(is_ecr_url(url))

    def test_127_0_0_1_ecr_url_only_hostname(self):
        url = "127.0.0.1"
        self.assertFalse(is_ecr_url(url))

    def test_127_0_0_1_ecr_url_long_port_name(self):
        url = "127.0.0.1:123456/my-repo"
        self.assertFalse(is_ecr_url(url))

    def test_127_0_0_1_ecr_url_bad_port_name(self):
        url = "127.0.0.1:abc/my-repo"
        self.assertFalse(is_ecr_url(url))

    def test_127_0_0_1_ecr_url_malform(self):
        url = "127.0.0.1:/my-repo"
        self.assertFalse(is_ecr_url(url))

    def test_localhost_ecr_url_wronghostname(self):
        url = "notlocalhost:1234/my-repo"
        self.assertFalse(is_ecr_url(url))

    def test_127_0_0_1_ecr_url_wronghostname(self):
        url = "127.0.0.2:1234/my-repo"
        self.assertFalse(is_ecr_url(url))
