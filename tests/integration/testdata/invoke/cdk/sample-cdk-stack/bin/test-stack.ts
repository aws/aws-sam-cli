#!/usr/bin/env node
import * as cdk from '@aws-cdk/core';
import { TestStack } from '../lib/test-stack';

const app = new cdk.App();
new TestStack(app, 'Stack');