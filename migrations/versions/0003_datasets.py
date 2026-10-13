"""Reviewed dataset drafts and frozen question manifests."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_datasets"
down_revision = "0002_documents"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column(
            "corpus_version_id", sa.Uuid(), sa.ForeignKey("corpus_versions.id"), nullable=False
        ),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "purpose IN ('research','development_fixture')", name="ck_dataset_purpose"
        ),
    )
    op.create_table(
        "questions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content", JSONB(), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_questions_dataset", "questions", ["dataset_id", "created_at", "id"])
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column(
            "corpus_version_id", sa.Uuid(), sa.ForeignKey("corpus_versions.id"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("manifest", JSONB(), nullable=False),
        sa.Column("sealed", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("dataset_id", "version", name="uq_dataset_version"),
        sa.UniqueConstraint("dataset_id", "draft_revision", name="uq_dataset_draft_version"),
    )
    op.execute("""CREATE TRIGGER immutable_dataset_version BEFORE UPDATE OR DELETE
                  ON dataset_versions FOR EACH ROW EXECUTE FUNCTION guard_sealed_parent()""")
    op.execute("""
        CREATE FUNCTION guard_dataset_lineage() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
          IF TG_OP = 'UPDATE' AND NEW.corpus_version_id <> OLD.corpus_version_id THEN
            RAISE EXCEPTION 'Dataset corpus lineage is immutable' USING ERRCODE = '23514';
          END IF;
          IF NOT EXISTS (SELECT 1 FROM corpus_versions
                         WHERE id=NEW.corpus_version_id AND sealed) THEN
            RAISE EXCEPTION 'Dataset requires published corpus' USING ERRCODE = '23514';
          END IF;
          RETURN NEW;
        END $$;
        CREATE TRIGGER dataset_lineage BEFORE INSERT OR UPDATE ON datasets
            FOR EACH ROW EXECUTE FUNCTION guard_dataset_lineage();
    """)
    op.execute("""
        CREATE FUNCTION guard_question_evidence() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE evidence jsonb;
        BEGIN
          FOR evidence IN
            SELECT s.value FROM jsonb_array_elements(NEW.content->'evidence_groups') g(value)
              CROSS JOIN LATERAL jsonb_array_elements(g.value->'alternatives') a(value)
              CROSS JOIN LATERAL jsonb_array_elements(a.value->'spans') s(value)
          LOOP
            IF NOT EXISTS (
              SELECT 1 FROM source_sections s JOIN corpus_version_members m
                ON m.revision_id=s.revision_id JOIN datasets d ON d.corpus_version_id=m.version_id
              WHERE d.id=NEW.dataset_id AND s.id=(evidence->>'section_id')::uuid
                AND (evidence->>'start_offset')::int >= 0
                AND (evidence->>'end_offset')::int > (evidence->>'start_offset')::int
                AND (evidence->>'end_offset')::int <= char_length(s.text)
            ) THEN
              RAISE EXCEPTION 'Evidence lineage or span mismatch' USING ERRCODE = '23514';
            END IF;
          END LOOP;
          RETURN NEW;
        END $$;
        CREATE TRIGGER question_evidence BEFORE INSERT OR UPDATE ON questions
          FOR EACH ROW EXECUTE FUNCTION guard_question_evidence();
    """)


def downgrade() -> None:
    op.drop_table("dataset_versions")
    op.drop_table("questions")
    op.drop_table("datasets")
    op.execute("DROP FUNCTION guard_dataset_lineage()")
    op.execute("DROP FUNCTION guard_question_evidence()")
