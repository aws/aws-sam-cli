"""Database helper utilities for DynamoDB operations."""

import boto3


def get_table(table_name):
    """Get a DynamoDB table resource."""
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(table_name)


def scan_table(table_name):
    """Scan all items from a DynamoDB table."""
    table = get_table(table_name)
    response = table.scan()
    return response.get("Items", [])
