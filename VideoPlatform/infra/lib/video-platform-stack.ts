import { Stack, StackProps, CfnOutput, Tags } from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { StorageConstruct } from './constructs/storage';
import { AuthConstruct } from './constructs/auth';
import { DeliveryConstruct } from './constructs/delivery';
import { PipelineConstruct } from './constructs/pipeline';
import { ApiConstruct } from './constructs/api';
import { COST_TAGS } from './config';

/**
 * Stack única que compõe os constructs da VideoPlatform.
 * Stack única evita a complexidade de referências cross-stack num protótipo.
 */
export class VideoPlatformStack extends Stack {
  constructor(scope: Construct, id: string, props?: StackProps) {
    super(scope, id, props);

    // 1. Armazenamento (S3 privado + DynamoDB)
    const storage = new StorageConstruct(this, 'Storage');

    // 2. Autenticação (Cognito)
    const auth = new AuthConstruct(this, 'Auth');

    // 3. Entrega segura (CloudFront + OAC + cookies assinados + WAF)
    const delivery = new DeliveryConstruct(this, 'Delivery', {
      mediaBucket: storage.mediaBucket,
    });

    // 4. Pipeline de processamento (Step Functions + MediaConvert + Transcribe)
    const pipeline = new PipelineConstruct(this, 'Pipeline', {
      mediaBucket: storage.mediaBucket,
      videosTable: storage.videosTable,
      settingsTable: storage.settingsTable,
    });

    // 5. API (upload, status, revisão, legenda, tradução, play, analytics, config)
    const api = new ApiConstruct(this, 'Api', {
      mediaBucket: storage.mediaBucket,
      videosTable: storage.videosTable,
      playsTable: storage.playsTable,
      settingsTable: storage.settingsTable,
      userPool: auth.userPool,
      userPoolClient: auth.userPoolClient,
      distribution: delivery.distribution,
      signingPublicKeyId: delivery.publicKeyId,
      signingPrivateKeySecret: delivery.privateKeySecret,
    });

    // Pipeline opcional: o Finalize pode disparar o worker de IA (SDH + avaliação)
    // automaticamente ao final (gated por settings pipeline.autoSdhMethod).
    api.aiWorkerFn.grantInvoke(pipeline.finalizeFn);
    pipeline.finalizeFn.addEnvironment('AI_WORKER_FN', api.aiWorkerFn.functionName);

    // ----- Tags de alocação de custo em toda a stack -----
    Tags.of(this).add('project', COST_TAGS.project);

    // ----- Saídas úteis para configurar o frontend -----
    new CfnOutput(this, 'MediaBucketName', { value: storage.mediaBucket.bucketName });
    new CfnOutput(this, 'VideosTableName', { value: storage.videosTable.tableName });
    new CfnOutput(this, 'PlaysTableName', { value: storage.playsTable.tableName });
    new CfnOutput(this, 'UserPoolId', { value: auth.userPool.userPoolId });
    new CfnOutput(this, 'UserPoolClientId', { value: auth.userPoolClient.userPoolClientId });
    new CfnOutput(this, 'CloudFrontDomain', { value: delivery.distribution.distributionDomainName });
    new CfnOutput(this, 'CloudFrontUrl', { value: `https://${delivery.distribution.distributionDomainName}` });
    new CfnOutput(this, 'FrontendBucketName', { value: delivery.frontendBucket.bucketName });
    new CfnOutput(this, 'ApiUrl', { value: api.apiUrl });
  }
}
