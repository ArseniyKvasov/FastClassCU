import { config as loadEnv } from "dotenv";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

loadEnv();

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, "..");

function env(name: string, fallback?: string): string {
  const value = process.env[name] ?? fallback;
  if (value == null || value === "") {
    throw new Error(`Missing required environment variable ${name}`);
  }
  return value;
}

function intEnv(name: string, fallback: number): number {
  const raw = process.env[name];
  if (!raw) {
    return fallback;
  }
  const parsed = Number.parseInt(raw, 10);
  if (!Number.isFinite(parsed)) {
    throw new Error(`Environment variable ${name} must be an integer`);
  }
  return parsed;
}

function csvEnv(name: string): string[] {
  return String(process.env[name] ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export const settings = {
  port: intEnv("PORT", 8000),
  wsPath: env("WS_PATH", "/ws/collab"),
  databaseUrl: env(
    "DATABASE_URL",
    "postgresql://collab:collab@localhost:5439/collaboration",
  ),
  redisUrl: env("REDIS_URL", "redis://localhost:6384/0"),
  jwtIssuer: env("JWT_ISSUER", "auth-service"),
  // Each service holds its own copy of Auth Service's public key (fetched
  // from Auth Service's /auth/public-key at provisioning time in real
  // deployments) - reaching into a sibling service's directory only works
  // in this local monorepo-style layout and breaks the moment each service
  // is deployed as its own independent container.
  jwtPublicKeyPath: resolve(
    projectRoot,
    env("JWT_PUBLIC_KEY_PATH", "keys/public.pem"),
  ),
  collabTokenSecret: env("COLLAB_TOKEN_SECRET", "replace-me"),
  collabTokenTtlSeconds: intEnv("COLLAB_TOKEN_TTL_SECONDS", 300),
  answersServiceBaseUrl: env(
    "ANSWERS_SERVICE_BASE_URL",
    "http://localhost:8006",
  ),
  authServiceBaseUrl: env(
    "AUTH_SERVICE_BASE_URL",
    "http://localhost:8001",
  ),
  serviceClientId: env("SERVICE_CLIENT_ID", "collaboration-service"),
  serviceClientSecret: process.env.SERVICE_CLIENT_SECRET?.trim() || "",
  answersServiceToken: env(
    "ANSWERS_SERVICE_TOKEN",
    "dev-insecure-service-token",
  ),
  classroomServiceBaseUrl: env(
    "CLASSROOM_SERVICE_BASE_URL",
    "http://localhost:8004",
  ),
  assignmentsServiceBaseUrl: env(
    "ASSIGNMENTS_SERVICE_BASE_URL",
    "http://localhost:8005",
  ),
  corsOrigins: csvEnv("CORS_ORIGINS"),
  publicWsBaseUrl: process.env.PUBLIC_WS_BASE_URL?.trim() || null,
  hocuspocusDebounceMs: intEnv("HOCUSPOCUS_DEBOUNCE_MS", 2000),
  hocuspocusMaxDebounceMs: intEnv("HOCUSPOCUS_MAX_DEBOUNCE_MS", 5000),
  roomFieldName: env("ROOM_FIELD_NAME", "default"),
};

export const jwtPublicKey = readFileSync(settings.jwtPublicKeyPath, "utf-8");
export const migrationsDir = resolve(projectRoot, "migrations");
