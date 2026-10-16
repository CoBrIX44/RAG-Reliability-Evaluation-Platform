"""Frozen paired analysis snapshots and fenced immutable report publication."""

from alembic import op

revision = "0009_comparisons"
down_revision = "0008_answer_evaluations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE TABLE comparisons (
        id uuid PRIMARY KEY, baseline_run_id uuid NOT NULL REFERENCES runs(id),
        candidate_run_id uuid NOT NULL REFERENCES runs(id),
        request_key varchar(128) NOT NULL UNIQUE, manifest jsonb NOT NULL,
        manifest_hash varchar(64) NOT NULL,
        state varchar(16) NOT NULL CHECK(state IN ('pending','running','completed','failed')),
        output jsonb, attempts integer NOT NULL CHECK(attempts>=0),
        max_attempts integer NOT NULL CHECK(max_attempts BETWEEN 1 AND 10),
        lease_token uuid, lease_expires_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(),
        CHECK(baseline_run_id<>candidate_run_id),
        CHECK((state='running')=(lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)),
        CHECK((state IN ('completed','failed'))=(output IS NOT NULL))
      );
      CREATE INDEX ix_comparison_queue ON comparisons(state,created_at,id);
      CREATE FUNCTION guard_comparison() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP='DELETE' THEN
          RAISE EXCEPTION 'Comparisons are retained' USING ERRCODE='23514';
        END IF;
        IF TG_OP='INSERT' THEN
          IF NEW.state<>'pending' OR NEW.attempts<>0 OR NOT EXISTS (
            SELECT 1 FROM runs a JOIN runs b ON b.id=NEW.candidate_run_id
            WHERE a.id=NEW.baseline_run_id
            AND NEW.manifest->'baseline'->>'id'=a.id::text
            AND NEW.manifest->'candidate'->>'id'=b.id::text
            AND NEW.manifest->'baseline'->>'manifest_hash'=a.manifest_hash
            AND NEW.manifest->'candidate'->>'manifest_hash'=b.manifest_hash
          ) THEN
            RAISE EXCEPTION 'Comparison run lineage mismatch' USING ERRCODE='23514';
          END IF;
        ELSE
          IF OLD.state IN ('completed','failed') OR
            ROW(NEW.id,NEW.baseline_run_id,NEW.candidate_run_id,NEW.request_key,NEW.manifest,
                NEW.manifest_hash,NEW.created_at,NEW.max_attempts)
            IS DISTINCT FROM
            ROW(OLD.id,OLD.baseline_run_id,OLD.candidate_run_id,OLD.request_key,OLD.manifest,
                OLD.manifest_hash,OLD.created_at,OLD.max_attempts) THEN
            RAISE EXCEPTION 'Comparison inputs and terminal reports are immutable'
              USING ERRCODE='23514';
          END IF;
          IF NEW.state IN ('completed','failed') AND
             (OLD.state<>'running' OR OLD.lease_expires_at<=clock_timestamp()) THEN
            RAISE EXCEPTION 'Comparison requires live publication ownership' USING ERRCODE='23514';
          END IF;
        END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER comparison_guard BEFORE INSERT OR UPDATE OR DELETE ON comparisons
        FOR EACH ROW EXECUTE FUNCTION guard_comparison();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE comparisons; DROP FUNCTION guard_comparison();")
