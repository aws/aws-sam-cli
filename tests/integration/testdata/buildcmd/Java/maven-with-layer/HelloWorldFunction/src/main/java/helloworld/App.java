package helloworld;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.LambdaLogger;

import helloworldlayer.SimpleMath;

/**
 * Handler for requests to Lambda function.
 */
public class App {

    public String handleRequest(Context context) {
        int sumResult = SimpleMath.sum(7, 5);
        return String.format("hello world. sum is %d.", sumResult);
    }
}
