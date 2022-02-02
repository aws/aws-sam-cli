#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { CDKSupportDemoRootStack } from '../lib/test-stack';

const app = new cdk.App();
new CDKSupportDemoRootStack(app, 'TestStack');
app.synth();