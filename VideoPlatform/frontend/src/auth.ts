import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserSession,
} from 'amazon-cognito-identity-js';
import { config } from './config';

let pool: CognitoUserPool | null = null;
function userPool(): CognitoUserPool {
  if (!pool) {
    pool = new CognitoUserPool({
      UserPoolId: config.userPoolId,
      ClientId: config.userPoolClientId,
    });
  }
  return pool;
}

export interface LoginResult {
  status: 'ok' | 'newPasswordRequired';
  user?: CognitoUser;
}

/** Login via SRP. Pode exigir troca de senha no primeiro acesso (usuário criado por admin). */
export function login(email: string, password: string): Promise<LoginResult> {
  const user = new CognitoUser({ Username: email, Pool: userPool() });
  const details = new AuthenticationDetails({ Username: email, Password: password });

  return new Promise((resolve, reject) => {
    user.authenticateUser(details, {
      onSuccess: () => resolve({ status: 'ok' }),
      onFailure: (err) => reject(err),
      newPasswordRequired: () => resolve({ status: 'newPasswordRequired', user }),
    });
  });
}

/** Completa o desafio de nova senha (primeiro acesso). */
export function completeNewPassword(user: CognitoUser, newPassword: string): Promise<void> {
  return new Promise((resolve, reject) => {
    user.completeNewPasswordChallenge(
      newPassword,
      {},
      {
        onSuccess: () => resolve(),
        onFailure: (err) => reject(err),
      }
    );
  });
}

export function currentUser(): CognitoUser | null {
  return userPool().getCurrentUser();
}

/** Sessão atual (renova via refresh token se necessário). */
export function getSession(): Promise<CognitoUserSession | null> {
  const user = currentUser();
  if (!user) return Promise.resolve(null);
  return new Promise((resolve) => {
    user.getSession((err: Error | null, session: CognitoUserSession | null) => {
      if (err || !session || !session.isValid()) resolve(null);
      else resolve(session);
    });
  });
}

/** ID token (JWT) para o header Authorization. */
export async function getIdToken(): Promise<string | null> {
  const session = await getSession();
  return session ? session.getIdToken().getJwtToken() : null;
}

export async function getEmail(): Promise<string | null> {
  const session = await getSession();
  if (!session) return null;
  const payload = session.getIdToken().decodePayload();
  return (payload['email'] as string) || null;
}

export function signOut(): void {
  currentUser()?.signOut();
}
