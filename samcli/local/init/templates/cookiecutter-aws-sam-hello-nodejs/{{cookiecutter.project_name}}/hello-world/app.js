/**
 *
 * Event doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html#api-gateway-simple-proxy-for-lambda-input-format
 * @param {Object} event - API Gateway Lambda Proxy Input Format
 *
 * Context doc: https://docs.aws.amazon.com/lambda/latest/dg/nodejs-prog-model-context.html 
 * @param {Object} context
 *
 * Return doc: https://docs.aws.amazon.com/apigateway/latest/developerguide/set-up-lambda-proxy-integrations.html
 * @returns {Object} object - API Gateway Lambda Proxy Output Format
 * 
 */
{%- if cookiecutter.runtime == 'nodejs6.10' or cookiecutter.runtime == 'nodejs4.3' %}
exports.lambdaHandler = function (event, context, callback) {
    var response = {
        statusCode: 200,
        body: JSON.stringify({
            message: 'hello world'
        })
    }

    callback(null, response);
};
{%- else %}
exports.lambdaHandler = async (event, context) => {
    var response = {
        statusCode: 200,
        body: JSON.stringify({
            message: 'hello world'
        })
    }

    return response
};
{% endif %}
