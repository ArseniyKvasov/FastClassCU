import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

import type { Pool } from "pg";

import { migrationsDir } from "./config.js";

export async function runMigrations(pool: Pool): Promise<void> {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS collab_schema_migrations (
      version TEXT PRIMARY KEY,
      applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
  `);

  const applied = await pool.query<{ version: string }>(
    "SELECT version FROM collab_schema_migrations",
  );
  const appliedSet = new Set(applied.rows.map((row) => row.version));

  const files = readdirSync(migrationsDir)
    .filter((name) => name.endsWith(".sql"))
    .sort();

  for (const fileName of files) {
    if (appliedSet.has(fileName)) {
      continue;
    }
    const sql = readFileSync(join(migrationsDir, fileName), "utf-8");
    const client = await pool.connect();
    try {
      await client.query("BEGIN");
      await client.query(sql);
      await client.query(
        "INSERT INTO collab_schema_migrations(version) VALUES ($1)",
        [fileName],
      );
      await client.query("COMMIT");
    } catch (error) {
      await client.query("ROLLBACK");
      throw error;
    } finally {
      client.release();
    }
  }
}
