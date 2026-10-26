import { Construct } from 'constructs';
import { Duration, Stack } from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import { HttpUserPoolAuthorizer } from 'aws-cdk-lib/aws-apigatewayv2-authorizers';
import { HttpLambdaIntegration } from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import { backendCode, NODE_RUNTIME } from '../backend-code';
import { APP_PREFIX, RAW_PREFIX, PROFILES_PREFIX } from '../config';

export interface ApiProps {
  readonly mediaBucket: s3.Bucket;
  readonly videosTable: dynamodb.Table;
  readonly playsTable: dynamodb.Table;
  readonly settingsTable: dynamodb.Table;
  readonly userPool: cognito.UserPool;
  readonly userPoolClient: cognito.UserPoolClient;
  readonly distribution: cloudfront.Distribution;
  readonly signingPublicKeyId: string;
  readonly signingPrivateKeySecret: secretsmanager.Secret;
}

/**
 * API HTTP (API Gateway v2) com uma única Lambda roteadora, protegida por JWT
 * do Cognito. Exposta sob o mesmo domínio CloudFront em /api/* (same-origin),
 * para que os cookies assinados emitidos no /play valham na mídia.
 */
export class ApiConstruct extends Construct {
  public readonly apiUrl: string;
  public readonly aiWorkerFn: lambda.Function;

