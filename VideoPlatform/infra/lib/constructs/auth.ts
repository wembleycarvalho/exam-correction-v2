import { Construct } from 'constructs';
import { RemovalPolicy } from 'aws-cdk-lib';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import { APP_PREFIX } from '../config';

/**
 * Autenticação (tela de login). User Pool do Cognito.
 * Nesta fase todos os usuários são admin (sem grupos/papéis).
 * Self sign-up DESABILITADO por segurança — usuários são criados por um admin
 * (console ou CLI). Veja infra/README.md para criar o primeiro usuário.
 */
export class AuthConstruct extends Construct {
  public readonly userPool: cognito.UserPool;
  public readonly userPoolClient: cognito.UserPoolClient;

  constructor(scope: Construct, id: string) {
    super(scope, id);

    this.userPool = new cognito.UserPool(this, 'UserPool', {
      userPoolName: `${APP_PREFIX}-users`,
      selfSignUpEnabled: false,
      signInAliases: { email: true },
      autoVerify: { email: true },
      standardAttributes: {
        email: { required: true, mutable: true },
      },
      passwordPolicy: {
        minLength: 10,
        requireLowercase: true,
        requireUppercase: true,
        requireDigits: true,
        requireSymbols: false,
      },
      accountRecovery: cognito.AccountRecovery.EMAIL_ONLY,
      removalPolicy: RemovalPolicy.DESTROY, // protótipo
    });

    // Cliente público para a SPA (sem secret). Login via SRP (senha não trafega).
    this.userPoolClient = this.userPool.addClient('WebClient', {
      userPoolClientName: `${APP_PREFIX}-web`,
      generateSecret: false,
      authFlows: {
        userSrp: true,
        userPassword: false,
      },
      preventUserExistenceErrors: true,
      accessTokenValidity: undefined, // usa default (1h)
    });
  }
}
