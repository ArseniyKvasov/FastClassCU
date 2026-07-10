import { Pool } from "pg";

import { settings } from "./config.js";
import { runMigrations } from "./migrations.js";

async function main(): Promise<void> {
  const pool = new Pool({ connectionString: settings.databaseUrl });
  try {
    await runMigrations(pool);
  } finally {
    await pool.end();
  }
}

main()
  .then(() => {
    process.exit(0);
  })
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
