'use strict';

// A simple hello world Lambda function
exports.handler = (event, context, callback) => {

    console.log('DEBUG: Name is ' + event.name);
    callback(null, "Hello " + event.name);

}
