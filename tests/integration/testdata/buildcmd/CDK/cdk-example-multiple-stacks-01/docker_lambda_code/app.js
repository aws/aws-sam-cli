'use strict';

const AWS = require('aws-sdk');
const log = require('lambda-log');

module.exports.get = (event, context, callback) => {

    log.options.debug = true;
    log.debug(params);

    const response = {
        statusCode: 200,
        body: JSON.stringify({
            "message": "hello world!!! docker"
        })
    };
    log.debug(response);
    callback(null, response);
};