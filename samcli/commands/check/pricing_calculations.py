"https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/REGION_INDEX/index.json"
import click

import boto3

import urllib.request
from urllib.error import HTTPError

import ast


class PricingCalculations:
    def __init__(self, graph):
        self.graph = graph
        self.max_num_of_free_requests = None
        self.max_free_GBs = None
        self.monthly_compute_charge = None
        self.monthly_request_charge = None
        self.max_request_skus = [
            "ZQVCC2M69R4S79XS",
            "ZQVCC2M69R4S79XS.A429C66SYZ",
            "ZQVCC2M69R4S79XS.A429C66SYZ.SB2VSFF4TP",
        ]
        self.max_free_GBs_skus = [
            "4VCGJ7EG8PJVZG7S",
            "4VCGJ7EG8PJVZG7S.A429C66SYZ",
            "4VCGJ7EG8PJVZG7S.A429C66SYZ.KJYPJPDD2A",
        ]
        self.compute_skus = [
            "TG3M4CAGBA3NYQBH",
            "TG3M4CAGBA3NYQBH.JRTCKXETXF",
            "TG3M4CAGBA3NYQBH.JRTCKXETXF.6YS6EN2CT7",
        ]
        self.request_charge_skus = [
            "GU2ZS9HVP6QTQ7KE",
            "GU2ZS9HVP6QTQ7KE.JRTCKXETXF",
            "GU2ZS9HVP6QTQ7KE.JRTCKXETXF.6YS6EN2CT7",
        ]

    def run_calculations(self):
        print("RUNNING PRICING CALCULATIONS")
        aws_lambda_pricing_info = self.get_aws_lambda_pricing_info()
        self.get_charge_and_request_amounts(aws_lambda_pricing_info)
        self.determine_cost()

    def get_charge_and_request_amounts(self, aws_lambda_pricing_info):
        self.monthly_compute_charge = float(
            aws_lambda_pricing_info["terms"]["OnDemand"][self.compute_skus[0]][self.compute_skus[1]]["priceDimensions"][
                self.compute_skus[2]
            ]["pricePerUnit"]["USD"]
        )

        self.max_free_GBs = float(
            aws_lambda_pricing_info["terms"]["OnDemand"][self.max_free_GBs_skus[0]][self.max_free_GBs_skus[1]][
                "priceDimensions"
            ][self.max_free_GBs_skus[2]]["endRange"]
        )

        self.monthly_request_charge = float(
            aws_lambda_pricing_info["terms"]["OnDemand"][self.request_charge_skus[0]][self.request_charge_skus[1]][
                "priceDimensions"
            ][self.request_charge_skus[2]]["pricePerUnit"]["USD"]
        )

        self.max_num_of_free_requests = float(
            aws_lambda_pricing_info["terms"]["OnDemand"][self.max_request_skus[0]][self.max_request_skus[1]][
                "priceDimensions"
            ][self.max_request_skus[2]]["endRange"]
        )

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

    def determine_cost(self):
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

        print("FINAL AMOUNT")
        print(monthly_lambda_costs)
