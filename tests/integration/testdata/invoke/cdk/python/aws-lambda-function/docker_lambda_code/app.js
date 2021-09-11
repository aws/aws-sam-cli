'use strict';

module.exports.get = (event, context, callback) => {
    const response = {
        statusCode: 200,
        body: JSON.stringify({
            "message": "Hello world from Docker!"
        })
    };
    callback(null, response);
};