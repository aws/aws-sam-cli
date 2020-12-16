let AWS = require('aws-sdk');
let sts = new AWS.STS();

exports.lambdaHandler = async (event, context) => {
    let response;
    try {
        const sts_response = await sts.getCallerIdentity().promise();

        response = {
            'statusCode': 200,
            'body': JSON.stringify({
                message: 'hello world',
                account: sts_response.Account
            })
        }
    } catch (err) {
        console.log(err);
        return err;
    }

    return response
};