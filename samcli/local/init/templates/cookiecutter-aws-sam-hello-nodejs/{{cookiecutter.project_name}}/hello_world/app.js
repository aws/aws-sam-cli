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
            console.log(err);
            callback(err, "");
        });    
};
{% else %}
exports.lambda_handler = async (event, context, callback) => {
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
        console.log(err);
        callback(err, null);
    }

    callback(null, response)
};
{% endif %}