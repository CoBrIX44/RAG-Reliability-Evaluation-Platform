"""Durable lexical index variants and immutable source-linked chunks."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

revision = "0004_lexical_indexes"
down_revision = "0003_datasets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "index_variants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "corpus_version_id", sa.Uuid(), sa.ForeignKey("corpus_versions.id"), nullable=False
        ),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("config", JSONB(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False),
        sa.Column("manifest", JSONB()),
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
        sa.CheckConstraint(
            "state IN ('pending','running','ready','failed')", name="ck_index_state"
        ),
        sa.CheckConstraint(
            "attempts >= 0 AND max_attempts BETWEEN 1 AND 10 AND chunk_count >= 0",
            name="ck_index_counts",
        ),
    )
    op.create_index("ix_index_queue", "index_variants", ["state", "available_at", "created_at"])
    op.create_table(
        "index_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("index_id", sa.Uuid(), sa.ForeignKey("index_variants.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("spans", JSONB(), nullable=False),
        sa.Column(
            "search_vector",
            TSVECTOR(),
            sa.Computed("to_tsvector('english'::regconfig, text)", persisted=True),
        ),
        sa.UniqueConstraint("index_id", "ordinal", name="uq_index_chunk_ordinal"),
        sa.CheckConstraint(
            "ordinal >= 0 AND token_count >= 0 AND char_length(text) > 0", name="ck_chunk_counts"
        ),
    )
    op.create_index("ix_chunk_fts", "index_chunks", ["search_vector"], postgresql_using="gin")
    op.execute("""
        CREATE FUNCTION guard_index_variant() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Index variants cannot be deleted' USING ERRCODE='23514';
          END IF;
          IF TG_OP = 'UPDATE' AND (OLD.state='ready' OR NEW.id<>OLD.id
            OR NEW.corpus_version_id<>OLD.corpus_version_id OR NEW.config<>OLD.config
            OR NEW.fingerprint<>OLD.fingerprint OR NEW.created_at<>OLD.created_at) THEN
            RAISE EXCEPTION 'Index lineage is immutable' USING ERRCODE='23514';
          END IF;
          IF NOT EXISTS (SELECT 1 FROM corpus_versions
                         WHERE id=NEW.corpus_version_id AND sealed) THEN
            RAISE EXCEPTION 'Index requires a published corpus' USING ERRCODE='23514';
          END IF;
          IF NEW.state='ready' THEN
            IF TG_OP='INSERT' THEN
              RAISE EXCEPTION 'Index must be built before publication' USING ERRCODE='23514';
            END IF;
            IF OLD.state<>'running' OR OLD.lease_expires_at IS NULL
              OR OLD.lease_expires_at<=clock_timestamp() OR NEW.manifest IS NULL
              OR NEW.chunk_count=0 OR NEW.chunk_count <>
                (SELECT count(*) FROM index_chunks WHERE index_id=NEW.id) THEN
              RAISE EXCEPTION 'Index publication is incomplete' USING ERRCODE='23514';
            END IF;
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER index_lineage BEFORE INSERT OR UPDATE OR DELETE ON index_variants
          FOR EACH ROW EXECUTE FUNCTION guard_index_variant();
        CREATE FUNCTION guard_index_chunk() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE cv uuid; annotation jsonb; source_text text; parent_state text; expiry timestamptz;
        BEGIN
          IF TG_OP <> 'INSERT' THEN
            RAISE EXCEPTION 'Index chunks are immutable' USING ERRCODE='23514';
          END IF;
          SELECT corpus_version_id,state,lease_expires_at INTO cv,parent_state,expiry
            FROM index_variants WHERE id=NEW.index_id FOR UPDATE;
          IF parent_state <> 'running' OR expiry IS NULL OR expiry <= clock_timestamp() THEN
            RAISE EXCEPTION 'Chunk build requires a live lease' USING ERRCODE='23514';
          END IF;
          IF jsonb_typeof(NEW.spans)<>'array' OR jsonb_array_length(NEW.spans)=0 THEN
            RAISE EXCEPTION 'Chunk requires canonical spans' USING ERRCODE='23514';
          END IF;
          FOR annotation IN SELECT value FROM jsonb_array_elements(NEW.spans) LOOP
            IF NOT annotation ?& ARRAY['section_id','start_offset','end_offset',
                                      'text_start','text_end'] THEN
              RAISE EXCEPTION 'Incomplete chunk source lineage' USING ERRCODE='23514';
            END IF;
            SELECT s.text INTO source_text FROM source_sections s
              JOIN corpus_version_members m ON m.revision_id=s.revision_id
              WHERE m.version_id=cv AND s.id=(annotation->>'section_id')::uuid;
            IF source_text IS NULL OR (annotation->>'start_offset')::int < 0
              OR (annotation->>'end_offset')::int > char_length(source_text)
              OR (annotation->>'end_offset')::int <= (annotation->>'start_offset')::int
              OR (annotation->>'text_start')::int < 0
              OR (annotation->>'text_end')::int > char_length(NEW.text)
              OR (annotation->>'text_end')::int - (annotation->>'text_start')::int
                 <> (annotation->>'end_offset')::int - (annotation->>'start_offset')::int
              OR substring(source_text FROM (annotation->>'start_offset')::int+1
                  FOR (annotation->>'end_offset')::int-(annotation->>'start_offset')::int)
                 <> substring(NEW.text FROM (annotation->>'text_start')::int+1
                  FOR (annotation->>'text_end')::int-(annotation->>'text_start')::int) THEN
              RAISE EXCEPTION 'Invalid chunk source lineage' USING ERRCODE='23514';
            END IF;
          END LOOP;
          RETURN NEW;
        END $$;
        CREATE TRIGGER chunk_lineage BEFORE INSERT OR UPDATE OR DELETE ON index_chunks
          FOR EACH ROW EXECUTE FUNCTION guard_index_chunk();
    """)


def downgrade() -> None:
    op.drop_table("index_chunks")
    op.drop_table("index_variants")
    op.execute("DROP FUNCTION guard_index_chunk()")
    op.execute("DROP FUNCTION guard_index_variant()")
