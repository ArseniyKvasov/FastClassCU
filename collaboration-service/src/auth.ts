import jwt from "jsonwebtoken";

import { jwtPublicKey, settings } from "./config.js";
import { buildRoomId } from "./room.js";
import type {
  AuthUser,
  CollabTokenClaims,
  SessionContext,
  SessionRequest,
} from "./types.js";

export class AuthError extends Error {}

export function verifyAuthToken(token: string): AuthUser {
  try {
    const payload = jwt.verify(token, jwtPublicKey, {
      algorithms: ["RS256"],
      issuer: settings.jwtIssuer,
    }) as jwt.JwtPayload;
    if (typeof payload.sub !== "string" || payload.sub.length === 0) {
      throw new AuthError("JWT is missing sub");
    }
    return {
      userId: payload.sub,
      accessLevel:
        typeof payload.access_level === "string"
          ? payload.access_level
          : "unknown",
      rawToken: token,
    };
  } catch (error) {
    throw new AuthError("Invalid auth token");
  }
}

export function issueCollabToken(context: SessionContext): string {
  const now = Math.floor(Date.now() / 1000);
  const claims: CollabTokenClaims = {
    room_id: context.roomId,
    task_id: context.task_id,
    context_type: context.context_type,
    context_id: context.context_id,
    owner_user_id: context.owner_user_id,
    actor_user_id: context.actorUserId,
    actor_role: context.actorRole,
    iss: "collaboration-service",
    sub: context.actorUserId,
    iat: now,
    exp: now + settings.collabTokenTtlSeconds,
  };

  return jwt.sign(claims, settings.collabTokenSecret, {
    algorithm: "HS256",
  });
}

export function verifyCollabToken(token: string): SessionContext {
  try {
    const payload = jwt.verify(token, settings.collabTokenSecret, {
      algorithms: ["HS256"],
      issuer: "collaboration-service",
    }) as CollabTokenClaims;

    const requestLike: SessionRequest = {
      task_id: payload.task_id,
      context_type: payload.context_type,
      context_id: payload.context_id,
      owner_user_id: payload.owner_user_id,
    };
    const expectedRoomId = buildRoomId(requestLike);
    if (payload.room_id !== expectedRoomId) {
      throw new AuthError("Room/token mismatch");
    }

    return {
      ...requestLike,
      roomId: payload.room_id,
      actorUserId: payload.actor_user_id,
      actorRole: payload.actor_role,
    };
  } catch (error) {
    throw new AuthError("Invalid collaboration token");
  }
}
