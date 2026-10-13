"""Compatible immutable vectors and worker-owned durable dense previews."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006_dense_retrieval"
down_revision = "0005_index_span_shape"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE chunk_embeddings (
          chunk_id uuid PRIMARY KEY REFERENCES index_chunks(id),
          index_id uuid NOT NULL REFERENCES index_variants(id),
          compatibility_key varchar(64) NOT NULL,
          embedding vector(384) NOT NULL,
          CHECK (abs(vector_norm(embedding)-1) < 0.001)
        );
        CREATE INDEX ix_embeddings_index ON chunk_embeddings(index_id);
        CREATE FUNCTION guard_chunk_embedding() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE parent index_variants%ROWTYPE;
        BEGIN
          IF TG_OP<>'INSERT' THEN
            RAISE EXCEPTION 'Embeddings are immutable' USING ERRCODE='23514';
          END IF;
          SELECT * INTO parent FROM index_variants WHERE id=NEW.index_id FOR UPDATE;
          IF parent.state<>'running' OR parent.lease_expires_at IS NULL
            OR parent.lease_expires_at<=clock_timestamp()
            OR COALESCE(parent.config->>'retrieval','')<>'pgvector-exact-cosine-v1'
            OR COALESCE(parent.config->'embedding'->>'compatibility_key','')<>NEW.compatibility_key
            OR NOT EXISTS (SELECT 1 FROM index_chunks
              WHERE id=NEW.chunk_id AND index_id=NEW.index_id)
          THEN
            RAISE EXCEPTION 'Embedding lineage or compatibility mismatch' USING ERRCODE='23514';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER embedding_lineage BEFORE INSERT OR UPDATE OR DELETE ON chunk_embeddings
          FOR EACH ROW EXECUTE FUNCTION guard_chunk_embedding();
        CREATE FUNCTION guard_dense_publication() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF NEW.state='ready' AND NEW.config->>'retrieval'='pgvector-exact-cosine-v1' THEN
            IF NEW.chunk_count<>(SELECT count(*) FROM chunk_embeddings WHERE index_id=NEW.id)
              OR COALESCE(NEW.manifest->'embedding'->'contract'->>'compatibility_key','')
                <>NEW.config->'embedding'->>'compatibility_key' THEN
              RAISE EXCEPTION 'Dense publication requires compatible embeddings'
                USING ERRCODE='23514';
            END IF;
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER dense_publication BEFORE UPDATE ON index_variants
          FOR EACH ROW EXECUTE FUNCTION guard_dense_publication();
    """)
    op.create_table(
        "dense_searches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("index_id", sa.Uuid(), sa.ForeignKey("index_variants.id"), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("request", JSONB(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("result", JSONB()),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("lease_token", sa.Uuid()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("index_id", "request_hash", name="uq_dense_preview_request"),
        sa.CheckConstraint(
            "state IN ('pending','running','completed','failed')", name="ck_dense_preview_state"
        ),
        sa.CheckConstraint(
            "attempts>=0 AND max_attempts BETWEEN 1 AND 10", name="ck_dense_preview_attempts"
        ),
        sa.CheckConstraint(
            "(state='completed')=(result IS NOT NULL)", name="ck_dense_preview_result"
        ),
    )
    op.create_index(
        "ix_dense_preview_queue", "dense_searches", ["state", "available_at", "created_at"]
    )
    op.execute("""
        CREATE FUNCTION guard_dense_search() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP='DELETE' THEN
            RAISE EXCEPTION 'Dense previews cannot be deleted' USING ERRCODE='23514';
          END IF;
          IF TG_OP='UPDATE' AND (OLD.state='completed' OR NEW.id<>OLD.id
            OR NEW.index_id<>OLD.index_id OR NEW.request<>OLD.request
            OR NEW.request_hash<>OLD.request_hash OR NEW.created_at<>OLD.created_at) THEN
            RAISE EXCEPTION 'Dense preview lineage is immutable' USING ERRCODE='23514';
          END IF;
          IF NOT EXISTS (SELECT 1 FROM index_variants WHERE id=NEW.index_id AND state='ready'
            AND config->>'retrieval'='pgvector-exact-cosine-v1') THEN
            RAISE EXCEPTION 'Dense preview requires a ready dense index' USING ERRCODE='23514';
          END IF;
          IF NEW.state='completed' THEN
            IF TG_OP='INSERT' THEN
              RAISE EXCEPTION 'Dense preview requires execution' USING ERRCODE='23514';
            END IF;
            IF OLD.state<>'running' OR OLD.lease_expires_at IS NULL
              OR OLD.lease_expires_at<=clock_timestamp() THEN
              RAISE EXCEPTION 'Dense preview requires live ownership' USING ERRCODE='23514';
            END IF;
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER dense_preview_lineage BEFORE INSERT OR UPDATE OR DELETE ON dense_searches
          FOR EACH ROW EXECUTE FUNCTION guard_dense_search();
    """)


def downgrade() -> None:
    op.drop_table("dense_searches")
    op.execute("DROP FUNCTION guard_dense_search()")
    op.execute("DROP TRIGGER dense_publication ON index_variants")
    op.execute("DROP FUNCTION guard_dense_publication()")
    op.drop_table("chunk_embeddings")
    op.execute("DROP FUNCTION guard_chunk_embedding()")
