using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading.Tasks;

using Newtonsoft.Json;
using Xunit;
using Amazon.Lambda.Core;
using Amazon.Lambda.TestUtilities;
using Amazon.Lambda.APIGatewayEvents;

namespace HelloWorld.Tests
{
  public class FunctionTest
  {

    [Fact]
    public void TestHelloWorldFunctionHandler()
    {
            TestLambdaContext context;
            APIGatewayProxyRequest request;
            APIGatewayProxyResponse response;

            request = new APIGatewayProxyRequest();
            context = new TestLambdaContext();
            Dictionary<string, string> body = new Dictionary<string, string>
            {
                { "message", "hello world" }
            };

            var ExpectedResponse = new APIGatewayProxyResponse
            {
                Body = JsonConvert.SerializeObject(body),
                StatusCode = 200,
                Headers = new Dictionary<string, string> { { "Content-Type", "application/json" } }
            };

            var function = new Function();
            response = function.FunctionHandler(request, context);

            Console.WriteLine("Lambda Response: \n" + response.Body);
            Console.WriteLine("Expected Response: \n" + ExpectedResponse.Body);

            Assert.Equal(ExpectedResponse.Body, response.Body);
            Assert.Equal(ExpectedResponse.Headers, response.Headers);
            Assert.Equal(ExpectedResponse.StatusCode, response.StatusCode);
    }
  }
}
