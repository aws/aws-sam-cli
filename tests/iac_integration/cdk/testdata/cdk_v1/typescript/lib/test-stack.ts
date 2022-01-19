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
import { AwsCliLayer } from '@aws-cdk/lambda-layer-awscli';
import { KubectlLayer } from '@aws-cdk/lambda-layer-kubectl';
import { NodeProxyAgentLayer }  from '@aws-cdk/lambda-layer-node-proxy-agent';

export class CDKSupportDemoRootStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Shared Layers
    // https://docs.aws.amazon.com/cdk/api/v1/docs/@aws-cdk_lambda-layer-awscli.AwsCliLayer.html
    const awsCliLayer = new AwsCliLayer(this, 'AwsCliLayer');
    // https://docs.aws.amazon.com/cdk/api/v1/docs/@aws-cdk_lambda-layer-kubectl.KubectlLayer.html
    const kubectlLayer = new KubectlLayer(this, 'KubectlLayer');
    const nodeProxyAgentLayer = new NodeProxyAgentLayer(this, 'NodeProxyAgentLayer');

    // Python Runtime
    // Layers
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda-python.PythonLayerVersion.html
    const pythonLayerVersion = new PythonLayerVersion(this, 'PythonLayerVersion', {
      compatibleRuntimes: [
        lambda.Runtime.PYTHON_3_7,
        lambda.Runtime.PYTHON_3_8,
        lambda.Runtime.PYTHON_3_9,
      ],
      entry: '../../src/python/layers/PythonLayerVersion',
    });
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda.LayerVersion.html
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

    // ZIP package type Functions
    // Functions Built by CDK - Runtime Functions Constructs
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda-python.PythonFunction.html
    const pythonFunction = new PythonFunction(this, 'PythonFunction', {
      entry: '../../src/python/PythonFunctionConstruct',
      index: 'app.py',
      handler: 'lambda_handler',
      runtime: lambda.Runtime.PYTHON_3_9,
      functionName: 'pythonFunc', // we need the name to use it in the API definition file
      logRetention: logs.RetentionDays.THREE_MONTHS,
      layers: [pythonLayerVersion, layerVersion, awsCliLayer, kubectlLayer, nodeProxyAgentLayer],
      tracing: lambda.Tracing.ACTIVE,
    });

    // Normal Lambda Function Construct - Python Runtime
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda.Function.html
    const functionPythonRuntime = new lambda.Function(this, 'FunctionPythonRuntime', {
      runtime: lambda.Runtime.PYTHON_3_7,
      code: lambda.Code.fromAsset('../../src/python/FunctionConstruct'),
      handler: 'app.lambda_handler',
      layers: [pythonLayerVersion, layerVersion, awsCliLayer, kubectlLayer, nodeProxyAgentLayer],
      tracing: lambda.Tracing.ACTIVE,
    });

    // Normal Lambda Function Construct - Python Runtime - with skip build metadata
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda.Function.html
    const preBuiltFunctionPythonRuntime = new lambda.Function(this, 'PreBuiltFunctionPythonRuntime', {
      runtime: lambda.Runtime.PYTHON_3_7,
      code: lambda.Code.fromAsset('../../src/python/BuiltFunctionConstruct'),
      handler: 'app.lambda_handler',
      layers: [pythonLayerVersion, layerVersion, awsCliLayer, kubectlLayer, nodeProxyAgentLayer],
      tracing: lambda.Tracing.ACTIVE,
    });
    // add SkipBuild Metadata, so SAM will skip building this function
    const cfnPreBuiltFunctionPythonRuntime = preBuiltFunctionPythonRuntime.node.defaultChild as CfnFunction;
    cfnPreBuiltFunctionPythonRuntime.addMetadata('SkipBuild', true);

    // NodeJs Runtime
    //Layers
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda.LayerVersion.html
    const layerVersionNodeJsRuntime = new lambda.LayerVersion(this, 'LayerVersionNodeJsRuntime', {
      compatibleRuntimes: [
        lambda.Runtime.NODEJS_14_X,
      ],
      code: lambda.Code.fromAsset('../../src/nodejs/layers/LayerVersion'),
    });
    // add SAM metadata to build layer
    const cfnLayerVersionNodeJsRuntime = layerVersionNodeJsRuntime.node.defaultChild as CfnLayerVersion;
    cfnLayerVersionNodeJsRuntime.addMetadata('BuildMethod', 'nodejs14.x');

    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda-nodejs.NodejsFunction.html
    const nodejsFunction = new NodejsFunction(this, 'NodejsFunction', {
      entry: path.join(__dirname, '../../../src/nodejs/NodeJsFunctionConstruct/app.ts'),
      depsLockFilePath: path.join(__dirname, '../../../src/nodejs/NodeJsFunctionConstruct/package-lock.json'),
      bundling: {
        externalModules: ['/opt/nodejs/layer_version_dependency'],
      },
      handler: 'lambdaHandler',
      layers: [layerVersionNodeJsRuntime, awsCliLayer, kubectlLayer, nodeProxyAgentLayer],
      tracing: lambda.Tracing.ACTIVE,
    });

    // Normal Lambda Function Construct - NodeJs Runtime
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda.Function.html
    const functionNodeJsRuntime = new lambda.Function(this, 'FunctionNodeJsRuntime', {
      runtime: lambda.Runtime.NODEJS_14_X,
      code: lambda.Code.fromAsset('../../src/nodejs/FunctionConstruct'),
      handler: 'app.lambdaHandler',
      layers: [layerVersionNodeJsRuntime, awsCliLayer, kubectlLayer, nodeProxyAgentLayer],
      tracing: lambda.Tracing.ACTIVE,
    });

    // Normal Lambda Function Construct - NodeJs Runtime - with skip build metadata
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda.Function.html
    const preBuiltFunctionNodeJsRuntime = new lambda.Function(this, 'PreBuiltFunctionNodeJsRuntime', {
      runtime: lambda.Runtime.NODEJS_14_X,
      code: lambda.Code.fromAsset('../../src/nodejs/BuiltFunctionConstruct'),
      handler: 'app.lambdaHandler',
      layers: [layerVersionNodeJsRuntime, awsCliLayer, kubectlLayer, nodeProxyAgentLayer],
      tracing: lambda.Tracing.ACTIVE,
    });
    // add SkipBuild Metadata, so SAM will skip building this function
    const cfnPreBuiltFunctionNodeJsRuntime = preBuiltFunctionNodeJsRuntime.node.defaultChild as CfnFunction;
    cfnPreBuiltFunctionNodeJsRuntime.addMetadata('SkipBuild', true);

    // Java Runtime
    //Layers
    // Lambda LayerVersion with bundled Asset that will be built by CDK
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda.LayerVersion.html
    const bundledLayerVersionJavaRuntime = new lambda.LayerVersion(this, 'BundledLayerVersionJavaRuntime', {
      compatibleRuntimes: [
        lambda.Runtime.JAVA_8,
      ],
      code: lambda.Code.fromAsset('../../src/java/layers/BundledLayerVersion', {
        bundling: {
          command: [
            '/bin/sh',
            '-c',
            'mvn clean install && mkdir /asset-output/java && mkdir /asset-output/java/lib && cp target/LayerVersionDependency.jar /asset-output/java/lib'
          ],
          image: lambda.Runtime.JAVA_11.bundlingImage,
          volumes: [
            {
              hostPath: require('os').homedir() + '/.m2',
              containerPath: '/root/.m2/',
            }
          ],
          user: 'root',
        }
      }),
    });

    // Normal Lambda Function Construct - Java Runtime
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda.Function.html
    const functionJavaRuntime = new lambda.Function(this, 'FunctionJavaRuntime', {
      runtime: lambda.Runtime.JAVA_8,
      code: lambda.Code.fromAsset('../../src/java/FunctionConstruct'),
      handler: 'helloworld.App',
      layers: [bundledLayerVersionJavaRuntime, awsCliLayer, kubectlLayer, nodeProxyAgentLayer],
      timeout: cdk.Duration.seconds(120),
      tracing: lambda.Tracing.ACTIVE,
    });

    // Normal Lambda Function with bundled Asset will be built by CDK
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_core.BundlingOptions.html
    const bundledFunctionJavaRuntime = new lambda.Function(this, 'BundledFunctionJavaRuntime', {
      runtime: lambda.Runtime.JAVA_8,
      code: lambda.Code.fromAsset('../../src/java/BundledFunctionConstruct/', {
        bundling: {
          command: [
            '/bin/sh',
            '-c',
            'mvn clean install && cp target/BundledHelloWorld.jar /asset-output/'
          ],
          image: lambda.Runtime.JAVA_11.bundlingImage,
          volumes: [
            {
              hostPath: require('os').homedir() + '/.m2',
              containerPath: '/root/.m2/',
            }
          ],
          user: 'root',
          outputType: cdk.BundlingOutput.ARCHIVED,
        }
      }),
      handler: "bundledhelloworld.App",
      layers: [bundledLayerVersionJavaRuntime, awsCliLayer, kubectlLayer, nodeProxyAgentLayer],
      timeout: cdk.Duration.seconds(120),
      tracing: lambda.Tracing.ACTIVE,
    });

    // PreBuilt Function - Customer built this function outside CDK
    // Normal Lambda function construct, so CDK will not build it
    const preBuiltFunctionJavaRuntime = new lambda.Function(this, 'PreBuiltFunctionJavaRuntime', {
      runtime: lambda.Runtime.JAVA_8,
      code: lambda.Code.fromAsset('../../src/java/BuiltFunctionConstruct/target/PreBuiltHelloWorld.jar'),
      handler: "prebuilthelloworld.App",
      layers: [bundledLayerVersionJavaRuntime, awsCliLayer, kubectlLayer, nodeProxyAgentLayer],
      timeout: cdk.Duration.seconds(120),
      tracing: lambda.Tracing.ACTIVE,
    });
    // add SkipBuild Metadata, so SAM will skip building this function
    const cfnpreBuiltFunctionJavaRuntime = preBuiltFunctionJavaRuntime.node.defaultChild as CfnFunction;
    cfnpreBuiltFunctionJavaRuntime.addMetadata('SkipBuild', true);

    // Go Runtime

    // https://docs.aws.amazon.com/cdk/api/v1/docs/@aws-cdk_aws-lambda-go.GoFunction.html
    const goFunction = new GoFunction(this, 'GoFunction', {
      entry: '../../src/go/GoFunctionConstruct',
      bundling: {
        forcedDockerBundling: true,
      },
    });

    // Normal Lambda Function Construct - Go Runtime
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda.Function.html
    const functionGoRuntime = new lambda.Function(this, 'FunctionGoRuntime', {
      runtime: lambda.Runtime.GO_1_X,
      code: lambda.Code.fromAsset('../../src/go/FunctionConstruct'),
      handler: 'FunctionConstruct',
    });

    // Image Package Type Functions

    // One way to define an Image Package Type Function
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda.DockerImageFunction.html
    const dockerImageFunction = new lambda.DockerImageFunction(this, "DockerImageFunction", {
      code: lambda.DockerImageCode.fromImageAsset('../../src/docker/DockerImageFunctionConstruct', {
        file: 'Dockerfile',
      }),
      tracing: lambda.Tracing.ACTIVE,
    });

    // another way
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-lambda.Code.html#static-fromwbrassetwbrimagedirectory-props
    const functionImageAsset = new lambda.Function(this, "FunctionImageAsset", {
      code: lambda.Code.fromAssetImage('../../src/docker/FunctionConstructWithImageAssetCode', {
        file: 'Dockerfile',
      }),
      handler: lambda.Handler.FROM_IMAGE,
      runtime: lambda.Runtime.FROM_IMAGE,
      tracing: lambda.Tracing.ACTIVE,
    });


    //Rest APIs

    // Spec Rest Api
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-apigateway.SpecRestApi.html
    new apigw.SpecRestApi(this, 'SpecRestAPI', {
      apiDefinition: apigw.ApiDefinition.fromAsset('../../src/rest-api-definition.yaml'),
    });

    // Role to be used as credentials for the Spec rest APi
    // it is used inside the spec rest api definition file
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-iam.Role.html
    new Role(this, 'SpecRestApiRole', {
      assumedBy: new ServicePrincipal('apigateway.amazonaws.com'),
      roleName: 'SpecRestApiRole',
    }).addToPolicy(new PolicyStatement({
      actions: ['lambda:InvokeFunction'],
      resources: ['*'],
    }));

    // Rest Api
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_aws-apigateway.RestApi.html
    const restApi = new apigw.RestApi(this, 'RestAPI', {});
    const normalRootResource = restApi.root.addResource('restapis')
      .addResource('normal');

    normalRootResource.addResource('pythonFunction')
      .addMethod('GET', new LambdaIntegration(pythonFunction));

    normalRootResource.addResource('functionPythonRuntime')
      .addMethod('GET', new LambdaIntegration(functionPythonRuntime));

    normalRootResource.addResource('preBuiltFunctionPythonRuntime')
      .addMethod('GET', new LambdaIntegration(preBuiltFunctionPythonRuntime));

    normalRootResource.addResource('nodejsFunction')
      .addMethod('GET', new LambdaIntegration(nodejsFunction));

    normalRootResource.addResource('functionNodeJsRuntime')
      .addMethod('GET', new LambdaIntegration(functionNodeJsRuntime));

    normalRootResource.addResource('preBuiltFunctionNodeJsRuntime')
      .addMethod('GET', new LambdaIntegration(preBuiltFunctionNodeJsRuntime));

    normalRootResource.addResource('functionJavaRuntime')
      .addMethod('GET', new LambdaIntegration(functionJavaRuntime));

    normalRootResource.addResource('bundledFunctionJavaRuntime')
      .addMethod('GET', new LambdaIntegration(bundledFunctionJavaRuntime));

    normalRootResource.addResource('preBuiltFunctionJavaRuntime')
      .addMethod('GET', new LambdaIntegration(preBuiltFunctionJavaRuntime));

    normalRootResource.addResource('goFunction')
      .addMethod('GET', new LambdaIntegration(goFunction));

    normalRootResource.addResource('functionGoRuntime')
      .addMethod('GET', new LambdaIntegration(functionGoRuntime));

    normalRootResource.addResource('dockerImageFunction')
      .addMethod('GET', new LambdaIntegration(dockerImageFunction));

    normalRootResource.addResource('functionImageAsset')
      .addMethod('GET', new LambdaIntegration(functionImageAsset));
    
    // Nested Stack
    // https://docs.aws.amazon.com/cdk/api/latest/docs/@aws-cdk_core.NestedStack.html
    new NestedStack1(this, 'NestedStack' ,{});
  }
}
