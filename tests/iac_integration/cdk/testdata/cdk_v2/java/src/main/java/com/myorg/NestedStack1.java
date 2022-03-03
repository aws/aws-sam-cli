package com.myorg;

import org.jetbrains.annotations.NotNull;
import software.amazon.awscdk.NestedStack;
import software.amazon.awscdk.services.apigatewayv2.alpha.AddRoutesOptions;
import software.amazon.awscdk.services.apigatewayv2.alpha.HttpApi;
import software.amazon.awscdk.services.apigatewayv2.alpha.HttpMethod;
import software.amazon.awscdk.services.apigatewayv2.integrations.alpha.HttpLambdaIntegration;
import software.amazon.awscdk.services.lambda.Runtime;
import software.amazon.awscdk.services.lambda.*;
import software.amazon.awscdk.services.lambda.python.alpha.PythonFunction;
import software.amazon.awscdk.services.lambda.python.alpha.PythonLayerVersion;
import software.amazon.awscdk.services.logs.RetentionDays;
import software.constructs.Construct;

import java.util.Arrays;

public class NestedStack1 extends NestedStack {

    public NestedStack1(@NotNull Construct scope, @NotNull String id) {
        super(scope, id);

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

        // ZIP package type Functions
        // Functions Built by CDK - Runtime Functions Constructs
        PythonFunction nestedPythonFunction = PythonFunction.Builder
                .create(this, "NestedPythonFunction")
                .entry("../../src/python/NestedPythonFunctionConstruct")
                .index("app.py")
                .handler("lambda_handler")
                .runtime(Runtime.PYTHON_3_9)
                .logRetention(RetentionDays.THREE_MONTHS)
                .layers(Arrays.asList(pythonLayerVersion, layerVersion))
                .tracing(Tracing.ACTIVE)
                .build();

        HttpApi httpApi = new HttpApi(this, "httpAPi");

        httpApi.addRoutes(AddRoutesOptions.builder()
                .path("/httpapis/nestedPythonFunction")
                .methods(Arrays.asList(HttpMethod.GET))
                .integration(new HttpLambdaIntegration("httpApiRandomNameIntegration", nestedPythonFunction))
                .build()
        );
    }
}
