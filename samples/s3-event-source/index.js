'use strict';

exports.handler = (event, context, callback) => {

    for (let record of event.Records) {
        console.log("Got an S3 event:");
        console.log(" - Bucket: " + record.s3.bucket.arn);
        console.log(" - Key: " + record.s3.object.key);
    }

    callback(null, "")

}