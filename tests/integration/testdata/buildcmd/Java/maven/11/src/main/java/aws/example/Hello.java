package aws.example;


import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.LambdaLogger;

public class Hello {
    public String myHandler(Context context) {
        LambdaLogger logger = context.getLogger();
        logger.log("Function Invoked\n");
        return "Hello World";
    }
}