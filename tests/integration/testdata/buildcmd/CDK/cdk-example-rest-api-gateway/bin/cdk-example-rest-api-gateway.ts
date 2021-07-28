#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from '@aws-cdk/core';
import { CdkExampleRestApiGatewayStack } from '../lib/cdk-example-rest-api-gateway-stack';

const app = new cdk.App();
new CdkExampleRestApiGatewayStack(app, 'CdkExampleRestApiGatewayStack');
