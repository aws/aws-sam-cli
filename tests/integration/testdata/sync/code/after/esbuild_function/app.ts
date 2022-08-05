import axios from "axios";

export const lambdaHandler = async (): Promise<object> => {
    let response: object;
    
    try {
        response = {
            'statusCode': 200,
            'body': JSON.stringify({
                message: 'Hello world!',
                extra_message: "banana"
            })
        }
    } catch (err) {
        console.log(err);

        response = {
            'statusCode': 500,
            'body': JSON.stringify({
                message: 'exception happened'
            })
        }
    }

    return response;
};
