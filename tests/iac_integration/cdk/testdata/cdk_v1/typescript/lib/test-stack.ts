import * as path from 'path';
import * as cdk from '@aws-cdk/core';
import * as lambda from '@aws-cdk/aws-lambda';
import * as apigw from '@aws-cdk/aws-apigateway';
import { LambdaIntegration} from '@aws-cdk/aws-apigateway';
import { NodejsFunction } from '@aws-cdk/aws-lambda-nodejs';
import { GoFunction } from '@aws-cdk/aws-lambda-go';
import { PythonFunction, PythonLayerVersion } from '@aws-cdk/aws-lambda-python';
import {Role, ServicePrincipal, PolicyStatement} from '@aws-cdk/aws-iam';
import { CfnFunction, CfnLayerVersion } from '@aws-cdk/aws-lambda';
import {NestedStack1} from './nested-stack';
import * as logs from '@aws-cdk/aws-logs';

export class CDKSupportDemoRootStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Python Runtime
    // Layers
    const pythonLayerVersion = new PythonLayerVersion(this, 'PythonLayerVersion', {
      compatibleRuntimes: [
        lambda.Runtime.PYTHON_3_7,
        lambda.Runtime.PYTHON_3_8,
        lambda.Runtime.PYTHON_3_9,
      ],
      entry: '../../src/python/layers/PythonLayerVersion',
    });
    const layerVersion = new lambda.LayerVersion(this, 'LayerVersion', {
      compatibleRuntimes: [
        lambda.Runtime.PYTHON_3_7,
        lambda.Runtime.PYTHON_3_8,
        lambda.Runtime.PYTHON_3_9,
      ],
      code: lambda.Code.fromAsset('../../src/python/layers/LayerVersion'),
    });
    // add SAM metadata to build layer
    const cfnLayerVersion = layerVersion.node.defaultChild as CfnLayerVersion;
    cfnLayerVersion.addMetadata('BuildMethod', 'python3.7');

    // Lambda LayerVersion with bundled Asset that will be built by CDK
    const bundledLayerVersionPythonRuntime = new lambda.LayerVersion(this, 'BundledLayerVersionPythonRuntime', {
      compatibleRuntimes: [
        lambda.Runtime.PYTHON_3_7,
        lambda.Runtime.PYTHON_3_8,
        lambda.Runtime.PYTHON_3_9,
      ],
      code: lambda.Code.fromAsset('../../src/python/layers/BundledLayerVersion', {
        bundling: {
          command: [
            '/bin/sh',
            '-c',
            'rm -rf /tmp/asset-input && mkdir /tmp/asset-input && cp * /tmp/asset-input && cd /tmp/asset-input && pip install -r requirements.txt -t . && mkdir /asset-output/python && cp -R /tmp/asset-input/* /asset-output/python',
          ],
          image: lambda.Runtime.PYTHON_3_7.bundlingImage,
          user: 'root',
        }
      }),
    });

    // ZIP package type Functions
    // Functions Built by CDK - Runtime Functions Constructs
    const pythonFunction = new PythonFunction(this, 'PythonFunction', {
      entry: '../../src/python/PythonFunctionConstruct',
      index: 'app.py',
      handler: 'lambda_handler',
      runtime: lambda.Runtime.PYTHON_3_9,
      functionName: 'pythonFunc', // we need the name to use it in the API definition file
      logRetention: logs.RetentionDays.THREE_MONTHS,
      layers: [pythonLayerVersion, layerVersion],
      tracing: lambda.Tracing.ACTIVE,
    });

    // Normal Lambda Function Construct - Python Runtime
    const functionPythonRuntime = new lambda.Function(this, 'FunctionPythonRuntime', {
      runtime: lambda.Runtime.PYTHON_3_7,
      code: lambda.Code.fromAsset('../../src/python/FunctionConstruct'),
      handler: 'app.lambda_handler',
      layers: [pythonLayerVersion, layerVersion],
      tracing: lambda.Tracing.ACTIVE,
    });

    // Normal Lambda Function Construct - Python Runtime - with skip build metadata
    const preBuiltFunctionPythonRuntime = new lambda.Function(this, 'PreBuiltFunctionPythonRuntime', {
      runtime: lambda.Runtime.PYTHON_3_7,
      code: lambda.Code.fromAsset('../../src/python/BuiltFunctionConstruct'),
      handler: 'app.lambda_handler',
      layers: [pythonLayerVersion, layerVersion],
      tracing: lambda.Tracing.ACTIVE,
    });
    // add SkipBuild Metadata, so SAM will skip building this function
    const cfnPreBuiltFunctionPythonRuntime = preBuiltFunctionPythonRuntime.node.defaultChild as CfnFunction;
    cfnPreBuiltFunctionPythonRuntime.addMetadata('SkipBuild', true);

    // Normal Lambda Function with bundled Asset will be built by CDK
    const bundledFunctionPythonRuntime = new lambda.Function(this, 'BundledFunctionPythonRuntime', {
      runtime: lambda.Runtime.PYTHON_3_7,
      code: lambda.Code.fromAsset('../../src/python/BundledFunctionConstruct/', {
        bundling: {
          command: [
            '/bin/sh',
            '-c',
            'rm -rf /tmp/asset-input && mkdir /tmp/asset-input && cp * /tmp/asset-input && cd /tmp/asset-input && pip install -r requirements.txt -t . && cp -R /tmp/asset-input/* /asset-output',
          ],
          image: lambda.Runtime.PYTHON_3_7.bundlingImage,
          user: 'root',
        }
      }),
      handler: "app.lambda_handler",
      layers: [bundledLayerVersionPythonRuntime, pythonLayerVersion],
      timeout: cdk.Duration.seconds(120),
      tracing: lambda.Tracing.ACTIVE,
    });

    // NodeJs Runtime
    //Layers
    const layerVersionNodeJsRuntime = new lambda.LayerVersion(this, 'LayerVersionNodeJsRuntime', {
      compatibleRuntimes: [
        lambda.Runtime.NODEJS_14_X,
      ],
      code: lambda.Code.fromAsset('../../src/nodejs/layers/LayerVersion'),
    });
    // add SAM metadata to build layer
    const cfnLayerVersionNodeJsRuntime = layerVersionNodeJsRuntime.node.defaultChild as CfnLayerVersion;
    cfnLayerVersionNodeJsRuntime.addMetadata('BuildMethod', 'nodejs14.x');

    const nodejsFunction = new NodejsFunction(this, 'NodejsFunction', {
      entry: path.join(__dirname, '../../../src/nodejs/NodeJsFunctionConstruct/app.ts'),
      depsLockFilePath: path.join(__dirname, '../../../src/nodejs/NodeJsFunctionConstruct/package-lock.json'),
      bundling: {
        externalModules: ['/opt/nodejs/layer_version_dependency'],
      },
      handler: 'lambdaHandler',
      layers: [layerVersionNodeJsRuntime],
      tracing: lambda.Tracing.ACTIVE,
    });

    // Normal Lambda Function Construct - NodeJs Runtime
    const functionNodeJsRuntime = new lambda.Function(this, 'FunctionNodeJsRuntime', {
      runtime: lambda.Runtime.NODEJS_14_X,
      code: lambda.Code.fromAsset('../../src/nodejs/FunctionConstruct'),
      handler: 'app.lambdaHandler',
      layers: [layerVersionNodeJsRuntime],
      tracing: lambda.Tracing.ACTIVE,
    });

    // Normal Lambda Function Construct - NodeJs Runtime - with skip build metadata
    const preBuiltFunctionNodeJsRuntime = new lambda.Function(this, 'PreBuiltFunctionNodeJsRuntime', {
      runtime: lambda.Runtime.NODEJS_14_X,
      code: lambda.Code.fromAsset('../../src/nodejs/BuiltFunctionConstruct'),
      handler: 'app.lambdaHandler',
      layers: [layerVersionNodeJsRuntime],
      tracing: lambda.Tracing.ACTIVE,
    });
    // add SkipBuild Metadata, so SAM will skip building this function
    const cfnPreBuiltFunctionNodeJsRuntime = preBuiltFunctionNodeJsRuntime.node.defaultChild as CfnFunction;
    cfnPreBuiltFunctionNodeJsRuntime.addMetadata('SkipBuild', true);

    // Go Runtime

    const goFunction = new GoFunction(this, 'GoFunction', {
      entry: '../../src/go/GoFunctionConstruct',
      bundling: {
        forcedDockerBundling: true,
      },
    });

    // Normal Lambda Function Construct - Go Runtime
    const functionGoRuntime = new lambda.Function(this, 'FunctionGoRuntime', {
      runtime: lambda.Runtime.GO_1_X,
      code: lambda.Code.fromAsset('../../src/go/FunctionConstruct'),
      handler: 'FunctionConstruct',
    });

    // Image Package Type Functions

    // One way to define an Image Package Type Function
    const dockerImageFunction = new lambda.DockerImageFunction(this, "DockerImageFunction", {
      code: lambda.DockerImageCode.fromImageAsset('../../src/docker/DockerImageFunctionConstruct', {
        file: 'Dockerfile',
      }),
      tracing: lambda.Tracing.ACTIVE,
    });

    // another way
    const functionImageAsset = new lambda.Function(this, "FunctionImageAsset", {
      code: lambda.Code.fromAssetImage('../../src/docker/FunctionConstructWithImageAssetCode', {
        file: 'Dockerfile',
      }),
      handler: lambda.Handler.FROM_IMAGE,
      runtime: lambda.Runtime.FROM_IMAGE,
      tracing: lambda.Tracing.ACTIVE,
    });

    // both ways work when 'file' is a path via subfolders to the Dockerfile
    // this is useful when multiple docker images share some common code
    const dockerImageFunctionWithSharedCode = new lambda.DockerImageFunction(this, "DockerImageFunctionWithSharedCode", {
      code: lambda.DockerImageCode.fromImageAsset("../../src/docker/ImagesWithSharedCode", {
        file: "DockerImageFunctionWithSharedCode/Dockerfile",
      }),
      tracing: lambda.Tracing.ACTIVE,
    });

    // another way
    const functionImageAssetWithSharedCode = new lambda.Function(this, "FunctionImageAssetWithSharedCode", {
      code: lambda.Code.fromAssetImage("../../src/docker/ImagesWithSharedCode", {
        file: "FunctionImageAssetWithSharedCode/Dockerfile",
      }),
      handler: lambda.Handler.FROM_IMAGE,
      runtime: lambda.Runtime.FROM_IMAGE,
      tracing: lambda.Tracing.ACTIVE,
    });


    //Rest APIs

    // Spec Rest Api
    new apigw.SpecRestApi(this, 'SpecRestAPI', {
      apiDefinition: apigw.ApiDefinition.fromAsset('../../src/rest-api-definition.yaml'),
    });

    // Role to be used as credentials for the Spec rest APi
    // it is used inside the spec rest api definition file
    new Role(this, 'SpecRestApiRole', {
      assumedBy: new ServicePrincipal('apigateway.amazonaws.com'),
      roleName: 'SpecRestApiRole',
    }).addToPolicy(new PolicyStatement({
      actions: ['lambda:InvokeFunction'],
      resources: ['*'],
    }));

    // Rest Api
    const restApi = new apigw.RestApi(this, 'RestAPI', {});
    const normalRootResource = restApi.root.addResource('restapis')
      .addResource('normal');

    normalRootResource.addResource('pythonFunction')
      .addMethod('GET', new LambdaIntegration(pythonFunction));

    normalRootResource.addResource('functionPythonRuntime')
      .addMethod('GET', new LambdaIntegration(functionPythonRuntime));

    normalRootResource.addResource('preBuiltFunctionPythonRuntime')
      .addMethod('GET', new LambdaIntegration(preBuiltFunctionPythonRuntime));

    normalRootResource.addResource('bundledFunctionPythonRuntime')
      .addMethod('GET', new LambdaIntegration(bundledFunctionPythonRuntime));

    normalRootResource.addResource('nodejsFunction')
      .addMethod('GET', new LambdaIntegration(nodejsFunction));

    normalRootResource.addResource('functionNodeJsRuntime')
      .addMethod('GET', new LambdaIntegration(functionNodeJsRuntime));

    normalRootResource.addResource('preBuiltFunctionNodeJsRuntime')
      .addMethod('GET', new LambdaIntegration(preBuiltFunctionNodeJsRuntime));

    normalRootResource.addResource('goFunction')
      .addMethod('GET', new LambdaIntegration(goFunction));

    normalRootResource.addResource('functionGoRuntime')
      .addMethod('GET', new LambdaIntegration(functionGoRuntime));

    normalRootResource.addResource('dockerImageFunction')
      .addMethod('GET', new LambdaIntegration(dockerImageFunction));

    normalRootResource.addResource('functionImageAsset')
      .addMethod('GET', new LambdaIntegration(functionImageAsset));

    normalRootResource.addResource('dockerImageFunctionWithSharedCode')
      .addMethod('GET', new LambdaIntegration(dockerImageFunctionWithSharedCode));

    normalRootResource.addResource('functionImageAssetWithSharedCode')
      .addMethod('GET', new LambdaIntegration(functionImageAssetWithSharedCode));
    
    // Nested Stack
    new NestedStack1(this, 'NestedStack' ,{});
  }
}
