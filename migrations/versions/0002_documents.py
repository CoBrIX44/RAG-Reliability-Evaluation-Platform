"""Document drafts, ingestion jobs, canonical evidence, and sealed snapshots."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0002_documents"
down_revision = "0001_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "corpora",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("corpus_id", sa.Uuid(), sa.ForeignKey("corpora.id"), nullable=False),
        sa.Column("filename", sa.String(240), nullable=False),
        sa.Column("media_type", sa.String(80), nullable=False),
        sa.Column("storage_key", sa.String(160), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("byte_count", sa.BigInteger(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("corpus_id", "checksum", name="uq_document_corpus_checksum"),
        sa.CheckConstraint(
            "state IN ('pending','processing','ready','failed')", name="ck_document_state"
        ),
        sa.CheckConstraint("byte_count > 0", name="ck_document_size"),
    )
    op.create_index("ix_documents_corpus_created", "documents", ["corpus_id", "created_at", "id"])
    op.create_table(
        "document_revisions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False, unique=True
        ),
        sa.Column("extractor_version", sa.String(80), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("section_count", sa.Integer(), nullable=False),
        sa.Column("character_count", sa.BigInteger(), nullable=False),
        sa.Column("sealed", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "source_sections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("revision_id", sa.Uuid(), sa.ForeignKey("document_revisions.id"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading_path", pg.JSONB(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.BigInteger(), nullable=False),
        sa.Column("end_offset", sa.BigInteger(), nullable=False),
        sa.Column("source", pg.JSONB(), nullable=False),
        sa.UniqueConstraint("revision_id", "ordinal", name="uq_section_revision_ordinal"),
        sa.CheckConstraint("end_offset >= start_offset", name="ck_section_offsets"),
    )
    op.create_table(
        "corpus_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("corpus_id", sa.Uuid(), sa.ForeignKey("corpora.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("manifest", pg.JSONB(), nullable=False),
        sa.Column("document_count", sa.Integer(), nullable=False),
        sa.Column("sealed", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("corpus_id", "version", name="uq_corpus_version"),
        sa.UniqueConstraint("corpus_id", "draft_revision", name="uq_corpus_draft_version"),
    )
    op.create_table(
        "corpus_version_members",
        sa.Column("version_id", sa.Uuid(), sa.ForeignKey("corpus_versions.id"), primary_key=True),
        sa.Column(
            "revision_id", sa.Uuid(), sa.ForeignKey("document_revisions.id"), primary_key=True
        ),
    )
    op.create_table(
        "jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id", sa.Uuid(), sa.ForeignKey("documents.id"), nullable=False, unique=True
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("lease_token", sa.Uuid()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("checkpoint", pg.JSONB()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("attempts >= 0 AND max_attempts > 0", name="ck_job_attempts"),
        sa.CheckConstraint(
            "state IN ('pending','running','succeeded','failed')", name="ck_job_state"
        ),
    )
    op.create_index("ix_jobs_claim", "jobs", ["state", "available_at", "lease_expires_at"])
    # Insert members only during the parent's unsealed construction transaction.
    # A sealed parent may never change, and its children cannot be appended or edited.
    op.execute("""
        CREATE FUNCTION guard_sealed_parent() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'UPDATE' AND NOT OLD.sealed AND NEW.sealed
             AND (to_jsonb(OLD) - 'sealed') = (to_jsonb(NEW) - 'sealed') THEN
            RETURN NEW;
          END IF;
          RAISE EXCEPTION 'Published evidence is immutable' USING ERRCODE = '23514';
        END $$;
    """)
    for table in ("document_revisions", "corpus_versions"):
        op.execute(f"""CREATE TRIGGER immutable_parent BEFORE UPDATE OR DELETE ON {table}
                    FOR EACH ROW EXECUTE FUNCTION guard_sealed_parent()""")
    op.execute("""
        CREATE FUNCTION guard_evidence_child() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE parent_sealed boolean;
        BEGIN
          IF TG_OP <> 'INSERT' THEN
            RAISE EXCEPTION 'Published evidence is immutable' USING ERRCODE = '23514';
          END IF;
          IF TG_TABLE_NAME = 'source_sections' THEN
            SELECT sealed INTO parent_sealed FROM document_revisions
                WHERE id = NEW.revision_id FOR SHARE;
          ELSE
            SELECT sealed INTO parent_sealed FROM corpus_versions
                WHERE id = NEW.version_id FOR SHARE;
            IF NOT EXISTS (
                SELECT 1 FROM document_revisions r JOIN documents d ON d.id = r.document_id
                JOIN corpus_versions v ON v.corpus_id = d.corpus_id
                WHERE r.id = NEW.revision_id AND v.id = NEW.version_id AND r.sealed
            ) THEN
                RAISE EXCEPTION 'Evidence lineage mismatch' USING ERRCODE = '23514';
            END IF;
          END IF;
          IF parent_sealed IS DISTINCT FROM false THEN
            RAISE EXCEPTION 'Published evidence is immutable' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END $$;
    """)
    for table in ("source_sections", "corpus_version_members"):
        op.execute(f"""CREATE TRIGGER immutable_child BEFORE INSERT OR UPDATE OR DELETE ON {table}
                    FOR EACH ROW EXECUTE FUNCTION guard_evidence_child()""")


def downgrade() -> None:
    for table in (
        "jobs",
        "corpus_version_members",
        "corpus_versions",
        "source_sections",
        "document_revisions",
        "documents",
        "corpora",
    ):
        op.drop_table(table)
    op.execute("DROP FUNCTION guard_evidence_child()")
    op.execute("DROP FUNCTION guard_sealed_parent()")
