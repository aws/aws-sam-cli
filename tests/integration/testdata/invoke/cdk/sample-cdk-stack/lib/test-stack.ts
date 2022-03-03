import * as cdk from '@aws-cdk/core';
import * as lambda from '@aws-cdk/aws-lambda';
import * as path from 'path';
import * as apigw from '@aws-cdk/aws-apigateway';
import { LambdaIntegration, RestApi } from '@aws-cdk/aws-apigateway';
import { App } from '@aws-cdk/core';
import { NodejsFunction } from '@aws-cdk/aws-lambda-nodejs'
import { GoFunction } from '@aws-cdk/aws-lambda-go'
import { PythonFunction } from '@aws-cdk/aws-lambda-python'
import { HttpApi, HttpMethod } from '@aws-cdk/aws-apigatewayv2';
import { LambdaProxyIntegration } from '@aws-cdk/aws-apigatewayv2-integrations';

export class TestStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const dockerfilePath = 'Dockerfile';
    const dockerBuildTarget = 'stage';
    const dockerBuildArgs = { arg1: 'val1', arg2: 'val2' };

    new PythonFunction(this, 'PythonFunction', {
      entry: './my_function', // required
      index: 'app.py', // optional, defaults to 'index.py'
      handler: 'lambda_handler', // optional, defaults to 'handler'
      runtime: lambda.Runtime.PYTHON_3_9, // optional, defaults to lambda.Runtime.PYTHON_3_7
    });
    
    new GoFunction(this, 'GoFunction', {
      runtime: lambda.Runtime.GO_1_X,
      entry: './go_handler',
      bundling: {
        goBuildFlags: ['-ldflags "-s -w"'],
      },
    });
    
    new NodejsFunction(this, 'NodejsFunction', {
      entry: './src/lambda.js',
      handler: 'handler',
    })

    new lambda.Function(this, 'Func', {
      code: lambda.Code.fromAssetImage(path.join(__dirname, "..", 'docker_lambda_code'), {
        file: dockerfilePath,
        target: dockerBuildTarget,
        buildArgs: dockerBuildArgs,
      }),
      handler: lambda.Handler.FROM_IMAGE,
      runtime: lambda.Runtime.FROM_IMAGE,
    });

    new lambda.DockerImageFunction(this, "DockerFunc", {
      code: lambda.DockerImageCode.fromImageAsset(path.join(__dirname, "..", 'docker_lambda_code'), {
        file: dockerfilePath,
        target: dockerBuildTarget,
        buildArgs: dockerBuildArgs,
      })
    });

    const layer = new lambda.LayerVersion(this, 'hello-layer', {
      compatibleRuntimes: [
        lambda.Runtime.NODEJS_12_X,
        lambda.Runtime.NODEJS_14_X,
      ],
      code: lambda.Code.fromAsset('layers/hello-layer'),
    });

    new lambda.Function(this, 'Fn', {
      runtime: lambda.Runtime.NODEJS_12_X,
      code: lambda.Code.fromAsset('./src'),
      handler: 'lambda.handler',
      layers: [layer],
    });

    // const api = new apigw.RestApi(this, 'api');

    const assetApiDefinition = apigw.ApiDefinition.fromAsset('sample-definition.yaml');
    const api = new apigw.SpecRestApi(this, 'API', {
      apiDefinition: assetApiDefinition,
    });

    const newLambda = new lambda.Function(this, 'MyFunction', {
      functionName: "ExampleFunction",
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'app.lambda_handler',
      code: lambda.Code.fromAsset('./my_function'),
    });

    new lambda.Function(this, 'FunctionBundledAssets', {
      code: lambda.Code.fromAsset('./my_function', {
        bundling: {
          image: lambda.Runtime.PYTHON_3_9.bundlingImage,
          command: [
            'bash', '-c',
            'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output'
          ],
        },
      }),
      runtime: lambda.Runtime.PYTHON_3_9,
      handler: 'app.lambda_handler',
    });

    const resource = api.root.addResource('v1');
    resource.addMethod('GET', new LambdaIntegration(newLambda));

    const second_resource = api.root.addResource('anyandall');
    second_resource.addMethod('ANY', new LambdaIntegration(newLambda));

    const third_resource = api.root.addResource('proxypath');
    const proxy = third_resource.addResource('{proxy+}');
    proxy.addMethod('GET', new LambdaIntegration(newLambda));

    const httpApi = new HttpApi(this, 'http-api-example', {
      description: 'HTTP API example',
    });

    const lambdaFunc = new lambda.Function(this, 'lambdaFunc', {
      runtime: lambda.Runtime.NODEJS_14_X,
      handler: 'lambda.handler',
      code: lambda.Code.fromAsset('./src'),
    });

    httpApi.addRoutes({
      path: '/get-info',
      methods: [HttpMethod.GET],
      integration: new LambdaProxyIntegration({
        handler: lambdaFunc,
      }),
    });

    httpApi.addRoutes({
      path: '/anyandall',
      methods: [HttpMethod.ANY],
      integration: new LambdaProxyIntegration({
        handler: lambdaFunc,
      }),
    });

    httpApi.addRoutes({
      path: '/proxypath/{proxy+}',
      methods: [HttpMethod.GET],
      integration: new LambdaProxyIntegration({
        handler: lambdaFunc,
      }),
    });
    
  }
}

const app = new App();
new TestStack(app, 'Stack');
app.synth();
