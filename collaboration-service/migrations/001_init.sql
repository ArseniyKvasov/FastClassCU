CREATE TABLE IF NOT EXISTS collab_schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS collab_documents (
    room_id TEXT PRIMARY KEY,
    task_id UUID NOT NULL,
    context_type TEXT NOT NULL,
    context_id UUID NOT NULL,
    owner_user_id UUID NOT NULL,
    yjs_state BYTEA NOT NULL,
    revision BIGINT NOT NULL DEFAULT 0,
    schema_version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_snapshot_at TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_collab_documents_task_id ON collab_documents(task_id);
CREATE INDEX IF NOT EXISTS idx_collab_documents_context ON collab_documents(context_type, context_id);
CREATE INDEX IF NOT EXISTS idx_collab_documents_owner_user_id ON collab_documents(owner_user_id);
