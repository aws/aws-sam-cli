const faker = require("@faker-js/faker");

exports.handler = async (event, context) => {
    const name = faker.faker.name.firstName();
    
    return {
        'statusCode': 200,
        'body': "foo bar"
    }
}