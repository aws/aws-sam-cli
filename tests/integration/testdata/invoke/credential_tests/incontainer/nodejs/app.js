const { STS } = require('@aws-sdk/client-sts');
let sts = new STS();

exports.lambdaHandler = async (event, context) => {
    let response;
    try {
        const sts_response = await sts.getCallerIdentity();

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