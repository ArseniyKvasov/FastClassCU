import test from "node:test";
import assert from "node:assert/strict";

import { issueCollabToken, verifyCollabToken } from "../src/auth.js";
import { buildRoomId } from "../src/room.js";

test("buildRoomId is deterministic", () => {
  const first = buildRoomId({
    task_id: "11111111-1111-1111-1111-111111111111",
    context_type: "classroom",
    context_id: "22222222-2222-2222-2222-222222222222",
    owner_user_id: "33333333-3333-3333-3333-333333333333",
  });

  const second = buildRoomId({
    task_id: "11111111-1111-1111-1111-111111111111",
    context_type: "classroom",
    context_id: "22222222-2222-2222-2222-222222222222",
    owner_user_id: "33333333-3333-3333-3333-333333333333",
  });

  assert.equal(first, second);
  assert.match(first, /^writing-answer:[a-f0-9]{64}$/);
});

test("collab token round-trips the session context", () => {
  const token = issueCollabToken({
    task_id: "11111111-1111-1111-1111-111111111111",
    context_type: "assignment",
    context_id: "22222222-2222-2222-2222-222222222222",
    owner_user_id: "33333333-3333-3333-3333-333333333333",
    roomId: buildRoomId({
      task_id: "11111111-1111-1111-1111-111111111111",
      context_type: "assignment",
      context_id: "22222222-2222-2222-2222-222222222222",
      owner_user_id: "33333333-3333-3333-3333-333333333333",
    }),
    actorUserId: "44444444-4444-4444-4444-444444444444",
    actorRole: "teacher",
  });

  const context = verifyCollabToken(token);
  assert.equal(context.actorRole, "teacher");
  assert.equal(context.actorUserId, "44444444-4444-4444-4444-444444444444");
  assert.equal(context.context_type, "assignment");
});
