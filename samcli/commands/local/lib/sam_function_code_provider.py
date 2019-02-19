"""
Class that provides codeuri from a given Function definition
"""

import logging
import os
import six

LOG = logging.getLogger(__name__)


class SamFunctionCodeProvider(object):
    """
    Lambda Function Code provider

        Parameters
        ----------
        function_name str
            FunctionId
        resource_properties dict
            Function dictionary
        function_type str
            Either Serverless::Function or Lambda::Function
    """

    _SERVERLESS_FUNCTION = "AWS::Serverless::Function"
    _LAMBDA_FUNCTION = "AWS::Lambda::Function"
    _DEFAULT_CODEURI = "."

    def __init__(self, function_name, resource_properties, function_type):
        """ Store Function info
        This Class is a Provider for the codeuri property hold the path to an existing file/folder
        or a pointer to a folder used to store InlineCode/ZipFile string property (Inline Lambdas)
        It also provide a context manager function to dump the code inside a cache path and remove it
        after invocation
        """
        self.function_name = function_name
        self.handler = resource_properties.get('Handler')
        self.runtime = resource_properties.get('Runtime')
        self.index = self._setup_postfix(self.runtime)

        self.inlinecode = self._extract_inline_code(resource_properties, function_type)
        if self.inlinecode:
            self.codeuri = './.aws-sam/inline/{}/'.format(function_name)
        else:
            self.codeuri = self._extract_code_uri(function_name, resource_properties, function_type)

    def __enter__(self):
        """ Dump Inline Code, if present for this Code Provider """
        if self.inlinecode:
            self._dump_code(self.inlinecode, self.codeuri, self.index)
        return self

    def __exit__(self, *exc):
        """ CleanUp Resources created when using Inline code """
        if self.inlinecode:
            self._cleanup(self.codeuri, self.index)

    def __repr__(self):
        return repr(self.codeuri)

    def __fspath__(self):
        return self.codeuri

    @staticmethod
    def _setup_postfix(runtime):
        index = 'index'
        if runtime and runtime.startswith('python'):
            return index + '.py'
        return index

    @staticmethod
    def _extract_inline_code(resource_properties, function_type):
        """ Parse InlineCode from and return the content or None """
        code = None
        if function_type == SamFunctionCodeProvider._SERVERLESS_FUNCTION:
            code = resource_properties.get('InlineCode')
        elif function_type == SamFunctionCodeProvider._LAMBDA_FUNCTION:
            code = resource_properties.get('Code')
            if isinstance(code, dict):
                code = code.get('ZipFile')
        if code:
            return SamFunctionCodeProvider._sanitize_inlinecode(code)
        return code

    @staticmethod
    def _extract_code_uri(function_name, resource_properties, function_type):
        """ Based off Function Type, normalize the structure to return a path """
        if function_type == SamFunctionCodeProvider._SERVERLESS_FUNCTION:
            return SamFunctionCodeProvider.extract_codeuri(function_name, resource_properties, 'CodeUri')
        elif function_type == SamFunctionCodeProvider._LAMBDA_FUNCTION:
            return SamFunctionCodeProvider.extract_code(resource_properties, 'Code')

    @staticmethod
    def extract_codeuri(name, resource_properties, code_property_key):
        """
        Extracts the SAM Function CodeUri from the Resource Properties

        Parameters
        ----------
        name str
            LogicalId of the resource
        resource_properties dict
            Dictionary representing the Properties of the Resource
        code_property_key str
            Property Key of the code on the Resource

        Returns
        -------
        str
            Representing the local code path
        """
        codeuri = resource_properties.get(code_property_key, SamFunctionCodeProvider._DEFAULT_CODEURI)
        # CodeUri can be a dictionary of S3 Bucket/Key or a S3 URI, neither of which are supported
        if isinstance(codeuri, dict) or \
                (isinstance(codeuri, six.string_types) and codeuri.startswith("s3://")):
            codeuri = SamFunctionCodeProvider._DEFAULT_CODEURI
            LOG.warning("Lambda function '%s' has specified S3 location for CodeUri which is unsupported. "
                        "Using default value of '%s' instead", name, codeuri)
        return codeuri

    @staticmethod
    def extract_code(resource_properties, code_property_key):
        """
        Extracts the Lambda Function Code from the Resource Properties

        Parameters
        ----------
        resource_properties dict
            Dictionary representing the Properties of the Resource
        code_property_key str
            Property Key of the code on the Resource

        Returns
        -------
        str
            Representing the local code path
        """

        codeuri = resource_properties.get(code_property_key, SamFunctionCodeProvider._DEFAULT_CODEURI)

        if isinstance(codeuri, dict):
            codeuri = SamFunctionCodeProvider._DEFAULT_CODEURI

        return codeuri

    @staticmethod
    def _dump_code(inlinecode, path, index='index'):
        """ Dump InlineCode to specified cache file """
        if not os.path.exists(path):
            os.makedirs(path)
            os.chmod(path, 0o755)
        with open(path + index, 'w') as code:
            code.write(inlinecode)

    @staticmethod
    def _cleanup(path, index='index'):
        """ Delete InlineCode file """
        try:
            os.remove(path + index)
        except IOError:
            # We don't care as we use here to cleanup resources
            pass

    @staticmethod
    def _sanitize_inlinecode(inlinecode):
        """
        Verify if InlineCode has runtime substitution
        """
        # InlineCode isn't type safe
        if isinstance(inlinecode, dict):
            # We expect to have only 1 keypair..
            inlinecode = list(inlinecode.values())[0]
            # Not sopporting !Sub as of now
            raise NotImplementedError('Not able to parse inline code because of !Sub presence')
        return inlinecode
