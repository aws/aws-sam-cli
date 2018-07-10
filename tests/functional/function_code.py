"""
Helper class for tests to generate code folders with different types of Lambda functions
"""

import tempfile
import os
import shutil

from contextlib import contextmanager

# Echoes the input back as result
ECHO_CODE = """
exports.handler = function(event, context, callback){

    console.log("Hello World"); 
    callback(null, event)
}
"""

# Sleeps for input number of seconds before returning
SLEEP_CODE = """
exports.handler = function(event, context, callback) {
    // Duration for the sleep comes in the event
    
    duration = event * 1000 // milliseconds
    setTimeout(function() { callback(null, event) }, duration)
}
"""

# Returns all  the environment variables as an output
GET_ENV_VAR = """
exports.handler = function(event, context, callback) {
    callback(null, process.env)
}
"""

CONSOLE_LOG_LAMBDA = """
exports.handler = function(event, context, callback) {
    console.log("Hello World")
    callback(null, null)
}
"""

HELLO_FROM_LAMBDA = """
exports.handler = function(event, context) {
    context.done(null, 'Hello from Lambda');
};
"""

THROW_ERROR_LAMBDA = """
exports.handler = function(event, context, callback) {
    var error = new Error("something is wrong");
    callback(error);
};
"""

API_GATEWAY_ECHO_EVENT = """
exports.handler = function(event, context, callback){

    response = {"statusCode":200,"headers":{},"body":JSON.stringify(event),"isBase64Encoded":false}
    context.done(null, response);
}
"""

API_GATEWAY_BAD_PROXY_RESPONSE = """
exports.handler = function(event, context, callback){

    response = "Non Proxy Response"
    context.done(null, response);
}
"""

API_GATEWAY_CONTENT_TYPE_LOWER = """
exports.handler = function(event, context, callback){
    body = JSON.stringify("hello")

    response = {"statusCode":200,"headers":{"content-type":"text/plain"},"body":body,"isBase64Encoded":false}
    context.done(null, response);
}
"""

API_GATEWAY_ECHO_BASE64_EVENT = """
exports.base54request = function(event, context, callback){

    response = {"statusCode":200,"headers":{"Content-Type":"image/gif"},"body":event["body"],"isBase64Encoded":event["isBase64Encoded"]}
    context.done(null, response);
}

exports.echoimagehandler = function(event, context, callback) {

    gifImageBase64 = "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"

    callback(null, {
        statusCode: 200,
        body: gifImageBase64,

        // API Gateway will automatically convert the base64 encoded response to binary if the Accept header in 
        // request matches the Content-Type of response. Unfortunately, if you use this in an HTML Image tag
        // <img src="https://your-api"/>, then browsers don't send a specific Accept header. Therefore API Gateway 
        // will return the base64 text response. If serving image in HTML tag is your primary usecase,
        // then you can use */* as value for BinaryMediaType which will make API Gateway treat every response
        // as binary type, and hence decode base64 always.
        isBase64Encoded: true,
        headers: {
            "Content-Type": "image/gif"
        }
    });
}
"""


def nodejs_lambda(code):
    """
    In a temporary directory, create "index.js" file with the passed in code and return directory path.
    This is a contextmanager. So it can be used inside `with` statements to automatically cleanup
    temp folder upon exit

    :param string code: Code to be written to the index.js file
    :return string: directory path

    """
    directory = tempfile.mkdtemp()
    filename = os.path.join(directory, "index.js")

    with open(filename, "w+") as fp:
        fp.write(code)
        fp.flush()

    # The directory that Python returns might have symlinks. The Docker File sharing settings will not resolve
    # symlinks. Hence get the real path before passing to Docker.
    return os.path.realpath(directory)

@contextmanager
def make_zip(directory, extension="zip"):
    """
    Zip up the contents of the directory and return path to the zipfile. This method can be used inside a ``with``
    statement so it will cleanup the zipfile after the context exists.

    :param string directory: Path to the directory to zip up
    :param string extension: Extension for the file
    :return string: Path to the zip file
    """
    tmpdir = None

    try:
        tmpdir = tempfile.mkdtemp()
        path_prefix = os.path.join(tmpdir, "code")

        zipfile_current_path = shutil.make_archive(path_prefix, 'zip', directory)

        # shutil always sets the file with .zip extension. Hence rename/move the file to be with right extension
        expected_path = path_prefix + "." + extension
        os.rename(zipfile_current_path, expected_path)

        yield expected_path
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir)
