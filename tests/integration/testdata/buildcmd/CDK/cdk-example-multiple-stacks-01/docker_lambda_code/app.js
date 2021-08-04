'use strict';

const log = require('lambda-log');

module.exports.get = (event, context, callback) => {

    log.options.debug = true;
    log.debug(params);

    const response = {
        statusCode: 200,
        body: JSON.stringify({
            "message": "hello world from Docker"
        })
    };
    log.debug(response);
    callback(null, response);
};