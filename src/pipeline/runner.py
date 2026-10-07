"""Run isolated, retryable batch stages; publish only complete snapshots."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
from tempfile import NamedTemporaryFile
from uuid import uuid4

import pandas as pd

from src.cleaning.pipeline import clean_datasets
from src.ingestion.csv_ingestion import expected_datasets, load_datasets
from src.transformation.transformations import build_analytical_datasets, save_analytical_datasets
from src.transformation.validation import validate_analytical_datasets
from src.utils.parquet import write_verified_parquet
from .quality import quality_report, require_quality

ROOT = Path(__file__).resolve().parents[2]
STAGES = ('ingest', 'validate_raw', 'clean', 'validate_clean', 'transform',
          'validate_transformed', 'load_database', 'analytics', 'publish')
LOGGER = logging.getLogger(__name__)


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        json.dump(value, handle, indent=2, sort_keys=True)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def run_path(data_dir, run_id):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,119}', run_id):
        raise ValueError('run_id must be a safe filename of at most 120 characters')
    return Path(data_dir).resolve() / 'runs' / run_id


def read_tables(directory):
    return {name: pd.read_parquet(Path(directory) / f'{name}.parquet') for name in sorted(expected_datasets)}


def source_hashes(raw_dir):
    result = {}
    for name in sorted(expected_datasets):
        path = Path(raw_dir) / f'{name}.csv'
        with path.open('rb') as handle:
            result[path.name] = hashlib.file_digest(handle, 'sha256').hexdigest()
    return result


def run_stage(stage, run_directory, raw_dir=None, with_database=False):
    """Return only a path for Airflow XCom; data stays in shared run storage."""
    if stage not in STAGES:
        raise ValueError(f'Unknown stage: {stage}')
    run = Path(run_directory).resolve()
    if run.parent.name != 'runs':
        raise ValueError('Run directory must live directly under a data/runs directory')
    run_path(run.parent.parent, run.name)  # Validate the identifier too.
    run.mkdir(parents=True, exist_ok=True)
    settings = {'with_database': with_database}
    config_path = run / 'run_config.json'
    if config_path.exists() and json.loads(config_path.read_text()) != settings:
        raise ValueError('Run configuration changed; use a new run_id')
    if not config_path.exists():
        atomic_json(config_path, settings)
    if (run / 'completed.json').exists() and (stage != 'publish' or (run / 'publish.json').exists()):
        return str(run)  # Published snapshots are immutable; retries are no-ops.
    previous = STAGES[:STAGES.index(stage)]
    for name in previous:
        if not (run / f'{name}.json').is_file():
            raise ValueError(f'{stage} requires completed stage {name}')
    snapshot = run / 'raw_snapshot'
    processed = run / 'processed'
    reports = processed / 'reports'
    reports.mkdir(parents=True, exist_ok=True)
    LOGGER.info('Starting %s for run %s', stage, run.name)
    try:
        if stage == 'ingest':
            if raw_dir is None:
                raise ValueError('raw_dir is required for ingestion')
            hashes = source_hashes(raw_dir)
            manifest = run / 'source_manifest.json'
            if manifest.exists():
                if json.loads(manifest.read_text()) != hashes:
                    raise ValueError('Raw sources changed for this run; use a new run_id')
            else:
                tables = load_datasets(raw_dir)
                if hashes != source_hashes(raw_dir):
                    raise ValueError('Raw sources changed during ingestion')
                for name in expected_datasets:
                    write_verified_parquet(tables[name], snapshot / f'{name}.parquet')
                atomic_json(manifest, hashes)
        elif stage in {'validate_raw', 'validate_clean'}:
            cleaned = stage == 'validate_clean'
            report = quality_report(read_tables(processed if cleaned else snapshot), cleaned=cleaned)
            report.to_csv(reports / f'{stage}.csv', index=False)
            require_quality(report)
        elif stage == 'clean':
            for name, frame in clean_datasets(read_tables(snapshot)).items():
                write_verified_parquet(frame, processed / f'{name}.parquet')
        elif stage == 'transform':
            tables = read_tables(processed)
            save_analytical_datasets(tables, build_analytical_datasets(tables), processed / 'analytical')
        elif stage == 'validate_transformed':
            analytical = {name: pd.read_parquet(processed / 'analytical' / f'{name}.parquet')
                          for name in ['orders', 'customers', 'products']}
            validate_analytical_datasets(read_tables(processed), analytical).to_csv(reports / 'transformation_validation.csv', index=False)
        elif stage == 'load_database' and with_database:
            from src.database.connection import connect_database
            from src.database.loader import load_cleaned_tables, read_cleaned_tables
            from src.database.warehouse import refresh_warehouse
            with connect_database() as connection:
                # One outer transaction: source + warehouse commit together.
                with connection.transaction():
                    load_cleaned_tables(connection, read_cleaned_tables(processed), replace=True)
                    report = refresh_warehouse(connection)
            report.to_csv(reports / 'warehouse_validation.csv', index=False)
        elif stage == 'analytics':
            from src.analytics.reports import build_reports, load_data
            for name, frame in build_reports(load_data(processed)).items():
                frame.to_csv(reports / f'{name}.csv', index=False)
        elif stage == 'publish':
            atomic_json(run / 'completed.json', {'run_id': run.name, 'with_database': with_database})
            # One atomic pointer replacement makes the complete snapshot visible.
            atomic_json(run.parent.parent / 'processed' / 'CURRENT.json', {
                'version': 1, 'processed_path': f'../runs/{run.name}/processed', 'run_id': run.name,
            })
        atomic_json(run / f'{stage}.json', {'stage': stage, 'status': 'complete',
            'database_enabled': with_database, 'finished_at': datetime.now(timezone.utc).isoformat()})
    except Exception as error:
        LOGGER.error('Stage %s failed (%s); snapshot not published.', stage, type(error).__name__)
        raise
    return str(run)


def run_pipeline(data_dir=ROOT / 'data', run_id=None, with_database=False):
    run_id = run_id or f'{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid4().hex[:8]}'
    directory = run_path(data_dir, run_id)
    for stage in STAGES:
        run_stage(stage, directory, raw_dir=Path(data_dir) / 'raw', with_database=with_database)
    return directory


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-dir', type=Path, default=Path(os.environ.get('OLIST_DATA_DIR', ROOT / 'data')))
    parser.add_argument('--run-id')
    parser.add_argument('--with-database', action='store_true', help='Intentionally refresh the configured Olist database and warehouse.')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    print(run_pipeline(args.data_dir, args.run_id, args.with_database))
