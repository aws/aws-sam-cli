using Amazon.Lambda.Core;
using Amazon.Lambda.APIGatewayEvents;

// Assembly attribute to enable the Lambda function's JSON input to be converted into a .NET class.
[assembly: LambdaSerializer(typeof(Amazon.Lambda.Serialization.Json.JsonSerializer))]

namespace HelloWorld
{

    public class Function
    {

        public string FunctionHandler(APIGatewayProxyRequest apigProxyEvent, ILambdaContext context)
        {
            return "{'message': 'Hello World'}";
        }
    }

    public class FirstFunction
    {

        public string FunctionHandler(APIGatewayProxyRequest apigProxyEvent, ILambdaContext context)
        {
            return "Hello World";
        }
    }

    public class SecondFunction
    {

        public string FunctionHandler(APIGatewayProxyRequest apigProxyEvent, ILambdaContext context)
        {
            return "Hello Mars";
        }
    }
}