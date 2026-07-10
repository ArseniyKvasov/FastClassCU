import { propagateHeaders } from "@fastclass/node-shared";

import { settings } from "./config.js";

let cachedToken: string | null = null;
let cachedExpiresAt = 0;
let inflight: Promise<string | null> | null = null;

async function fetchServiceToken(): Promise<string | null> {
  if (!settings.serviceClientSecret) {
    return null;
  }

  const response = await fetch(new URL("/auth/service-token", settings.authServiceBaseUrl), {
    method: "POST",
    headers: propagateHeaders({
      "Content-Type": "application/x-www-form-urlencoded",
    }),
    body: new URLSearchParams({
      grant_type: "client_credentials",
      client_id: settings.serviceClientId,
      client_secret: settings.serviceClientSecret,
      scope: "answers:collab-snapshot:write",
    }),
  });

  if (!response.ok) {
    throw new Error(`Service token request failed with ${response.status}`);
  }

  const payload = (await response.json()) as {
    access_token: string;
    expires_in?: number;
  };
  cachedToken = payload.access_token;
  cachedExpiresAt = Date.now() + ((payload.expires_in ?? 60) - 30) * 1000;
  return cachedToken;
}

export async function getServiceAuthHeaders(): Promise<HeadersInit> {
  if (!settings.serviceClientSecret) {
    return propagateHeaders({
      "Content-Type": "application/json",
      "X-Service-Token": settings.answersServiceToken,
    });
  }

  if (cachedToken && Date.now() < cachedExpiresAt) {
    return propagateHeaders({
      "Content-Type": "application/json",
      Authorization: `Bearer ${cachedToken}`,
    });
  }

  if (!inflight) {
    inflight = fetchServiceToken().finally(() => {
      inflight = null;
    });
  }
  const token = await inflight;
  return token
    ? propagateHeaders({
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      })
    : propagateHeaders({
        "Content-Type": "application/json",
        "X-Service-Token": settings.answersServiceToken,
      });
}
