import { Construct } from 'constructs';
import { CustomResource, Duration, RemovalPolicy } from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as wafv2 from 'aws-cdk-lib/aws-wafv2';
import * as cr from 'aws-cdk-lib/custom-resources';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import { backendCode, NODE_RUNTIME } from '../backend-code';
import { APP_PREFIX, PROFILES_PREFIX } from '../config';

export interface DeliveryProps {
  readonly mediaBucket: s3.Bucket;
}

/**
 * Entrega segura. Uma distribuição CloudFront serve TUDO sob o mesmo domínio
 * (same-origin, evitando CORS e dor de cabeça com cookies):
 *   - default            -> bucket do frontend (SPA, público via CDN)
 *   - /video-profiles/*   -> bucket de mídia (OAC + cookies assinados obrigatórios)
 *   - /api/*              -> API Gateway (adicionado pelo ApiConstruct)
 *
 * A chave privada de assinatura fica no Secrets Manager; a pública é registrada
 * em um Trusted Key Group do CloudFront.
 */
export class DeliveryConstruct extends Construct {
  public readonly distribution: cloudfront.Distribution;
  public readonly frontendBucket: s3.Bucket;
  public readonly publicKeyId: string;
  public readonly privateKeySecret: secretsmanager.Secret;

  constructor(scope: Construct, id: string, props: DeliveryProps) {
    super(scope, id);

    const { mediaBucket } = props;

    // ---- Bucket do frontend (SPA), privado; servido só via CloudFront (OAC) ----
    this.frontendBucket = new s3.Bucket(this, 'FrontendBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: RemovalPolicy.DESTROY, // protótipo
      autoDeleteObjects: true,
    });

    // ---- Chave de assinatura (par RSA via custom resource) ----
    this.privateKeySecret = new secretsmanager.Secret(this, 'SigningPrivateKey', {
      secretName: `${APP_PREFIX}-cf-signing-private-key`,
      description: 'Chave privada RSA para assinar cookies do CloudFront',
      removalPolicy: RemovalPolicy.DESTROY, // protótipo
    });

    const keygenFn = new lambda.Function(this, 'KeygenFn', {
      runtime: NODE_RUNTIME,
      code: backendCode(),
      handler: 'infra/keygen.handler',
      timeout: Duration.minutes(1),
    });
    this.privateKeySecret.grantWrite(keygenFn);

    const keygenProvider = new cr.Provider(this, 'KeygenProvider', {
      onEventHandler: keygenFn,
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    const keygen = new CustomResource(this, 'SigningKeyPair', {
      serviceToken: keygenProvider.serviceToken,
      properties: { SecretArn: this.privateKeySecret.secretArn },
    });

    const publicKey = new cloudfront.PublicKey(this, 'SigningPublicKey', {
      encodedKey: keygen.getAttString('PublicKey'),
      comment: `${APP_PREFIX} CloudFront signing key`,
    });
    this.publicKeyId = publicKey.publicKeyId;

    const keyGroup = new cloudfront.KeyGroup(this, 'SigningKeyGroup', {
      items: [publicKey],
      comment: `${APP_PREFIX} signed cookies key group`,
    });

    // ---- WAF (escopo CLOUDFRONT exige us-east-1, que é a região da stack) ----
    const webAcl = new wafv2.CfnWebACL(this, 'WebAcl', {
      scope: 'CLOUDFRONT',
      defaultAction: { allow: {} },
      visibilityConfig: {
        cloudWatchMetricsEnabled: true,
        metricName: `${APP_PREFIX}-waf`,
        sampledRequestsEnabled: true,
      },
      rules: [
        {
          name: 'AWSManagedCommon',
          priority: 1,
          overrideAction: { none: {} },
          statement: {
            managedRuleGroupStatement: { vendorName: 'AWS', name: 'AWSManagedRulesCommonRuleSet' },
          },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: `${APP_PREFIX}-waf-common`,
            sampledRequestsEnabled: true,
          },
        },
        {
          name: 'RateLimit',
          priority: 2,
          action: { block: {} },
          statement: { rateBasedStatement: { limit: 2000, aggregateKeyType: 'IP' } },
          visibilityConfig: {
            cloudWatchMetricsEnabled: true,
            metricName: `${APP_PREFIX}-waf-ratelimit`,
            sampledRequestsEnabled: true,
          },
        },
      ],
    });

    // ---- Políticas de resposta/segurança ----
    const securityHeaders = new cloudfront.ResponseHeadersPolicy(this, 'SecurityHeaders', {
      securityHeadersBehavior: {
        strictTransportSecurity: {
          accessControlMaxAge: Duration.days(365),
          includeSubdomains: true,
          override: true,
        },
        contentTypeOptions: { override: true },
        referrerPolicy: {
          referrerPolicy: cloudfront.HeadersReferrerPolicy.STRICT_ORIGIN_WHEN_CROSS_ORIGIN,
          override: true,
        },
        frameOptions: { frameOption: cloudfront.HeadersFrameOption.SAMEORIGIN, override: true },
      },
    });

    // ---- Origens (OAC) ----
    const frontendOrigin = origins.S3BucketOrigin.withOriginAccessControl(this.frontendBucket);
    const mediaOrigin = origins.S3BucketOrigin.withOriginAccessControl(mediaBucket);

    // ---- Distribuição ----
    this.distribution = new cloudfront.Distribution(this, 'Distribution', {
      comment: `${APP_PREFIX} - SPA + media + api`,
      defaultRootObject: 'index.html',
      httpVersion: cloudfront.HttpVersion.HTTP2_AND_3,
      webAclId: webAcl.attrArn,
      // SPA
      defaultBehavior: {
        origin: frontendOrigin,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        responseHeadersPolicy: securityHeaders,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
      },
      additionalBehaviors: {
        // Mídia protegida: exige cookies assinados (trusted key group).
        [`${PROFILES_PREFIX}/*`]: {
          origin: mediaOrigin,
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          responseHeadersPolicy: securityHeaders,
          cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
          trustedKeyGroups: [keyGroup],
        },
      },
      // Sem error-responses globais de propósito: um 403 da mídia (cookie
      // inválido) deve continuar sendo 403. A SPA usa hash routing (#/...),
      // então não precisa de rewrite de rota no servidor.
    });
  }
}
