package com.myorg;

import software.amazon.awscdk.*;
import software.amazon.awscdk.services.apigateway.Resource;
import software.amazon.awscdk.services.apigateway.*;
import software.amazon.awscdk.services.iam.PolicyStatement;
import software.amazon.awscdk.services.iam.Role;
import software.amazon.awscdk.services.iam.ServicePrincipal;
import software.amazon.awscdk.services.lambda.Runtime;
import software.amazon.awscdk.services.lambda.*;
import software.amazon.awscdk.services.lambda.go.alpha.GoFunction;
import software.amazon.awscdk.services.lambda.nodejs.NodejsFunction;
import software.amazon.awscdk.services.lambda.python.alpha.PythonFunction;
import software.amazon.awscdk.services.lambda.python.alpha.PythonLayerVersion;
import software.amazon.awscdk.services.logs.RetentionDays;
import software.amazon.awscdk.services.s3.assets.AssetOptions;
import software.constructs.Construct;
import com.myorg.NestedStack1;

import java.util.Arrays;

public class JavaStack extends Stack {
    public JavaStack(final Construct scope, final String id) {
        this(scope, id, null);
    }

    public JavaStack(final Construct scope, final String id, final StackProps props) {
        super(scope, id, props);

        // Python Runtime
        // Layers
        PythonLayerVersion pythonLayerVersion = PythonLayerVersion.Builder
                .create(this, "PythonLayerVersion")
                .compatibleRuntimes(Arrays.asList(Runtime.PYTHON_3_7, Runtime.PYTHON_3_8,
                        Runtime.PYTHON_3_9))
                .entry("../../src/python/layers/PythonLayerVersion")
                .build();

        LayerVersion layerVersion = LayerVersion.Builder
                .create(this, "LayerVersion")
                .compatibleRuntimes(Arrays.asList(Runtime.PYTHON_3_7, Runtime.PYTHON_3_8,
                        Runtime.PYTHON_3_9))
                .code(Code.fromAsset("../../src/python/layers/LayerVersion"))
                .build();
        // add SAM metadata to build layer
        CfnLayerVersion cfnLayerVersion = (CfnLayerVersion) layerVersion.getNode().getDefaultChild();
        cfnLayerVersion.addMetadata("BuildMethod", "python3.7");

        // Lambda LayerVersion with bundled Asset that will be built by CDK
        LayerVersion bundledLayerVersionPythonRuntime = LayerVersion.Builder
                .create(this, "BundledLayerVersionPythonRuntime")
                .compatibleRuntimes(Arrays.asList(Runtime.PYTHON_3_7, Runtime.PYTHON_3_8,
                        Runtime.PYTHON_3_9))
                .code(Code.fromAsset("../../src/python/layers/BundledLayerVersion",
                        AssetOptions.builder().bundling(
                                BundlingOptions.builder()
                                        .image(Runtime.PYTHON_3_7.getBundlingImage())
                                        .command(Arrays.asList(
                                                "/bin/sh",
                                                "-c",
                                                "rm -rf /tmp/asset-input && mkdir /tmp/asset-input && cp * /tmp/asset-input && cd /tmp/asset-input" +
                                                        " && pip install -r requirements.txt -t . && mkdir /asset-output/python && " +
                                                        "cp -R /tmp/asset-input/* /asset-output/python"
                                        )).build()
                        ).build()
                )).build();

        // ZIP package type Functions
        // Functions Built by CDK - Runtime Functions Constructs
        PythonFunction pythonFunction = PythonFunction.Builder
                .create(this, "PythonFunction")
                .entry("../../src/python/PythonFunctionConstruct")
                .index("app.py")
                .handler("lambda_handler")
                .runtime(Runtime.PYTHON_3_9)
                .functionName("pythonFunc") // we need the name to use it in the API definition file
                .logRetention(RetentionDays.THREE_MONTHS)
                .layers(Arrays.asList(pythonLayerVersion, layerVersion))
                .tracing(Tracing.ACTIVE)
                .build();

        // Normal Lambda Function Construct - Python Runtime
        Function functionPythonRuntime = Function.Builder.create(this, "FunctionPythonRuntime")
                .runtime(Runtime.PYTHON_3_7)
                .code(Code.fromAsset("../../src/python/FunctionConstruct"))
                .handler("app.lambda_handler")
                .layers(Arrays.asList(pythonLayerVersion, layerVersion))
                .tracing(Tracing.ACTIVE)
                .build();

        // Normal Lambda Function Construct - Python Runtime - with skip build metadata
        Function preBuiltFunctionPythonRuntime = Function.Builder.create(this, "PreBuiltFunctionPythonRuntime")
                .runtime(Runtime.PYTHON_3_7)
                .code(Code.fromAsset("../../src/python/BuiltFunctionConstruct"))
                .handler("app.lambda_handler")
                .layers(Arrays.asList(pythonLayerVersion, layerVersion))
                .tracing(Tracing.ACTIVE)
                .build();
        // add SkipBuild Metadata, so SAM will skip building this function
        CfnFunction cfnPreBuiltFunctionPythonRuntime = (CfnFunction) preBuiltFunctionPythonRuntime.getNode()
                .getDefaultChild();
        cfnPreBuiltFunctionPythonRuntime.addMetadata("SkipBuild", true);

        // Normal Lambda Function with bundled Asset will be built by CDK
        Function bundledFunctionPythonRuntime = Function.Builder.create(this, "BundledFunctionPythonRuntime")
                .runtime(Runtime.PYTHON_3_7)
                .code(Code.fromAsset("../../src/python/BundledFunctionConstruct/",
                        AssetOptions.builder().bundling(
                                BundlingOptions.builder()
                                        .command(Arrays.asList("/bin/sh", "-c", "rm -rf /tmp/asset-input && mkdir /tmp/asset-input && cp * /tmp/asset-input && cd /tmp/asset-input && pip install -r requirements.txt -t . && cp -R /tmp/asset-input/* /asset-output"))
                                        .image(Runtime.PYTHON_3_7.getBundlingImage())
                                        .build()
                        ).build()
                ))
                .handler("app.lambda_handler")
                .layers(Arrays.asList(bundledLayerVersionPythonRuntime, pythonLayerVersion))
                .timeout(Duration.seconds(120))
                .tracing(Tracing.ACTIVE)
                .build();

        // NodeJs Runtime
        //Layers
        LayerVersion layerVersionNodeJsRuntime = LayerVersion.Builder.create(this, "LayerVersionNodeJsRuntime")
                .compatibleRuntimes(Arrays.asList(Runtime.NODEJS_14_X))
                .code(Code.fromAsset("../../src/nodejs/layers/LayerVersion"))
                .build();
        // add SAM metadata to build layer
        CfnLayerVersion cfnLayerVersionNodeJsRuntime = (CfnLayerVersion) layerVersionNodeJsRuntime.getNode().getDefaultChild();
        cfnLayerVersionNodeJsRuntime.addMetadata("BuildMethod", "nodejs14.x");

        NodejsFunction nodejsFunction = NodejsFunction.Builder.create(this, "NodejsFunction")
                .entry("../../src/nodejs/NodeJsFunctionConstruct/app.ts")
                .depsLockFilePath("../../src/nodejs/NodeJsFunctionConstruct/package-lock.json")
                .handler("lambdaHandler")
                .layers(Arrays.asList(layerVersionNodeJsRuntime))
                .tracing(Tracing.ACTIVE)
                .bundling(software.amazon.awscdk.services.lambda.nodejs.BundlingOptions.builder()
                        .externalModules(
                                Arrays.asList("/opt/nodejs/layer_version_dependency")
                        ).build()
                ).build();

        // Normal Lambda Function Construct - NodeJs Runtime
        Function functionNodeJsRuntime = Function.Builder.create(this, "FunctionNodeJsRuntime")
                .runtime(Runtime.NODEJS_14_X)
                .code(Code.fromAsset("../../src/nodejs/FunctionConstruct"))
                .handler("app.lambdaHandler")
                .layers(Arrays.asList(layerVersionNodeJsRuntime))
                .tracing(Tracing.ACTIVE)
                .build();

        // Normal Lambda Function Construct - NodeJs Runtime - with skip build metadata
        Function preBuiltFunctionNodeJsRuntime = Function.Builder.create(this, "PreBuiltFunctionNodeJsRuntime")
                .runtime(Runtime.NODEJS_14_X)
                .code(Code.fromAsset("../../src/nodejs/BuiltFunctionConstruct"))
                .handler("app.lambdaHandler")
                .layers(Arrays.asList(layerVersionNodeJsRuntime))
                .tracing(Tracing.ACTIVE)
                .build();
        // add SkipBuild Metadata, so SAM will skip building this function
        CfnFunction cfnPreBuiltFunctionNodeJsRuntime = (CfnFunction) preBuiltFunctionNodeJsRuntime.getNode().getDefaultChild();
        cfnPreBuiltFunctionNodeJsRuntime.addMetadata("SkipBuild", true);

        // Go Runtime
        GoFunction goFunction = GoFunction.Builder.create(this, "GoFunction")
                .entry("../../src/go/GoFunctionConstruct")
                .bundling(software.amazon.awscdk.services.lambda.go.alpha.BundlingOptions.builder()
                        .forcedDockerBundling(true).build())
                .build();

        // Normal Lambda Function Construct - Go Runtime
        Function functionGoRuntime = Function.Builder.create(this, "FunctionGoRuntime")
                .runtime(Runtime.GO_1_X)
                .code(Code.fromAsset("../../src/go/FunctionConstruct"))
                .handler("FunctionConstruct")
                .build();

        // Image Package Type Functions
        // One way to define an Image Package Type Function
        DockerImageFunction dockerImageFunction = DockerImageFunction.Builder.create(this, "DockerImageFunction")
                .code(DockerImageCode.fromImageAsset("../../src/docker/DockerImageFunctionConstruct",
                        AssetImageCodeProps.builder().file("Dockerfile").build()
                        )
                ).tracing(Tracing.ACTIVE)
                .build();

        // another way
        Function functionImageAsset = Function.Builder.create(this, "FunctionImageAsset")
                .code(Code.fromAssetImage("../../src/docker/FunctionConstructWithImageAssetCode",
                        AssetImageCodeProps.builder().file("Dockerfile").build()))
                .handler(Handler.FROM_IMAGE)
                .runtime(Runtime.FROM_IMAGE)
                .tracing(Tracing.ACTIVE)
                .build();

        // both ways work when 'file' is a path via subfolders to the Dockerfile
        // this is useful when multiple docker images share some common code
        DockerImageFunction dockerImageFunctionWithSharedCode = DockerImageFunction.Builder.create(this, "DockerImageFunctionWithSharedCode")
                .code(DockerImageCode.fromImageAsset("../../src/docker/ImagesWithSharedCode",
                        AssetImageCodeProps.builder().file("DockerImageFunctionWithSharedCode/Dockerfile").build()
                        )
                ).tracing(Tracing.ACTIVE)
                .build();

        Function functionImageAssetWithSharedCode = Function.Builder.create(this, "FunctionImageAssetWithSharedCode")
                .code(Code.fromAssetImage("../../src/docker/ImagesWithSharedCode",
                        AssetImageCodeProps.builder().file("FunctionImageAssetWithSharedCode/Dockerfile").build()))
                .handler(Handler.FROM_IMAGE)
                .runtime(Runtime.FROM_IMAGE)
                .tracing(Tracing.ACTIVE)
                .build();

        //Rest APIs

        // Spec Rest Api
        SpecRestApi.Builder.create(this, "SpecRestAPI")
                .apiDefinition(ApiDefinition.fromAsset("../../src/rest-api-definition.yaml"))
                .build();

        // Role to be used as credentials for the Spec rest APi
        // it is used inside the spec rest api definition file
        Role.Builder.create(this, "SpecRestApiRole")
                .assumedBy(new ServicePrincipal("apigateway.amazonaws.com"))
                .roleName("SpecRestApiRole")
                .build()
                .addToPolicy(
                        PolicyStatement.Builder.create()
                                .actions(Arrays.asList("lambda:InvokeFunction"))
                                .resources(Arrays.asList("*"))
                                .build()
                );

        // Rest Api
        RestApi restApi = new RestApi(this, "RestAPI");
        Resource normalRootResource = restApi.getRoot().addResource("restapis")
                .addResource("normal");

        normalRootResource.addResource("pythonFunction")
                .addMethod("GET", new LambdaIntegration(pythonFunction));
        normalRootResource.addResource("functionPythonRuntime")
                .addMethod("GET", new LambdaIntegration(functionPythonRuntime));
        normalRootResource.addResource("preBuiltFunctionPythonRuntime")
                .addMethod("GET", new LambdaIntegration(preBuiltFunctionPythonRuntime));
        normalRootResource.addResource("bundledFunctionPythonRuntime")
                .addMethod("GET", new LambdaIntegration(bundledFunctionPythonRuntime));
        normalRootResource.addResource("nodejsFunction")
                .addMethod("GET", new LambdaIntegration(nodejsFunction));
        normalRootResource.addResource("functionNodeJsRuntime")
                .addMethod("GET", new LambdaIntegration(functionNodeJsRuntime));
        normalRootResource.addResource("preBuiltFunctionNodeJsRuntime")
                .addMethod("GET", new LambdaIntegration(preBuiltFunctionNodeJsRuntime));
        normalRootResource.addResource("goFunction")
                .addMethod("GET", new LambdaIntegration(goFunction));
        normalRootResource.addResource("functionGoRuntime")
                .addMethod("GET", new LambdaIntegration(functionGoRuntime));
        normalRootResource.addResource("dockerImageFunction")
                .addMethod("GET", new LambdaIntegration(dockerImageFunction));
        normalRootResource.addResource("functionImageAsset")
                .addMethod("GET", new LambdaIntegration(functionImageAsset));
        normalRootResource.addResource("dockerImageFunctionWithSharedCode")
                .addMethod("GET", new LambdaIntegration(dockerImageFunctionWithSharedCode));
        normalRootResource.addResource("functionImageAssetWithSharedCode")
                .addMethod("GET", new LambdaIntegration(functionImageAssetWithSharedCode));

        // Nested Stack
        new NestedStack1(this, "NestedStack");

    }
}
