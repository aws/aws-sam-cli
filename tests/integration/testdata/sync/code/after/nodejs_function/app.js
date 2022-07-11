import * as faker from '@faker-js/faker';

const name = faker.faker.name.firstName();
let response;

exports.lambdaHandler = async (event, context) => {
    try {
        response = {
            'statusCode': 200,
            'body': JSON.stringify({
                message: 'Hello world!',
                extra_message: name
            })
        }
    } catch (err) {
        console.log(err);
        return err;
    }

    return response
};
