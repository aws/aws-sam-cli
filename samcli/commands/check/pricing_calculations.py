"https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/REGION_INDEX/index.json"
import click

import boto3

import urllib.request
from urllib.error import HTTPError

import ast

from botocore.session import get_session


class PricingCalculations:
    def __init__(self, graph):
        self.graph = graph
        self.lambda_pricing_results = None
        self.max_num_of_free_requests = None
        self.max_free_GBs = None
        self.monthly_compute_charge = None
        self.monthly_request_charge = None
        self.max_request_usage_type = "Global-Request"
        self.max_free_GBs_usage_type = "Global-Lambda-GB-Second"
        self.compute_usage_type = "Lambda-GB-Second"
        self.request_charge_usage_type = "Request"
        self.region_prefix = ""

    def get_lambda_pricing_results(self):
        return self.lambda_pricing_results

    def run_calculations(self):
        self.get_charge_and_request_amounts()
        self.determine_lambda_cost()

    def get_charge_and_request_amounts(self):
        self.get_lambda_charge_and_request_amounts()

    def get_aws_lambda_pricing_info(self):
        try:
            with urllib.request.urlopen(
                "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/us-east-1/index.json"
            ) as f:
                file = f.read().decode("utf-8")
                return ast.literal_eval(file)
        except HTTPError as e:
            if e.code == 403:
                raise Exception("Invalid region id")
            else:
                raise Exception()

    def determine_lambda_cost(self):
        template_lambda_pricing_info = self.graph.get_lambda_function_pricing_info()

        memory_amount = float(template_lambda_pricing_info.get_allocated_memory())
        memory_unit = template_lambda_pricing_info.get_allocated_memory_unit()
        number_of_requests = template_lambda_pricing_info.get_number_of_requests()
        average_duration = template_lambda_pricing_info.get_average_duration()

        # Need to convert to GB if provided in MB
        if memory_unit == "MB":
            memory_amount *= 0.0009765625

        # converts average_duration from ms to seconds within equation
        total_compute_s = number_of_requests * average_duration * 0.001

        total_compute_GB_s = memory_amount * total_compute_s

        total_compute_GB_s -= self.max_free_GBs

        if total_compute_GB_s < 0:
            total_compute_GB_s = 0

        monthly_compute_amount = total_compute_GB_s * self.monthly_compute_charge

        total_requests = number_of_requests - self.max_num_of_free_requests

        if total_requests < 0:
            total_requests = 0

        monthly_request_amount = total_requests * self.monthly_request_charge

        monthly_lambda_costs = round(monthly_compute_amount + monthly_request_amount, 2)

        self.lambda_pricing_results = monthly_lambda_costs

    def get_lambda_charge_and_request_amounts(self):
        aws_lambda_price = self.get_aws_lambda_pricing_info()
        products = aws_lambda_price["products"]
        terms = aws_lambda_price["terms"]

        region = get_session().get_config_variable("region")

        # default is us-east-1, so no prefix is needed for Bulk Api. Every other region needs a prefix
        if region != "us-east-1":
            self.get_region_prefix(region)

        for product in products.values():
            usage_type = self.region_prefix + product["attributes"]["usagetype"]

            if usage_type == self.region_prefix + "Global-Request":
                self.get_pricing_or_request_value(product, terms, "global-request")

            elif usage_type == self.region_prefix + "Global-Lambda-GB-Second":
                self.get_pricing_or_request_value(product, terms, "global-lambda")

            elif usage_type == self.region_prefix + "Lambda-GB-Second":
                self.get_pricing_or_request_value(product, terms, "lambda")

            elif usage_type == self.region_prefix + "Request":
                self.get_pricing_or_request_value(product, terms, "request")

    def get_pricing_or_request_value(self, product, terms, get_type):
        sku = product["sku"]

        temp_key = terms["OnDemand"][sku]

        """
        The dictionaries have unknown sku numbers. To prevent a massive storage of over
        400 sku numbers, plus 2 additional unique keys per sku number, a temp_key is used
        to bypass the need to know the keys. This is just to hold the value of the first
        key in a given dictionary until the final path is reached. It is only done when
        there is only one value in a given object.
        """
        temp_key = next(iter(temp_key.values()))
        temp_key = temp_key["priceDimensions"]
        price_dimentions = next(iter(temp_key.values()))

        if get_type == "global-request":
            self.max_num_of_free_requests = float(price_dimentions["endRange"])
        elif get_type == "global-lambda":
            self.max_free_GBs = float(price_dimentions["endRange"])
        elif get_type == "lambda":
            self.monthly_compute_charge = float(price_dimentions["pricePerUnit"]["USD"])
        elif get_type == "request":
            self.monthly_request_charge = float(price_dimentions["pricePerUnit"]["USD"])

    def get_region_prefix(self, region):
        if region == "ap-northeast-1":
            self.region_prefix = "APN1-"
        elif region == "ap-northeast-2":
            self.region_prefix = "APN2-"
        elif region == "ap-south-1":
            self.region_prefix = "APS3-"
        elif region == "ap-southeast-1":
            self.region_prefix = "APS1-"
        elif region == "ap-southeast-2":
            self.region_prefix = "APS2-"
        elif region == "ca-central-1":
            self.region_prefix = "CAN1-"
        elif region == "eu-central-1":
            self.region_prefix = "EUC1-"
        elif region == "eu-north-1":
            self.region_prefix = "EUN1-"
        elif region == "eu-south-1":
            self.region_prefix = "EUS1-"
        elif region == "eu-west-1":
            self.region_prefix = "EU-"
        elif region == "eu-west-2":
            self.region_prefix = "EUW2-"
        elif region == "eu-west-3":
            self.region_prefix = "EUW3-"
        elif region == "me-south-1":
            self.region_prefix = "MES1-"
        elif region == "sa-east-1":
            self.region_prefix = "SAE1-"
        elif region == "us-east-1":
            self.region_prefix = "USE1-"
        elif region == "us-gov-east-1":
            self.region_prefix = "UGE1-"
        elif region == "us-gov-west-1":
            self.region_prefix = "UGW1-"
        elif region == "us-west-1":
            self.region_prefix = "USW1-"
        elif region == "us-west-2":
            self.region_prefix = "USW2-"
        elif region == "ap-east-1":
            self.region_prefix = "APE1-"
        elif region == "af-south-1":
            self.region_prefix = "AFS1-"
        elif region == "us-east-2":
            self.region_prefix = "USE2-"
        else:
            raise Exception("Invalid region. Please use a valid region to calcualte pricing of application")
