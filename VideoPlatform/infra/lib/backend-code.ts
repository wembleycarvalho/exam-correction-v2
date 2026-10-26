import * as path from 'path';
import * as lambda from 'aws-cdk-lib/aws-lambda';

/**
 * Caminho para os handlers do backend (JavaScript puro, sem build).
 * Reaproveitar o mesmo asset em várias Functions gera um único upload (mesmo hash).
 */
export const BACKEND_SRC_PATH = path.resolve(__dirname, '../../backend/src');

// nodejs22.x é LTS e inclui o AWS SDK v3 no runtime (do qual os handlers dependem).
export const NODE_RUNTIME = lambda.Runtime.NODEJS_22_X;

let cached: lambda.AssetCode | undefined;
export function backendCode(): lambda.AssetCode {
  if (!cached) cached = lambda.Code.fromAsset(BACKEND_SRC_PATH);
  return cached;
}
