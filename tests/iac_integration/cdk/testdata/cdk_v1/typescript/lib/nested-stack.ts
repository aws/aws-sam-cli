import * as cdk from '@aws-cdk/core';
import * as lambda from '@aws-cdk/aws-lambda';
import { HttpApi, HttpMethod } from '@aws-cdk/aws-apigatewayv2';
import { HttpLambdaIntegration } from '@aws-cdk/aws-apigatewayv2-integrations';
import { PythonFunction, PythonLayerVersion } from '@aws-cdk/aws-lambda-python';
import {CfnLayerVersion} from "@aws-cdk/aws-lambda";

export class NestedStack1 extends cdk.NestedStack {

    constructor(scope: cdk.Construct, id: string, props?: cdk.NestedStackProps) {
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

        // ZIP package type Functions
        // Functions Built by CDK - Runtime Functions Constructs
        const nestedPythonFunction = new PythonFunction(this, 'NestedPythonFunction', {
          entry: '../../src/python/NestedPythonFunctionConstruct',
          index: 'app.py',
          handler: 'lambda_handler',
          runtime: lambda.Runtime.PYTHON_3_9,
          layers: [pythonLayerVersion, layerVersion],
          tracing: lambda.Tracing.ACTIVE,
        });

        const httpApi = new HttpApi(this, 'httpAPi', {
        });

        httpApi.addRoutes({
            path: '/httpapis/nestedPythonFunction',
            methods: [HttpMethod.GET],
            integration: new HttpLambdaIntegration('httpApiRandomNameIntegration',
                nestedPythonFunction, {}
            ),
        });

    }
}