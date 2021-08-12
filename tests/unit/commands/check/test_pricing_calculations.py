from unittest import TestCase
from unittest.mock import Mock, patch
from samcli.commands.check.lambda_function_pricing_calculations import (
    LambdaFunctionPricingCalculations,
    _convert_usage_type,
)


class TestLambdaFunctionPricingCalculations(TestCase):
    def test_run_calculations(self):
        self_mock = Mock()
        self_mock._get_charge_and_request_amounts = Mock()
        self_mock._determine_cost = Mock()

        LambdaFunctionPricingCalculations.run_calculations(self_mock)

        self_mock._get_charge_and_request_amounts.assert_called_once()
        self_mock._determine_cost.assert_called_once()

    @patch("samcli.commands.check.lambda_function_pricing_calculations.requests")
    @patch("samcli.commands.check.lambda_function_pricing_calculations.json")
    def test_get_aws_pricing_info(self, patch_json, patch_requests):

        responce_mock = Mock()
        responce_mock.text = Mock()
        responce_text_mock = Mock()

        patch_requests.get.return_value = responce_mock
        patch_json.loads.return_value = responce_text_mock

        result = LambdaFunctionPricingCalculations._get_aws_pricing_info(Mock(), "")

        patch_requests.get.assert_called_once()
        patch_json.loads.assert_called_once()
        self.assertEqual(result, responce_text_mock)

    def test_determine_cost(self):
        self_mock = Mock()
        self_mock._monthly_compute_charge = 0.00001
        self_mock._monthly_request_charge = 0.00002
        self_mock._max_num_of_free_requests = 1000000
        self_mock._max_free_gb_s = 400000

        template_lambda_pricing_info_mock = Mock()
        template_lambda_pricing_info_mock.allocated_memory = 4.1
        template_lambda_pricing_info_mock.allocated_memory_unit = "GB"
        template_lambda_pricing_info_mock.number_of_requests = 4000000
        template_lambda_pricing_info_mock.average_duration = 1984

        self_mock._graph.unique_pricing_info = {}
        self_mock._graph.unique_pricing_info["LambdaFunction"] = template_lambda_pricing_info_mock

        LambdaFunctionPricingCalculations._determine_cost(self_mock)

        self.assertEqual(381.38, self_mock.lambda_pricing_results)

    @patch("samcli.commands.check.lambda_function_pricing_calculations._convert_usage_type")
    @patch("samcli.commands.check.lambda_function_pricing_calculations.get_session")
    def test_get_charge_and_request_amounts(self, patch_session, patch_convert):
        self_mock = Mock()
        self_mock.get_region_prefix = Mock()
        self_mock._get_pricing_or_request_value = Mock()
        self_mock.region_prefix = "@#$"

        product_1 = {"attributes": {"usagetype": "Global-Request", "location": ""}}
        product_2 = {"attributes": {"usagetype": "Global-Lambda-GB-Second", "location": ""}}
        product_3 = {"attributes": {"usagetype": "Lambda-GB-Second", "location": ""}}
        product_4 = {"attributes": {"usagetype": "Request", "location": ""}}

        terms_mock = Mock()
        products = {"1": product_1, "2": product_2, "3": product_3, "4": product_4}

        patch_session.get_config_variable.return_value = ""

        self_mock._get_aws_pricing_info = Mock()
        self_mock._get_aws_pricing_info.return_value = {"products": products, "terms": terms_mock}

        patch_convert.return_value = ["", "Lambda-GB-Second"]

        LambdaFunctionPricingCalculations._get_charge_and_request_amounts(self_mock)

        self_mock._get_pricing_or_request_value.assert_any_call(product_1, terms_mock, "global-request")
        self_mock._get_pricing_or_request_value.assert_any_call(product_2, terms_mock, "global-lambda")
        self_mock._get_pricing_or_request_value.assert_any_call(product_3, terms_mock, "lambda")

        patch_convert.return_value = ["Request", ""]
        LambdaFunctionPricingCalculations._get_charge_and_request_amounts(self_mock)
        self_mock._get_pricing_or_request_value.assert_any_call(product_4, terms_mock, "request")

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
        LambdaFunctionPricingCalculations._get_pricing_or_request_value(self_mock, product, terms, "global-request")
        self.assertEqual(8.15, self_mock._max_num_of_free_requests)

        # testing global-lambda
        LambdaFunctionPricingCalculations._get_pricing_or_request_value(self_mock, product, terms, "global-lambda")
        self.assertEqual(8.15, self_mock._max_free_gb_s)

        # testing lambda
        LambdaFunctionPricingCalculations._get_pricing_or_request_value(self_mock, product, terms, "lambda")
        self.assertEqual(115, self_mock._monthly_compute_charge)

        # testing request
        LambdaFunctionPricingCalculations._get_pricing_or_request_value(self_mock, product, terms, "request")
        self.assertEqual(115, self_mock._monthly_request_charge)

    def test_convert_usage_type(self):
        usage_type = "USW2-Request"
        lambda_request_key = "Request"
        lambda_gb_second_key = "Lambda-GB-Second"
        default_region = False

        result1, result2 = _convert_usage_type(usage_type, lambda_request_key, lambda_gb_second_key, default_region)
        self.assertEqual(result1, lambda_request_key)

        usage_type = "USW2-Lambda-GB-Second"
        result1, result2 = _convert_usage_type(usage_type, lambda_request_key, lambda_gb_second_key, default_region)

        self.assertEqual(result2, lambda_gb_second_key)
