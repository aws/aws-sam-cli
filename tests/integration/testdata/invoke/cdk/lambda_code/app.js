let response;

exports.lambdaFunctionNameHandler = async (event, context) => {
    try {
        response = {
            'statusCode': 200,
            'body': JSON.stringify({
                message: context.functionName,
            })
        }
    } catch (err) {
        console.log(err);
        return err;
    }

    return response
};