'use strict';

// Make sure to run 'npm install' before running this function.
// This will fetch the AWS SDK to ./node_modules.

// Create a new AWS SDK object
const AWS = require('aws-sdk');

// Create S3 service object
const s3 = new AWS.S3({apiVersion: '2006-03-01'});

exports.handler = (event, context, callback) => {
  
    s3.listBuckets((err, data) => {

        if(err){
            console.log("Error listing S3 buckets: " + err);
            callback(err, null);
            return;
        }

        for (let bucket of data.Buckets){
            console.log("s3://" + bucket.Name)
            callback(null, "ok")
        }

    })

}