#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { VideoPlatformStack } from '../lib/video-platform-stack';
import { APP_PREFIX, REGION } from '../lib/config';

const app = new cdk.App();

new VideoPlatformStack(app, `${APP_PREFIX}-stack`, {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: REGION,
  },
  description: 'VideoPlatform (VOD) - prototipo: upload, pipeline, entrega segura, frontend.',
});

app.synth();
