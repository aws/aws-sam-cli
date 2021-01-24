package sts;

import com.amazonaws.auth.EnvironmentVariableCredentialsProvider;
import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.APIGatewayProxyRequestEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayProxyResponseEvent;
import com.amazonaws.services.securitytoken.AWSSecurityTokenService;
import com.amazonaws.services.securitytoken.AWSSecurityTokenServiceClientBuilder;
import com.amazonaws.services.securitytoken.model.GetCallerIdentityRequest;
import com.amazonaws.services.securitytoken.model.GetCallerIdentityResult;

import java.util.HashMap;
import java.util.Map;

/**
 * Handler for requests to Lambda function.
 */
public class App implements RequestHandler<APIGatewayProxyRequestEvent, APIGatewayProxyResponseEvent> {

    public APIGatewayProxyResponseEvent handleRequest(final APIGatewayProxyRequestEvent input, final Context context) {
        AWSSecurityTokenServiceClientBuilder awsSecurityTokenServiceClientBuilder =
            AWSSecurityTokenServiceClientBuilder.standard();
        awsSecurityTokenServiceClientBuilder.setCredentials(new EnvironmentVariableCredentialsProvider());
        AWSSecurityTokenService securityClient = awsSecurityTokenServiceClientBuilder.build();
        GetCallerIdentityRequest securityRequest = new GetCallerIdentityRequest();
        GetCallerIdentityResult securityResponse = securityClient.getCallerIdentity(securityRequest);

        Map<String, String> headers = new HashMap<>();
        headers.put("Content-Type", "application/json");
        headers.put("X-Custom-Header", "application/json");
        APIGatewayProxyResponseEvent response = new APIGatewayProxyResponseEvent()
                .withHeaders(headers);

        String output = String.format("{ \"message\": \"hello world\", \"account\": \"%s\" }",
            securityResponse.getAccount());

        return response
            .withStatusCode(200)
            .withBody(output);
    }

}
