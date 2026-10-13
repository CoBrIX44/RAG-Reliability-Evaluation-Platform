"""Immutable experiments and per-question publication fenced by durable run ownership."""

from alembic import op

revision = "0007_experiment_runs"
down_revision = "0006_dense_retrieval"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      CREATE TABLE experiments (
        id uuid PRIMARY KEY, name varchar(160) NOT NULL,
        dataset_version_id uuid NOT NULL REFERENCES dataset_versions(id),
        index_id uuid NOT NULL REFERENCES index_variants(id),
        fingerprint varchar(64) NOT NULL UNIQUE, config jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
      );
      CREATE TABLE runs (
        id uuid PRIMARY KEY, experiment_id uuid NOT NULL REFERENCES experiments(id),
        idempotency_key varchar(128) NOT NULL, manifest jsonb NOT NULL,
        manifest_hash varchar(64) NOT NULL, state varchar(32) NOT NULL,
        cancel_requested boolean NOT NULL, total_count integer NOT NULL CHECK(total_count>0),
        attempts integer NOT NULL CHECK(attempts>=0),
        max_attempts integer NOT NULL CHECK(max_attempts BETWEEN 1 AND 10),
        available_at timestamptz NOT NULL DEFAULT now(), lease_token uuid,
        lease_expires_at timestamptz, error_code varchar(80), error_message text,
        started_at timestamptz, finished_at timestamptz,
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(idempotency_key),
        CHECK(state IN ('queued','running','completed','completed_with_errors',
                        'failed','cancelled')),
        CHECK((state='running')=(lease_token IS NOT NULL AND lease_expires_at IS NOT NULL))
      );
      CREATE INDEX ix_runs_queue ON runs(state,available_at,created_at);
      CREATE TABLE question_results (
        id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES runs(id),
        question_id uuid NOT NULL, question_revision integer NOT NULL CHECK(question_revision>=1),
        repeat integer NOT NULL CHECK(repeat>=0), state varchar(16) NOT NULL,
        trace jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE(run_id,question_id,repeat), CHECK(state IN ('succeeded','failed'))
      );
      CREATE TABLE run_attempts (
        id uuid PRIMARY KEY, run_id uuid NOT NULL REFERENCES runs(id), question_id uuid NOT NULL,
        repeat integer NOT NULL CHECK(repeat>=0), ordinal integer NOT NULL CHECK(ordinal>=1),
        lease_token uuid NOT NULL, state varchar(16) NOT NULL,
        trace jsonb NOT NULL, error_code varchar(80), started_at timestamptz NOT NULL DEFAULT now(),
        finished_at timestamptz, UNIQUE(run_id,question_id,repeat,ordinal),
        CHECK(state IN ('started','completed','failed','interrupted','cancelled'))
      );
      CREATE FUNCTION guard_experiment() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP<>'INSERT' THEN
          RAISE EXCEPTION 'Experiments are immutable' USING ERRCODE='23514';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM dataset_versions d JOIN index_variants i
          ON i.corpus_version_id=d.corpus_version_id WHERE d.id=NEW.dataset_version_id
          AND d.sealed AND i.id=NEW.index_id AND i.state='ready') THEN
          RAISE EXCEPTION 'Experiment input lineage mismatch' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER experiment_immutable BEFORE INSERT OR UPDATE OR DELETE ON experiments
        FOR EACH ROW EXECUTE FUNCTION guard_experiment();
      CREATE FUNCTION guard_run() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF TG_OP='INSERT' AND NOT EXISTS (
          SELECT 1 FROM experiments e JOIN dataset_versions d ON d.id=e.dataset_version_id
          JOIN index_variants i ON i.id=e.index_id WHERE e.id=NEW.experiment_id
          AND NEW.state='queued' AND NEW.manifest->'config'=e.config
          AND NEW.manifest->>'dataset_version_id'=d.id::text
          AND NEW.manifest->>'dataset_hash'=d.manifest_hash
          AND NEW.manifest->>'index_id'=i.id::text
          AND NEW.manifest->'index_manifest'=i.manifest
          AND NEW.manifest->>'corpus_version_id'=d.corpus_version_id::text
          AND NEW.manifest->>'purpose'=d.manifest->>'purpose'
          AND NEW.manifest->>'experiment_id'=e.id::text
          AND jsonb_typeof(NEW.manifest->'questions')='array'
          AND jsonb_array_length(NEW.manifest->'questions')>0
          AND NEW.manifest->'questions'=(SELECT jsonb_agg(q ORDER BY ord)
            FROM jsonb_array_elements(d.manifest->'questions') WITH ORDINALITY a(q,ord)
            WHERE q->'content'->>'split'=e.config->>'split')
          AND NEW.total_count=jsonb_array_length(NEW.manifest->'questions')
            *(e.config->>'repeats')::int
        ) THEN
          RAISE EXCEPTION 'Run manifest input lineage mismatch' USING ERRCODE='23514';
        END IF;
        IF TG_OP='DELETE' THEN
          RAISE EXCEPTION 'Runs cannot be deleted' USING ERRCODE='23514';
        END IF;
        IF TG_OP='UPDATE' AND (NEW.id<>OLD.id OR NEW.experiment_id<>OLD.experiment_id
          OR NEW.idempotency_key<>OLD.idempotency_key OR NEW.manifest<>OLD.manifest
          OR NEW.manifest_hash<>OLD.manifest_hash OR NEW.total_count<>OLD.total_count
          OR NEW.created_at<>OLD.created_at OR (OLD.cancel_requested AND NOT NEW.cancel_requested)
          OR OLD.state IN ('completed','completed_with_errors','failed','cancelled')) THEN
          RAISE EXCEPTION 'Run inputs or terminal state are immutable' USING ERRCODE='23514';
        END IF;
        IF NEW.state IN ('completed','completed_with_errors') THEN
          IF TG_OP='INSERT' THEN
            RAISE EXCEPTION 'Run requires worker execution' USING ERRCODE='23514';
          END IF;
          IF OLD.state<>'running' OR OLD.lease_expires_at<=clock_timestamp()
            OR NEW.total_count<>(SELECT count(*) FROM question_results WHERE run_id=NEW.id) THEN
            RAISE EXCEPTION 'Run publication is incomplete or stale' USING ERRCODE='23514';
          END IF;
        END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER run_lineage BEFORE INSERT OR UPDATE OR DELETE ON runs
        FOR EACH ROW EXECUTE FUNCTION guard_run();
      CREATE FUNCTION guard_question_result() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE parent runs%ROWTYPE; planned jsonb;
      BEGIN
        IF TG_OP<>'INSERT' THEN
          RAISE EXCEPTION 'Question results are immutable' USING ERRCODE='23514';
        END IF;
        SELECT * INTO parent FROM runs WHERE id=NEW.run_id FOR UPDATE;
        IF parent.state<>'running' OR parent.cancel_requested
          OR parent.lease_expires_at IS NULL
          OR parent.lease_expires_at<=clock_timestamp() THEN
          RAISE EXCEPTION 'Result requires a live uncancelled run' USING ERRCODE='23514';
        END IF;
        SELECT value INTO planned FROM jsonb_array_elements(parent.manifest->'questions')
          WHERE value->>'id'=NEW.question_id::text;
        IF planned IS NULL OR NEW.trace->'question' IS DISTINCT FROM planned
          OR (planned->>'revision')::int<>NEW.question_revision
          OR NEW.repeat>=(parent.manifest->'config'->>'repeats')::int THEN
          RAISE EXCEPTION 'Result question lineage mismatch' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER question_result_lineage BEFORE INSERT OR UPDATE OR DELETE ON question_results
        FOR EACH ROW EXECUTE FUNCTION guard_question_result();
      CREATE FUNCTION guard_run_attempt() RETURNS trigger LANGUAGE plpgsql AS $$
      DECLARE parent runs%ROWTYPE;
      BEGIN
        IF TG_OP='DELETE' THEN
          RAISE EXCEPTION 'Attempts cannot be deleted' USING ERRCODE='23514';
        END IF;
        SELECT * INTO parent FROM runs WHERE id=NEW.run_id FOR UPDATE;
        IF parent.state<>'running' OR parent.lease_expires_at IS NULL
          OR parent.lease_expires_at<=clock_timestamp() THEN
          RAISE EXCEPTION 'Attempt requires live run ownership' USING ERRCODE='23514';
        END IF;
        IF TG_OP='INSERT' AND (NEW.lease_token<>parent.lease_token OR parent.cancel_requested
          OR NEW.state<>'started' OR NOT EXISTS (
            SELECT 1 FROM jsonb_array_elements(parent.manifest->'questions') q
              WHERE q->>'id'=NEW.question_id::text)
          OR NEW.repeat>=(parent.manifest->'config'->>'repeats')::int) THEN
          RAISE EXCEPTION 'Attempt lineage mismatch' USING ERRCODE='23514';
        END IF;
        IF TG_OP='UPDATE' AND (OLD.state<>'started' OR NEW.id<>OLD.id OR NEW.run_id<>OLD.run_id
          OR NEW.question_id<>OLD.question_id OR NEW.repeat<>OLD.repeat OR NEW.ordinal<>OLD.ordinal
          OR NEW.lease_token<>OLD.lease_token OR NEW.started_at<>OLD.started_at
          OR (NEW.state IN ('completed','failed','started')
              AND OLD.lease_token<>parent.lease_token)
          OR (NEW.state IN ('interrupted','cancelled') AND NEW.trace<>OLD.trace)) THEN
          RAISE EXCEPTION 'Attempt update is stale or immutable' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END $$;
      CREATE TRIGGER run_attempt_lineage BEFORE INSERT OR UPDATE OR DELETE ON run_attempts
        FOR EACH ROW EXECUTE FUNCTION guard_run_attempt();
    """)


def downgrade() -> None:
    for table in ("run_attempts", "question_results", "runs", "experiments"):
        op.drop_table(table)
    for name in ("guard_run_attempt", "guard_question_result", "guard_run", "guard_experiment"):
        op.execute(f"DROP FUNCTION {name}()")
