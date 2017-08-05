'use strict';

exports.handler = (event, context, callback) => {
    console.log('This is a log mesage from NodeJS 4.3!');
    return callback(null, "Hello, from NodeJS 4.3!");
};
    