import * as cdk from '@aws-cdk/core';
import * as lambda from '@aws-cdk/aws-lambda';
import * as apigateway from '@aws-cdk/aws-apigateway';
import * as path from 'path';

export class CdkExampleRestApiGatewayStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // The code that defines your stack goes here
    const backend = new lambda.Function(this, 'APIGWLambdaFunction', {
      runtime: lambda.Runtime.NODEJS_12_X,
      handler: 'app.lambdaHandler',
      code: lambda.Code.fromAsset(path.join(__dirname, '..', 'hello-world')),
    });
    
    const api = new apigateway.LambdaRestApi(this, 'myapi', {
      handler: backend,
      proxy: false
    });

    const hello = api.root.addResource('hello');
    hello.addMethod('GET');
  }
}
