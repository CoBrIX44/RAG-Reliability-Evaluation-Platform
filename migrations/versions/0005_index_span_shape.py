"""Reject null, noninteger, overlapping, and unordered chunk annotations at the SQL boundary."""

from alembic import op

revision = "0005_index_span_shape"
down_revision = "0004_lexical_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION guard_index_span_shape() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE annotation jsonb; field text; previous_end bigint := 0;
        BEGIN
          IF jsonb_typeof(NEW.spans)<>'array' OR jsonb_array_length(NEW.spans)=0 THEN
            RAISE EXCEPTION 'Chunk requires canonical spans' USING ERRCODE='23514';
          END IF;
          FOR annotation IN SELECT value FROM jsonb_array_elements(NEW.spans) LOOP
            FOREACH field IN ARRAY ARRAY['start_offset','end_offset','text_start','text_end'] LOOP
              IF COALESCE(jsonb_typeof(annotation->field),'missing')<>'number'
                OR (annotation->>field) !~ '^[0-9]+$' THEN
                RAISE EXCEPTION 'Chunk offsets require nonnegative integers' USING ERRCODE='23514';
              END IF;
            END LOOP;
            IF (annotation->>'text_start')::bigint < previous_end THEN
              RAISE EXCEPTION 'Chunk spans must be ordered and disjoint' USING ERRCODE='23514';
            END IF;
            previous_end := (annotation->>'text_end')::bigint;
          END LOOP;
          RETURN NEW;
        END $$;
        CREATE TRIGGER chunk_annotation_shape BEFORE INSERT ON index_chunks
          FOR EACH ROW EXECUTE FUNCTION guard_index_span_shape();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER chunk_annotation_shape ON index_chunks")
    op.execute("DROP FUNCTION guard_index_span_shape()")
