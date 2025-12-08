package aws.example;


import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.LambdaLogger;

public class SecondFunction {
    public String myHandler(Context context) {
        LambdaLogger logger = context.getLogger();
        logger.log("Second function Invoked\n");
        return "Hello Mars";
    }
}