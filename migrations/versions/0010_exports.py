"""Frozen export selections and durable artifact ownership; existing sources stay immutable."""

from alembic import op

revision = "0010_exports"
down_revision = "0009_comparisons"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE TABLE export_jobs (
        id uuid PRIMARY KEY, run_id uuid REFERENCES runs(id),
        comparison_id uuid REFERENCES comparisons(id),
        request_key varchar(128) NOT NULL UNIQUE, manifest jsonb NOT NULL,
        manifest_hash varchar(64) NOT NULL,
        state varchar(16) NOT NULL CHECK(state IN ('pending','running','completed','failed')),
        output jsonb, attempts integer NOT NULL CHECK(attempts>=0),
        max_attempts integer NOT NULL CHECK(max_attempts BETWEEN 1 AND 10),
        lease_token uuid, lease_expires_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(),
        CHECK((run_id IS NULL)<>(comparison_id IS NULL)),
        CHECK((state='running')=(lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)),
        CHECK((state IN ('completed','failed'))=(output IS NOT NULL))
      );
      CREATE INDEX ix_export_queue ON export_jobs(state,created_at,id);
      CREATE FUNCTION guard_export() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP='DELETE' THEN
          RAISE EXCEPTION 'Exports are retained' USING ERRCODE='23514';
        END IF;
        IF TG_OP='INSERT' THEN
          IF NEW.state<>'pending' OR NEW.attempts<>0 OR NOT (
            EXISTS (SELECT 1 FROM runs r WHERE r.id=NEW.run_id
              AND NEW.manifest->>'source_id'=r.id::text
              AND NEW.manifest->>'source_hash'=r.manifest_hash
              AND r.state IN ('completed','completed_with_errors','failed','cancelled')) OR
            EXISTS (SELECT 1 FROM comparisons c WHERE c.id=NEW.comparison_id
              AND NEW.manifest->>'source_id'=c.id::text
              AND NEW.manifest->>'source_hash'=c.manifest_hash
              AND c.state IN ('completed','failed'))
          ) THEN
            RAISE EXCEPTION 'Export lineage or terminal source mismatch' USING ERRCODE='23514';
          END IF;
        ELSE
          IF OLD.state IN ('completed','failed') OR
            ROW(NEW.id,NEW.run_id,NEW.comparison_id,NEW.request_key,NEW.manifest,NEW.manifest_hash,
                NEW.max_attempts,NEW.created_at)
            IS DISTINCT FROM
            ROW(OLD.id,OLD.run_id,OLD.comparison_id,OLD.request_key,OLD.manifest,OLD.manifest_hash,
                OLD.max_attempts,OLD.created_at) THEN
            RAISE EXCEPTION 'Export inputs and terminal artifacts are immutable'
              USING ERRCODE='23514';
          END IF;
          IF NEW.state IN ('completed','failed') AND
             (OLD.state<>'running' OR OLD.lease_expires_at<=clock_timestamp()) THEN
            RAISE EXCEPTION 'Export publication needs live ownership' USING ERRCODE='23514';
          END IF;
        END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER export_guard BEFORE INSERT OR UPDATE OR DELETE ON export_jobs
        FOR EACH ROW EXECUTE FUNCTION guard_export();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE export_jobs; DROP FUNCTION guard_export();")
