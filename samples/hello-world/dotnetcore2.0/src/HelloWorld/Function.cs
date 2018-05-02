using Amazon.Lambda.Core;
using Amazon.Lambda.Serialization.Json;

// Assembly attribute to enable the Lambda function's JSON input to be converted into a .NET class.
[assembly: LambdaSerializer(typeof(JsonSerializer))]

namespace HelloWorld
{
    public class Function
    {
        public void Handler(Event @event, ILambdaContext context)
        {
            context.Logger.Log($"The name is '{@event.Name}'.");
            context.Logger.Log($"The age is '{@event.Age}'.");
        }
    }
}