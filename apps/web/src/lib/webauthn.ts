import {
  webauthnLoginBegin,
  webauthnLoginComplete,
  webauthnRegisterBegin,
  webauthnRegisterComplete,
} from "./api";

export function isPasskeySupported(): boolean {
  return typeof window !== "undefined" && !!window.PublicKeyCredential && !!navigator.credentials;
}

function base64urlToBuffer(base64url: string): ArrayBuffer {
  const padding = "=".repeat((4 - (base64url.length % 4)) % 4);
  const base64 = (base64url + padding).replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes.buffer;
}

function bufferToBase64url(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export async function registerPasskey(label?: string): Promise<void> {
  const options = await webauthnRegisterBegin();
  const publicKey = {
    ...options,
    challenge: base64urlToBuffer(options.challenge),
    user: { ...options.user, id: base64urlToBuffer(options.user.id) },
    excludeCredentials: (options.excludeCredentials ?? []).map((cred) => ({
      ...cred,
      id: base64urlToBuffer(cred.id),
    })),
  } as unknown as PublicKeyCredentialCreationOptions;

  const credential = (await navigator.credentials.create({ publicKey })) as PublicKeyCredential;
  const response = credential.response as AuthenticatorAttestationResponse;

  await webauthnRegisterComplete(
    {
      id: credential.id,
      rawId: bufferToBase64url(credential.rawId),
      type: credential.type,
      response: {
        clientDataJSON: bufferToBase64url(response.clientDataJSON),
        attestationObject: bufferToBase64url(response.attestationObject),
      },
      clientExtensionResults: credential.getClientExtensionResults(),
    },
    label,
  );
}

export async function loginWithPasskey(): Promise<string> {
  const { session_key: sessionKey, ...options } = await webauthnLoginBegin();
  const publicKey = {
    ...options,
    challenge: base64urlToBuffer(options.challenge),
    allowCredentials: (options.allowCredentials ?? []).map((cred) => ({
      ...cred,
      id: base64urlToBuffer(cred.id),
    })),
  } as unknown as PublicKeyCredentialRequestOptions;

  const credential = (await navigator.credentials.get({ publicKey })) as PublicKeyCredential;
  const response = credential.response as AuthenticatorAssertionResponse;

  const { access_token: accessToken } = await webauthnLoginComplete(sessionKey, {
    id: credential.id,
    rawId: bufferToBase64url(credential.rawId),
    type: credential.type,
    response: {
      clientDataJSON: bufferToBase64url(response.clientDataJSON),
      authenticatorData: bufferToBase64url(response.authenticatorData),
      signature: bufferToBase64url(response.signature),
      userHandle: response.userHandle ? bufferToBase64url(response.userHandle) : undefined,
    },
    clientExtensionResults: credential.getClientExtensionResults(),
  });
  return accessToken;
}
