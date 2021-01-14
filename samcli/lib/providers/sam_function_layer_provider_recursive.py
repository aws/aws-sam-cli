import itertools
import os
import pathlib
from typing import Union, Type, Optional, Dict, List

from samcli.lib.providers.sam_base_provider import SamBaseProvider
from samcli.lib.providers.sam_function_provider import SamFunctionProvider
from samcli.lib.providers.sam_layer_provider import SamLayerProvider
from samcli.lib.providers.sam_nested_app_provider import SamNestedAppProvider


def find_providers_recursively(
    provider_type: Union[Type[SamFunctionProvider], Type[SamLayerProvider], Type[SamNestedAppProvider]],
    template_file: str,
    parameter_overrides: Optional[Dict],
    app_prefix: str,
    **kwargs,
):
    providers = [provider_type(app_prefix, template_file, parameter_overrides, **kwargs)]

    nested_app_provider = SamNestedAppProvider(app_prefix, template_file, parameter_overrides)
    for nested_app in nested_app_provider.get_all():
        providers.extend(
            find_providers_recursively(
                provider_type,
                pathlib.Path(os.path.dirname(template_file), nested_app.location),
                nested_app.parameters,
                app_prefix + f"{nested_app.name}/",
                **kwargs,
            )
        )
    return providers


class SamRecursiveFunctionProvider(SamBaseProvider):
    _providers: List[SamFunctionProvider]

    def __init__(
        self, template_file: str, parameter_overrides=None, ignore_code_extraction_warnings=False, base_url=None
    ):
        self._providers = find_providers_recursively(
            SamFunctionProvider,
            template_file,
            parameter_overrides,
            "",
            ignore_code_extraction_warnings=ignore_code_extraction_warnings,
            base_url=base_url,
        )

    def get(self, name):
        for provider in self._providers:
            resource = provider.get(name)
            if resource:
                return resource
        return None

    def get_all(self):
        return itertools.chain.from_iterable([provider.get_all() for provider in self._providers])


class SamRecursiveLayerProvider(SamBaseProvider):
    _providers: List[SamFunctionProvider]

    def __init__(self, template_file: str, parameter_overrides=None, base_url=None):
        self._providers = find_providers_recursively(
            SamLayerProvider, template_file, parameter_overrides, "", base_url=base_url
        )

    def get(self, name):
        for provider in self._providers:
            resource = provider.get(name)
            if resource:
                return resource
        return None

    def get_all(self):
        return itertools.chain.from_iterable([provider.get_all() for provider in self._providers])


class SamRecursiveAppProvider(SamBaseProvider):
    _providers: List[SamNestedAppProvider]

    def __init__(self, template_file: str, parameter_overrides=None, base_url=None):
        self._providers = find_providers_recursively(
            SamNestedAppProvider, template_file, parameter_overrides, "", base_url=base_url
        )

    def get(self, name):
        for provider in self._providers:
            resource = provider.get(name)
            if resource:
                return resource
        return None

    def get_all(self):
        return itertools.chain.from_iterable([provider.get_all() for provider in self._providers])
