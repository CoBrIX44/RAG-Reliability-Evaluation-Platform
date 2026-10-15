"""Independent immutable answer reviews and fenced local judge jobs."""

from alembic import op

revision = "0008_answer_evaluations"
down_revision = "0007_experiment_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE TABLE answer_evaluations (
        id uuid PRIMARY KEY, result_id uuid NOT NULL REFERENCES question_results(id),
        kind varchar(16) NOT NULL CHECK(kind IN ('human','model')),
        request_key varchar(128) NOT NULL UNIQUE, reviewer varchar(160),
        manifest jsonb NOT NULL, manifest_hash varchar(64) NOT NULL,
        state varchar(16) NOT NULL CHECK(state IN ('pending','running','completed','failed')),
        output jsonb, attempts integer NOT NULL CHECK(attempts>=0),
        max_attempts integer NOT NULL CHECK(max_attempts BETWEEN 1 AND 10),
        lease_token uuid, lease_expires_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(),
        CHECK((state='running')=(lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)),
        CHECK((kind='human' AND reviewer IS NOT NULL AND state='completed') OR
              (kind='model' AND reviewer IS NULL)),
        CHECK((state IN ('completed','failed'))=(output IS NOT NULL))
      );
      CREATE INDEX ix_answer_evaluations_result ON answer_evaluations(result_id,created_at,id);
      CREATE INDEX ix_answer_evaluations_queue ON answer_evaluations(state,created_at,id);
      CREATE FUNCTION guard_answer_evaluation() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP='DELETE' THEN
          RAISE EXCEPTION 'Evaluations are retained' USING ERRCODE='23514';
        END IF;
        IF TG_OP='INSERT' THEN
          IF NOT EXISTS (SELECT 1 FROM question_results q JOIN runs r ON r.id=q.run_id
            WHERE q.id=NEW.result_id AND q.state='succeeded'
            AND NEW.manifest->>'result_id'=q.id::text
            AND NEW.manifest->>'run_manifest_hash'=r.manifest_hash
            AND NEW.manifest->'inputs'->>'answer'=q.trace->'generation'->>'answer'
            AND NEW.manifest->'inputs'->>'question'=q.trace->'question'->'content'->>'text'
            AND NEW.manifest->'inputs'->'answerable'=q.trace->'question'->'content'->'answerable'
            AND NEW.manifest->'inputs'->'reference_answer'
                =q.trace->'question'->'content'->'reference_answer'
            AND NEW.manifest->'inputs'->'required_facts'
                =q.trace->'question'->'content'->'required_facts'
            AND NEW.manifest->'inputs'->'evidence'=COALESCE((SELECT jsonb_agg(
              jsonb_build_object('citation','P'||ord::text,'text',p->>'text') ORDER BY ord)
              FROM jsonb_array_elements(q.trace->'generation'->'context'->'passages')
                WITH ORDINALITY a(p,ord)), '[]'::jsonb)
            AND NEW.manifest->'rubric'->>'version'='answer-evidence-v1') THEN
            RAISE EXCEPTION 'Evaluation lineage mismatch' USING ERRCODE='23514';
          END IF;
          IF NOT ((NEW.kind='model' AND NEW.state='pending' AND NEW.attempts=0) OR
                  (NEW.kind='human' AND NEW.state='completed' AND NEW.attempts=0)) THEN
            RAISE EXCEPTION 'Invalid evaluation submission' USING ERRCODE='23514';
          END IF;
        ELSE
          IF OLD.state IN ('completed','failed') OR
             ROW(NEW.id,NEW.result_id,NEW.kind,NEW.request_key,NEW.reviewer,NEW.manifest,
                 NEW.manifest_hash,NEW.max_attempts,NEW.created_at)
             IS DISTINCT FROM
             ROW(OLD.id,OLD.result_id,OLD.kind,OLD.request_key,OLD.reviewer,OLD.manifest,
                 OLD.manifest_hash,OLD.max_attempts,OLD.created_at) THEN
            RAISE EXCEPTION 'Evaluation inputs and terminal records are immutable'
              USING ERRCODE='23514';
          END IF;
          IF NEW.state IN ('completed','failed') AND
             (OLD.state<>'running' OR OLD.lease_expires_at<=clock_timestamp()) THEN
            RAISE EXCEPTION 'Evaluation publication requires live ownership' USING ERRCODE='23514';
          END IF;
        END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER answer_evaluation_guard BEFORE INSERT OR UPDATE OR DELETE
        ON answer_evaluations FOR EACH ROW EXECUTE FUNCTION guard_answer_evaluation();
    """)


def downgrade() -> None:
    op.execute("DROP TABLE answer_evaluations; DROP FUNCTION guard_answer_evaluation();")
