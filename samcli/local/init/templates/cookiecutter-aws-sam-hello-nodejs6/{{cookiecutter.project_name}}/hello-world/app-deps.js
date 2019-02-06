var axios = require('axios')
var url = 'http://checkip.amazonaws.com/';
var response;


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
exports.lambdaHandler = function (event, context, callback) {
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
            console.log(err);
            callback(err);
        });
};
