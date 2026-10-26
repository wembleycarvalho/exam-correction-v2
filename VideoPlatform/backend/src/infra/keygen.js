'use strict';

/**
 * Custom Resource do CloudFormation: gera um par de chaves RSA 2048.
 * - A chave PRIVADA é gravada no Secrets Manager (usada pela API para assinar cookies).
 * - A chave PÚBLICA é devolvida (Data.PublicKey) para criar o CloudFront PublicKey.
 *
 * A chave privada NUNCA aparece no template nem em logs.
 */

const crypto = require('crypto');
const { SecretsManagerClient, PutSecretValueCommand } = require('@aws-sdk/client-secrets-manager');

const sm = new SecretsManagerClient({ region: process.env.AWS_REGION });

exports.handler = async (event) => {
  const type = event.RequestType;

  // Em Delete não há o que fazer (o Secret é removido pela própria stack).
  if (type === 'Delete') {
    return { PhysicalResourceId: event.PhysicalResourceId || 'cloudfront-signing-key' };
  }

  const secretArn = event.ResourceProperties.SecretArn;

  const { publicKey, privateKey } = crypto.generateKeyPairSync('rsa', {
    modulusLength: 2048,
    publicKeyEncoding: { type: 'spki', format: 'pem' },
    privateKeyEncoding: { type: 'pkcs1', format: 'pem' },
  });

  await sm.send(new PutSecretValueCommand({ SecretId: secretArn, SecretString: privateKey }));

  // A chave pública (PEM) pode ser exposta — é pública por definição.
  return {
    PhysicalResourceId: 'cloudfront-signing-key',
    Data: { PublicKey: publicKey },
  };
};
