const localdep = require("local-dependency");

exports.lambdaHandler = async (event, context) => {
    return localdep.lambdaHandler(event, context)
}
