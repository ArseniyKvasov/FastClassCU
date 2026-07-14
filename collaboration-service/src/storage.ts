import { Pool } from "pg";
import * as Y from "yjs";

import { settings } from "./config.js";
import { extractPlainText, yDocToJson } from "./schema.js";
import type {
  PersistedSnapshot,
  SessionContext,
  StoredDocumentRow,
} from "./types.js";

export class CollabStorage {
  readonly pool: Pool;

  constructor() {
    this.pool = new Pool({
      connectionString: settings.databaseUrl,
      max: 2,
    });
  }

  async close(): Promise<void> {
    await this.pool.end();
  }

  async healthcheck(): Promise<void> {
    await this.pool.query("SELECT 1");
  }

  async getDocument(roomId: string): Promise<StoredDocumentRow | null> {
    const result = await this.pool.query<StoredDocumentRow>(
      `
        SELECT
          room_id,
          task_id::text,
          context_type,
          context_id::text,
          owner_user_id::text,
          yjs_state,
          revision,
          schema_version
        FROM collab_documents
        WHERE room_id = $1
      `,
      [roomId],
    );
    return result.rows[0] ?? null;
  }

  async saveDocument(
    context: SessionContext,
    document: Y.Doc,
  ): Promise<PersistedSnapshot> {
    const state = Buffer.from(Y.encodeStateAsUpdate(document));
    const documentJson = yDocToJson(document);
    const plainText = extractPlainText(documentJson).trim();

    const result = await this.pool.query<{ revision: string }>(
      `
        INSERT INTO collab_documents (
          room_id,
          task_id,
          context_type,
          context_id,
          owner_user_id,
          yjs_state,
          revision,
          schema_version,
          created_at,
          updated_at,
          last_snapshot_at
        )
        VALUES ($1, $2::uuid, $3, $4::uuid, $5::uuid, $6, 1, 1, NOW(), NOW(), NOW())
        ON CONFLICT (room_id)
        DO UPDATE SET
          yjs_state = EXCLUDED.yjs_state,
          revision = collab_documents.revision + 1,
          updated_at = NOW(),
          last_snapshot_at = NOW()
        RETURNING revision::text
      `,
      [
        context.roomId,
        context.task_id,
        context.context_type,
        context.context_id,
        context.owner_user_id,
        state,
      ],
    );

    return {
      revision: Number.parseInt(result.rows[0].revision, 10),
      documentJson,
      plainText,
    };
  }
}
