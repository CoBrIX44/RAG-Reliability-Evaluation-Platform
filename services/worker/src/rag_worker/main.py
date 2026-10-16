"""Signal-aware durable worker for ingestion, indexes, previews, and experiment runs."""

import argparse
import logging
import signal
from threading import Event

from rag_core.comparisons import ComparisonQueue
from rag_core.database import create_database_engine, inspect_database, record_worker_heartbeat
from rag_core.dense_searches import DenseSearchQueue
from rag_core.evaluations import EvaluationQueue
from rag_core.exports import ExportQueue
from rag_core.indexes import IndexQueue
from rag_core.jobs import IngestionQueue
from rag_core.run_worker import RunQueue
from rag_core.settings import Settings
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger("rag.worker")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check schema readiness and exit")
    parser.add_argument(
        "--once", action="store_true", help="Process one eligible durable job and exit"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    settings = Settings()
    engine = create_database_engine(settings)
    stop = Event()
    queue = IngestionQueue(engine, settings)
    indexes = IndexQueue(engine, settings)
    previews = DenseSearchQueue(engine, settings)
    runs = RunQueue(engine, settings)
    evaluations = EvaluationQueue(engine, settings)
    comparisons = ComparisonQueue(engine, settings)
    exports = ExportQueue(engine, settings)
    next_queue = 0
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda _signum, _frame: stop.set())

    try:
        if args.check:
            health = inspect_database(engine)
            logger.info("Database readiness: %s", health.code)
            return 0 if health.status == "ready" else 1
        logger.info("Ingestion, retrieval, and experiment worker started.")
        while not stop.is_set():
            health = inspect_database(engine)
            if health.status == "ready":
                try:
                    record_worker_heartbeat(engine)
                    # Rotate queue priority to keep each kind of durable work eligible.
                    all_processors = (
                        queue,
                        indexes,
                        previews,
                        runs,
                        evaluations,
                        comparisons,
                        exports,
                    )
                    processors = all_processors[next_queue:] + all_processors[:next_queue]
                    for processor in processors:
                        if claim := processor.claim():
                            processor.process(*claim, stop)
                            break
                    next_queue = (next_queue + 1) % len(all_processors)
                except SQLAlchemyError:
                    logger.warning("Heartbeat write failed; retrying on the next poll.")
                    if args.once:
                        return 1
            else:
                logger.warning("Waiting for database: %s", health.code)
                if args.once:
                    return 1
            if args.once:
                return 0
            stop.wait(settings.worker_poll_seconds)
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
