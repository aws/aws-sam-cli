from unittest import TestCase
from unittest.mock import Mock, patch
from samcli.commands.check.pricing_calculations import PricingCalculations


class TestPricingCalculations(TestCase):
    def test_get_lambda_pricing_results(self):
        self_mock = Mock()
        self_mock.lambda_pricing_results = Mock()

        result = PricingCalculations.get_lambda_pricing_results(self_mock)

        self.assertEqual(result, self_mock.lambda_pricing_results)

    def test_run_calculations(self):
        self_mock = Mock()
        self_mock.get_charge_and_request_amounts = Mock()
        self_mock.determine_lambda_cost = Mock()

        PricingCalculations.run_calculations(self_mock)

        self_mock.get_charge_and_request_amounts.assert_called_once()
        self_mock.determine_lambda_cost.assert_called_once()

    def test_get_charge_and_request_amounts(self):
        self_mock = Mock()
        self_mock.get_lambda_charge_and_request_amounts = Mock()

        PricingCalculations.get_charge_and_request_amounts(self_mock)

        self_mock.get_lambda_charge_and_request_amounts.assert_called_once()

    @patch("samcli.commands.check.pricing_calculations.ast")
    @patch("samcli.commands.check.pricing_calculations.urllib")
    def test_get_aws_lambda_pricing_info(self, patch_request, patch_ast):

        file_return_mock = Mock()
        file_return_mock.read.decode = Mock()

        patch_ast.literal_eval.return_value = Mock()

        result = PricingCalculations.get_aws_lambda_pricing_info(Mock())

        self.assertEqual(result, patch_ast.literal_eval.return_value)

    def test_determine_lambda_cost(self):
        self_mock = Mock()
        self_mock.monthly_compute_charge = 0.00001
        self_mock.monthly_request_charge = 0.00002
        self_mock.max_num_of_free_requests = 1000000
        self_mock.max_free_GBs = 400000

        template_lambda_pricing_info_mock = Mock()
        template_lambda_pricing_info_mock.allocated_memory = 4.1
        template_lambda_pricing_info_mock.allocated_memory_unit = "GB"
        template_lambda_pricing_info_mock.number_of_requests = 4000000
        template_lambda_pricing_info_mock.average_duration = 1984

        self_mock.graph.lambda_function_pricing_info = template_lambda_pricing_info_mock

        PricingCalculations.determine_lambda_cost(self_mock)

        self.assertEqual(381.38, self_mock.lambda_pricing_results)

    @patch("samcli.commands.check.pricing_calculations.get_session")
    def test_get_lambda_charge_and_request_amounts(self, patch_session):
        self_mock = Mock()
        self_mock.get_region_prefix = Mock()
        self_mock.get_pricing_or_request_value = Mock()
        self_mock.region_prefix = "@#$"

        product_1 = {"attributes": {"usagetype": "Global-Request"}}
        product_2 = {"attributes": {"usagetype": "Global-Lambda-GB-Second"}}
        product_3 = {"attributes": {"usagetype": "Lambda-GB-Second"}}
        product_4 = {"attributes": {"usagetype": "Request"}}

        terms_mock = Mock()
        products = {"1": product_1, "2": product_2, "3": product_3, "4": product_4}

        patch_session.get_config_variable.return_value = ""

        self_mock.get_aws_lambda_pricing_info = Mock()
        self_mock.get_aws_lambda_pricing_info.return_value = {"products": products, "terms": terms_mock}

        PricingCalculations.get_lambda_charge_and_request_amounts(self_mock)

        self_mock.get_pricing_or_request_value.assert_any_call(product_1, terms_mock, "global-request")
        self_mock.get_pricing_or_request_value.assert_any_call(product_2, terms_mock, "global-lambda")
        self_mock.get_pricing_or_request_value.assert_any_call(product_3, terms_mock, "lambda")
        self_mock.get_pricing_or_request_value.assert_any_call(product_4, terms_mock, "request")

    def test_get_pricing_or_request_value(self):
        self_mock = Mock()
        sku = ""

        price_dimentions_values = {"endRange": 8.15, "pricePerUnit": {"USD": 115}}
        price_dimentions = {"": price_dimentions_values}
        temp_key_values = {"priceDimensions": price_dimentions}
        temp_key = {"": temp_key_values}

        product = {"sku": sku}
        terms = {"OnDemand": {sku: temp_key}}

        # testing global-request
        PricingCalculations.get_pricing_or_request_value(self_mock, product, terms, "global-request")
        self.assertEqual(8.15, self_mock.max_num_of_free_requests)

        # testing global-lambda
        PricingCalculations.get_pricing_or_request_value(self_mock, product, terms, "global-lambda")
        self.assertEqual(8.15, self_mock.max_free_GBs)

        # testing lambda
        PricingCalculations.get_pricing_or_request_value(self_mock, product, terms, "lambda")
        self.assertEqual(115, self_mock.monthly_compute_charge)

        # testing request
        PricingCalculations.get_pricing_or_request_value(self_mock, product, terms, "request")
        self.assertEqual(115, self_mock.monthly_request_charge)

    def test_get_region_prefix(self):
        # TODO
        pass
