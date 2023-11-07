const localDep = require("local-dep");

exports.handler = async (event, context) => {
    return {
        'statusCode': 200,
        'body': JSON.stringify({
            message: localDep.exported(),
        })
    };
}
