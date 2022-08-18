"""
Handles bundler properties as needed to modify the build process
"""
import logging
from copy import deepcopy
from typing import Dict, Optional

from samcli.lib.providers.provider import Stack
from samcli.lib.providers.sam_function_provider import SamFunctionProvider

LOG = logging.getLogger(__name__)

ESBUILD_PROPERTY = "esbuild"


class EsbuildBundlerManager:
    def __init__(self, stack: Stack, template: Optional[Dict] = None):
        self._stack = stack
        self._previous_template = template or dict()

    def esbuild_configured(self) -> bool:
        """
        Checks if esbuild is configured on any resource in a given stack
        :return: True if there is a function instance using esbuild as the build method
        """
        function_provider = SamFunctionProvider([self._stack], ignore_code_extraction_warnings=True)
        functions = list(function_provider.get_all())
        for function in functions:
            if function.metadata and function.metadata.get("BuildMethod", "") == ESBUILD_PROPERTY:
                return True
        return False

    def enable_source_maps(self) -> Dict:
        """
        Appends ``NODE_OPTIONS: --enable-source-maps``, if Sourcemap is set to true
        and sets Sourcemap to true if ``NODE_OPTIONS: --enable-source-maps`` is provided.
        :return: Dict containing deep-copied, updated template
        """
        using_source_maps = False
        invalid_node_option = False

        template = deepcopy(self._previous_template)
        resources = template.get("Resources", {})

        for name, resource in resources.items():
            metadata = resource.get("Metadata", {})

            node_option_set = self._is_node_option_set(resource)

            # check if Sourcemap is provided and append --enable-source-map if not set
            build_properties = metadata.get("BuildProperties", {})
            source_map = build_properties.get("Sourcemap", None)

            if source_map and not node_option_set:
                LOG.info(
                    "\nSourcemap set without --enable-source-maps, adding"
                    " --enable-source-maps to function %s NODE_OPTIONS",
                    name,
                )

                resource.setdefault("Properties", {})
                resource["Properties"].setdefault("Environment", {})
                resource["Properties"]["Environment"].setdefault("Variables", {})
                existing_options = resource["Properties"]["Environment"]["Variables"].setdefault("NODE_OPTIONS", "")

                # make sure the NODE_OPTIONS is a string
                if not isinstance(existing_options, str):
                    invalid_node_option = True
                else:
                    resource["Properties"]["Environment"]["Variables"]["NODE_OPTIONS"] = " ".join(
                        [existing_options, "--enable-source-maps"]
                    )

                using_source_maps = True

            # check if --enable-source-map is provided and append Sourcemap: true if it is not set
            if source_map is None and node_option_set:
                LOG.info(
                    "\n--enable-source-maps set without Sourcemap, adding Sourcemap to"
                    " Metadata BuildProperties for %s",
                    name,
                )

                resource.setdefault("Metadata", {})
                resource["Metadata"].setdefault("BuildProperties", {})
                resource["Metadata"]["BuildProperties"]["Sourcemap"] = True

                using_source_maps = True

        if using_source_maps:
            self._warn_using_source_maps()

        if invalid_node_option:
            self._warn_invalid_node_options()

        return template

    @staticmethod
    def _is_node_option_set(resource: Dict) -> bool:
        """
        Checks if the template has NODE_OPTIONS --enable-source-maps set

        Parameters
        ----------
        resource : Dict
            The resource dictionary to lookup if --enable-source-maps is set

        Returns
        -------
        bool
            True if --enable-source-maps is set, otherwise false
        """
        try:
            node_options = resource["Properties"]["Environment"]["Variables"]["NODE_OPTIONS"]

            return "--enable-source-maps" in node_options.split()
        except (KeyError, AttributeError):
            return False

    @staticmethod
    def _warn_invalid_node_options() -> None:
        """
        Log warning for invalid node options
        """
        LOG.info(
            "\nNODE_OPTIONS is not a string! As a result, the NODE_OPTIONS environment variable will "
            "not be set correctly, please make sure it is a string. "
            "Visit https://nodejs.org/api/cli.html#node_optionsoptions for more details.\n",
        )

    @staticmethod
    def _warn_using_source_maps() -> None:
        """
        Log warning telling user that node options will be set
        :return:
        """
        LOG.info(
            "\nYou are using source maps, note that this comes with a performance hit!"
            " Set Sourcemap to false and remove"
            " NODE_OPTIONS: --enable-source-maps to disable source maps.\n",
        )
