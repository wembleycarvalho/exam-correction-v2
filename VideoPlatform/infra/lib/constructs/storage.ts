import { Construct } from 'constructs';
import { RemovalPolicy, Duration, CustomResource } from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as logs from 'aws-cdk-lib/aws-logs';
import { APP_PREFIX } from '../config';
import { backendCode, NODE_RUNTIME } from '../backend-code';

/**
 * Armazenamento: bucket S3 PRIVADO (bruto + profiles), tabelas DynamoDB
 * (vídeos + plays) e a tabela de CONFIGURAÇÃO (settings), semeada no deploy.
 */
export class StorageConstruct extends Construct {
  public readonly mediaBucket: s3.Bucket;
  public readonly videosTable: dynamodb.Table;
  public readonly playsTable: dynamodb.Table;
  public readonly settingsTable: dynamodb.Table;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    // ----- Bucket de mídia (bruto + profiles) -----
    this.mediaBucket = new s3.Bucket(this, 'MediaBucket', {
      // Totalmente privado: nenhum acesso público é permitido.
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      publicReadAccess: false,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: false,
      // CORS necessário apenas para o UPLOAD multipart direto do navegador.
      // (A entrega do vídeo é via CloudFront, não direto no S3.)
      cors: [
        {
          allowedMethods: [
            s3.HttpMethods.PUT,
            s3.HttpMethods.POST,
            s3.HttpMethods.GET,
            s3.HttpMethods.HEAD,
          ],
          // Protótipo: liberar origem. Em produção, restrinja ao domínio do frontend.
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
          // ETag é necessário para concluir o multipart upload no cliente.
          exposedHeaders: ['ETag'],
          maxAge: 3000,
        },
      ],
      // Protótipo: facilita teardown com `cdk destroy`.
      removalPolicy: RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
      lifecycleRules: [
        // Limpa uploads multipart incompletos para não acumular custo.
        { abortIncompleteMultipartUploadAfter: Duration.days(2) },
      ],
    });

    // ----- Tabela de vídeos (metadados + status + custo + contador de plays) -----
    this.videosTable = new dynamodb.Table(this, 'VideosTable', {
      tableName: `${APP_PREFIX}-videos`,
      partitionKey: { name: 'videoId', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      pointInTimeRecovery: true,
      removalPolicy: RemovalPolicy.DESTROY, // protótipo
    });

    // GSI para listar/ordenar por status (Biblioteca e Analytics).
    this.videosTable.addGlobalSecondaryIndex({
      indexName: 'byStatus',
      partitionKey: { name: 'status', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'createdAt', type: dynamodb.AttributeType.STRING },
      projectionType: dynamodb.ProjectionType.ALL,
    });

    // ----- Tabela de plays (eventos para analytics) -----
    this.playsTable = new dynamodb.Table(this, 'PlaysTable', {
      tableName: `${APP_PREFIX}-plays`,
      partitionKey: { name: 'videoId', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'ts', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY, // protótipo
    });

    // ----- Tabela de CONFIGURAÇÃO (settings) -----
    // Toda a config de comportamento vive aqui; editável na tela de Config.
    this.settingsTable = new dynamodb.Table(this, 'SettingsTable', {
      tableName: `${APP_PREFIX}-settings`,
      partitionKey: { name: 'settingKey', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: RemovalPolicy.DESTROY, // protótipo
    });

    // Seed dos valores padrão + metadados (só cria o que não existe; não
    // sobrescreve valores já editados pelo usuário).
    const seedFn = new lambda.Function(this, 'SeedSettingsFn', {
      runtime: NODE_RUNTIME,
      code: backendCode(),
      handler: 'infra/seed-settings.handler',
      timeout: Duration.minutes(2),
    });
    this.settingsTable.grantWriteData(seedFn);

    const seedProvider = new cr.Provider(this, 'SeedSettingsProvider', {
      onEventHandler: seedFn,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // SeedVersion muda sempre que os defaults/metadados mudam, forçando o
    // custom resource a rodar de novo (e adicionar chaves novas).
    new CustomResource(this, 'SeedSettings', {
      serviceToken: seedProvider.serviceToken,
      properties: { SettingsTable: this.settingsTable.tableName, SeedVersion: '10' },
    });
  }
}
