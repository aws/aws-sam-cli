{%- if cookiecutter.runtime == 'nodejs4.3' %}
var axios = require('axios')
var url = 'http://checkip.amazonaws.com/';
var response;
{%- else %}
const axios = require('axios')
const url = 'http://checkip.amazonaws.com/';
let response;
{%- endif %}

{% if cookiecutter.runtime == 'nodejs6.10' or cookiecutter.runtime == 'nodejs4.3' %}
exports.lambda_handler = function (event, context, callback) {
    axios(url)
        .then(function (ret) {
            response = {
                'statusCode': 200,
                'body': JSON.stringify({
                    message: 'hello world',
                    location: ret.data.trim()
                })
            }
            callback(null, response);
        })
        .catch(function (err) {
            error = {
                "lambda_request_id": context.awsRequestId,
                "lambda_log_group": context.logGroupName,
                "lambda_log_stream": context.logStreamName,
                "apigw_request_id": event.requestContext.requestId,
                "error_message": err,
            }

            console.error(error);

            response = {
                'statusCode': 500,
                'body': JSON.stringify({
                    message: 'Something went wrong :(',
                    request_id: error.apigw_request_id
                })
            }

            callback(null, response);
        });
};
{% else %}
exports.lambda_handler = async (event, context) => {
    try {
        const ret = await axios(url);
        response = {
            'statusCode': 200,
            'body': JSON.stringify({
                message: 'hello world',
                location: ret.data.trim()
            })
        }
    }
    catch (err) {
        error = {
            "lambda_request_id": context.awsRequestId,
            "lambda_log_group": context.logGroupName,
            "lambda_log_stream": context.logStreamName,
            "apigw_request_id": event.requestContext.requestId,
            "error_message": err,
        }

        console.error(error);

        response = {
            'statusCode': 500,
            'body': JSON.stringify({
                message: 'Something went wrong :(',
                request_id: error.apigw_request_id
            })
        }

        return response
    }

    return response
};
{% endif %}