package com.myorg;

import software.amazon.awscdk.App;
import software.amazon.awscdk.StackProps;

import java.util.Arrays;

public class JavaApp {
    public static void main(final String[] args) {
        App app = new App();

        new JavaStack(app, "TestStack", StackProps.builder()
                .build());

        app.synth();
    }
}
