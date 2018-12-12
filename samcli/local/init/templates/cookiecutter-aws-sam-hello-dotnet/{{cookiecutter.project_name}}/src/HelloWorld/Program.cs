using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;
using Newtonsoft.Json;

using Amazon.Lambda.Core;
using Amazon.Lambda.APIGatewayEvents;

// Assembly attribute to enable the Lambda function's JSON input to be converted into a .NET class.
[assembly: LambdaSerializer(typeof(Amazon.Lambda.Serialization.Json.JsonSerializer))]

namespace HelloWorld
{

    public class Function
    {

        public APIGatewayProxyResponse FunctionHandler(APIGatewayProxyRequest apigProxyEvent, ILambdaContext context)
        {

            Dictionary<string, string> body = new Dictionary<string, string>
            {
                { "message", "hello world" }
            };

            return new APIGatewayProxyResponse
            {
                Body = JsonConvert.SerializeObject(body),
                StatusCode = 200,
                Headers = new Dictionary<string, string> { { "Content-Type", "application/json" } }
            };
        }
    }
}
