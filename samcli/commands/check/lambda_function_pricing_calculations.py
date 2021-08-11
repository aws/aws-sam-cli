"""
Class for calculating pricing information for all lambda functiuons
"""

from typing import List
import urllib.request
from urllib.error import HTTPError

import ast

from botocore.session import get_session

from samcli.commands.check.pricing_calculations import PricingCalculations


class LambdaFunctionPricingCalculations(PricingCalculations):
    def __init__(self, graph):
        super().__init__(graph)
        self._max_num_of_free_requests = None
        self._max_free_gb_s = None
        self._monthly_compute_charge = None
        self._monthly_request_charge = None
        self._max_request_usage_type = "Global-Request"
        self._max_free_gb_s_usage_type = "Global-Lambda-GB-Second"
        self._compute_usage_type = "Lambda-GB-Second"
        self._request_charge_usage_type = "Request"

        self.lambda_pricing_results = None

    def get_aws_pricing_info(self, region):
        return _get_aws_lambda_pricing_info(region)

    def determine_cost(self) -> None:
        self._determine_lambda_cost()

    def run_calculations(self) -> None:
        self.get_charge_and_request_amounts()
        self.determine_cost()

    def get_charge_and_request_amounts(self) -> None:
        self._get_lambda_charge_and_request_amounts()

    def _determine_lambda_cost(self) -> None:
        """
        Determines the cost of running all lambda functions based on the
        answers the user provided for lamnda function pricing
        """
        template_lambda_pricing_info = self.graph.unique_pricing_info["LambdaFunction"]

        memory_amount = float(template_lambda_pricing_info.allocated_memory)
        memory_unit = template_lambda_pricing_info.allocated_memory_unit
        number_of_requests = template_lambda_pricing_info.number_of_requests
        average_duration = template_lambda_pricing_info.average_duration

        # Need to convert to GB if provided in MB
        if memory_unit == "MB":
            memory_amount *= 0.0009765625

        # converts average_duration from ms to seconds within equation
        total_compute_s = number_of_requests * average_duration * 0.001

        total_compute_gb_s = memory_amount * total_compute_s

        total_compute_gb_s -= self._max_free_gb_s

        if total_compute_gb_s < 0:
            total_compute_gb_s = 0

        monthly_compute_amount = total_compute_gb_s * self._monthly_compute_charge

        total_requests = number_of_requests - self._max_num_of_free_requests

        if total_requests < 0:
            total_requests = 0

        monthly_request_amount = total_requests * self._monthly_request_charge

        monthly_lambda_costs = round(monthly_compute_amount + monthly_request_amount, 2)

        self.lambda_pricing_results = monthly_lambda_costs

    def _get_lambda_charge_and_request_amounts(self) -> None:
        """
        Gets the charge and request amouint from the AWS Price List API
        """
        region = get_session().get_config_variable("region")

        aws_lambda_price = self.get_aws_pricing_info(region)
        products = aws_lambda_price["products"]
        terms = aws_lambda_price["terms"]
        default_region = False

        # default is us-east-1, so no prefix is needed for Bulk Api. Every other region needs a prefix
        if region == "us-east-1":
            default_region = True

        for product in products.values():
            location = product["attributes"]["location"]

            lambda_gb_second_key = "Lambda-GB-Second"
            lambda_request_key = "Request"
            global_request = "Global-Request"
            global_lambda_gb_second = "Global-Lambda-GB-Second"

            usage_type = product["attributes"]["usagetype"]

            modified_lambda_request_key, modified_lambda_gb_second_key = _convert_usage_type(
                usage_type, lambda_request_key, lambda_gb_second_key, default_region
            )

            if usage_type == global_request:
                self._get_pricing_or_request_value(product, terms, "global-request")

            elif usage_type == global_lambda_gb_second:
                self._get_pricing_or_request_value(product, terms, "global-lambda")

            elif modified_lambda_gb_second_key == lambda_gb_second_key and location != "Any":
                self._get_pricing_or_request_value(product, terms, "lambda")

            elif modified_lambda_request_key == lambda_request_key and location != "Any":
                self._get_pricing_or_request_value(product, terms, "request")

    def _get_pricing_or_request_value(self, product, terms, get_type) -> None:
        """
        The dictionaries have unknown sku numbers. To prevent a massive storage of over
        400 sku numbers, plus 2 additional unique keys per sku number, a temp_key is used
        to bypass the need to know the keys. This is just to hold the value of the first
        key in a given dictionary until the final path is reached. It is only done when
        there is only one value in a given object.
        """
        sku = product["sku"]

        temp_key = terms["OnDemand"][sku]

        temp_key = next(iter(temp_key.values()))
        temp_key = temp_key["priceDimensions"]
        price_dimentions = next(iter(temp_key.values()))

        if get_type == "global-request":
            self._max_num_of_free_requests = float(price_dimentions["endRange"])
        elif get_type == "global-lambda":
            self._max_free_gb_s = float(price_dimentions["endRange"])
        elif get_type == "lambda":
            self._monthly_compute_charge = float(price_dimentions["pricePerUnit"]["USD"])
        elif get_type == "request":
            self._monthly_request_charge = float(price_dimentions["pricePerUnit"]["USD"])


def _get_aws_lambda_pricing_info(region: str):
    """
    Gets AWS Price List API json file for appropriate reigon and resource

    Parameters
    ----------
        region: str
            The region associated with the users account or their preset
            region, if it exists.

    Raises
    ------
        Exception: error code 403
            An invalid region id is used
        Exception
            Catches remaining exceptions

    Returns
    -------
        file
            Returns the json file from the API
    """
    try:
        with urllib.request.urlopen(
            "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/" + region + "/index.json"
        ) as f:
            file = f.read().decode("utf-8")
            return ast.literal_eval(file)
    except HTTPError as e:
        if e.code == 403:
            raise Exception("Invalid region id") from e
        raise Exception() from e


def _convert_usage_type(
    usage_type: str, lambda_request_key: str, lambda_gb_second_key: str, default_region: bool
) -> List[str]:
    """
    Converts the usage_type into a format that can be used to find the correct pricing
    or request value. This is a work around to avoid using the abreviation of every
    region to find the correct pricing or request value in the AWS Price List API json file

    It's unknown if the request or pricing key value is hidden within the usage_type, so
    it is checked for both. Only one can be in a single usage_type at a given time.

    Parameters
    ----------
        usage_type: str
            The usage type, which includes the region abreviation
        lambda_request_key: str
            The lambda request key we are looking for in the usage_type
        lambda_gb_second_key: str
            The gb_second pricing key we are looking for in the usage_type
        default_region: bool
            The default region does not have any region abrviations within it,
            so nothing needs to be done

    Returns:
        Tuple[str, str]:
            Returns the request and pricing keys, but without the unecessary
            region abreviation
    """
    modified_lambda_request_key = ""
    modified_lambda_gb_second_key = ""

    usage_type_length = len(usage_type)
    lambda_request_key_length = len(lambda_request_key)
    lambda_gb_second_key_length = len(lambda_gb_second_key)

    if default_region:
        return [usage_type, usage_type]

    if usage_type_length >= lambda_request_key_length:
        modified_lambda_request_key = usage_type[usage_type_length - lambda_request_key_length :]

    if usage_type_length >= lambda_gb_second_key_length:
        modified_lambda_gb_second_key = usage_type[usage_type_length - lambda_gb_second_key_length :]

    return [modified_lambda_request_key, modified_lambda_gb_second_key]