  constructor(scope: Construct, id: string, props: ApiProps) {
    super(scope, id);

    const {
      mediaBucket,
      videosTable,
      playsTable,
      settingsTable,
      userPool,
      userPoolClient,
      distribution,
      signingPublicKeyId,
      signingPrivateKeySecret,
    } = props;

    const apiFn = new lambda.Function(this, 'ApiFn', {
      runtime: NODE_RUNTIME,
      code: backendCode(),
      handler: 'api/index.handler',
      timeout: Duration.seconds(29), // API HTTP tem limite de 30s
      memorySize: 512,
      environment: {
        // Apenas identidade de infra; TODA config de comportamento vem da tabela settings.
        VIDEOS_TABLE: videosTable.tableName,
        PLAYS_TABLE: playsTable.tableName,
        MEDIA_BUCKET: mediaBucket.bucketName,
        SETTINGS_TABLE: settingsTable.tableName,
        RAW_PREFIX,
        PROFILES_PREFIX,
        APP_PREFIX,
        ACCOUNT_ID: Stack.of(this).account,
        CF_DOMAIN: distribution.distributionDomainName,
        SIGNING_PUBLIC_KEY_ID: signingPublicKeyId,
        SIGNING_PRIVATE_KEY_SECRET_ARN: signingPrivateKeySecret.secretArn,
      },
    });

    // Permissões
    mediaBucket.grantReadWrite(apiFn);
    videosTable.grantReadWriteData(apiFn);
    playsTable.grantReadWriteData(apiFn);
    settingsTable.grantReadWriteData(apiFn); // PUT /api/settings
    signingPrivateKeySecret.grantRead(apiFn);
    apiFn.addToRolePolicy(
      new iam.PolicyStatement({ actions: ['translate:TranslateText'], resources: ['*'] })
    );
    // Bedrock (análise comparativa + traduções síncronas). Amplo no protótipo.
    apiFn.addToRolePolicy(
      new iam.PolicyStatement({ actions: ['bedrock:InvokeModel'], resources: ['*'] })
    );
    // MediaConvert: ler o progresso do job (GET /api/videos/{id}/progress).
    apiFn.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['mediaconvert:GetJob', 'mediaconvert:DescribeEndpoints'],
        resources: ['*'],
      })
    );

    // ---- Worker assíncrono de IA (SDH/Voxtral + Descrição/Pegasus) ----
    // Fica fora do caminho síncrono (evita o limite de 30s do API HTTP).
    const aiWorkerFn = new lambda.Function(this, 'AiWorkerFn', {
      runtime: NODE_RUNTIME,
      code: backendCode(),
      handler: 'workers/ai-worker.handler',
      // SDH de vídeos longos faz várias chamadas Voxtral (fatias) e carrega o
      // WAV inteiro na memória; 15 min é o teto do Lambda.
      timeout: Duration.minutes(15),
      memorySize: 2048,
      environment: {
        VIDEOS_TABLE: videosTable.tableName,
        MEDIA_BUCKET: mediaBucket.bucketName,
        SETTINGS_TABLE: settingsTable.tableName,
        RAW_PREFIX,
        PROFILES_PREFIX,
        ACCOUNT_ID: Stack.of(this).account,
      },
    });
    mediaBucket.grantReadWrite(aiWorkerFn);
    videosTable.grantReadWriteData(aiWorkerFn);
    settingsTable.grantReadData(aiWorkerFn);
    aiWorkerFn.addToRolePolicy(
      new iam.PolicyStatement({ actions: ['bedrock:InvokeModel'], resources: ['*'] })
    );

    // A API dispara o worker de forma assíncrona.
    aiWorkerFn.grantInvoke(apiFn);
    apiFn.addEnvironment('AI_WORKER_FN', aiWorkerFn.functionName);
    this.aiWorkerFn = aiWorkerFn; // exposto p/ o pipeline disparar SDH automático

    // ---- HTTP API + authorizer Cognito ----
    const authorizer = new HttpUserPoolAuthorizer('CognitoAuthorizer', userPool, {
      userPoolClients: [userPoolClient],
    });
    const integration = new HttpLambdaIntegration('ApiIntegration', apiFn);

    const httpApi = new apigw.HttpApi(this, 'HttpApi', {
      apiName: `${APP_PREFIX}-api`,
      corsPreflight: {
        allowHeaders: ['authorization', 'content-type'],
        allowMethods: [apigw.CorsHttpMethod.ANY],
        allowOrigins: ['*'], // protótipo; em prod restrinja ao domínio do frontend
        maxAge: Duration.days(1),
      },
    });

    const routes: Array<[apigw.HttpMethod, string]> = [
      [apigw.HttpMethod.POST, '/api/uploads'],
      [apigw.HttpMethod.POST, '/api/uploads/{videoId}/part-url'],
      [apigw.HttpMethod.POST, '/api/uploads/{videoId}/complete'],
      [apigw.HttpMethod.POST, '/api/uploads/{videoId}/abort'],
      [apigw.HttpMethod.GET, '/api/videos'],
      [apigw.HttpMethod.GET, '/api/videos/{videoId}'],
      [apigw.HttpMethod.GET, '/api/videos/{videoId}/progress'],
      [apigw.HttpMethod.PATCH, '/api/videos/{videoId}'],
      [apigw.HttpMethod.POST, '/api/videos/{videoId}/publish'],
      [apigw.HttpMethod.POST, '/api/videos/{videoId}/unpublish'],
      [apigw.HttpMethod.DELETE, '/api/videos/{videoId}'],
      [apigw.HttpMethod.GET, '/api/videos/{videoId}/subtitle'],
      [apigw.HttpMethod.PUT, '/api/videos/{videoId}/subtitle'],
      [apigw.HttpMethod.POST, '/api/videos/{videoId}/translate'],
      [apigw.HttpMethod.POST, '/api/videos/{videoId}/compare-subtitles'],
      [apigw.HttpMethod.POST, '/api/videos/{videoId}/sdh'],
      [apigw.HttpMethod.POST, '/api/videos/{videoId}/describe'],
      [apigw.HttpMethod.GET, '/api/videos/{videoId}/description'],
      [apigw.HttpMethod.POST, '/api/videos/{videoId}/play'],
      [apigw.HttpMethod.GET, '/api/analytics'],
      [apigw.HttpMethod.GET, '/api/settings'],
      [apigw.HttpMethod.PUT, '/api/settings'],
    ];
    for (const [method, path] of routes) {
      httpApi.addRoutes({ path, methods: [method], integration, authorizer });
    }

    this.apiUrl = httpApi.apiEndpoint;

    // ---- Behavior /api/* no CloudFront (same-origin) ----
    const region = Stack.of(this).region;
    const apiDomain = `${httpApi.apiId}.execute-api.${region}.amazonaws.com`;
    distribution.addBehavior('api/*', new origins.HttpOrigin(apiDomain), {
      viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
      allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
      cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
      originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
    });
  }
}
