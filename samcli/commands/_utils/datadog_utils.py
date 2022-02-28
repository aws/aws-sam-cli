import click

DATADOG_LIVE_TAIL_URL = "https://app.datadoghq.com/logs/livetail?query=functionname%3A"

def generate_datadog_url(resource_information_list):
    lambda_functions = [r for r in resource_information_list if r.resource_type == 'AWS::Lambda::Function']
    if len(lambda_functions) == 0: 
        click.echo(
            "There are no lambda functions in your stack."
        )
        return

    click.echo(
        "If your functions are instrumented with Datadog, use the following links to see datadog live tailed logs:"
    )
    for resource in resource_information_list:
        if resource.resource_type != 'AWS::Lambda::Function': continue
        physical_resource_id = resource.physical_resource_id.lower()
        logical_resource_id = resource.logical_resource_id
        url = DATADOG_LIVE_TAIL_URL + physical_resource_id
        click.echo(
            "{function_name}: {datadog_url}".format(function_name=logical_resource_id, datadog_url=url)
        )
