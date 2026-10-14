"""Store a static retrieval corpus in PostgreSQL; restore without embedding API calls.

Operator commands: export FILE, publish FILE. No public upload endpoint.
Run export after ingest finishes; publish uses the configured PostgreSQL database.
"""
import argparse
import gzip
import hashlib
import json
import os
import math
import tempfile
from contextlib import ExitStack
from itertools import islice
from pathlib import Path

import chromadb
import ijson
from settings import chroma_directory
from database import get_db_connection

MODEL = 'text-embedding-3-small'
COLLECTION = 'langchain'
BATCH_SIZE = 128
COLUMNS = ('ids', 'documents', 'metadatas', 'embeddings')


def collection(directory):
    return chromadb.PersistentClient(path=str(directory)).get_or_create_collection(
        COLLECTION, embedding_function=None)


def export_snapshot(directory):
    rows = collection(directory).get(include=['documents', 'metadatas', 'embeddings'])
    if not rows['ids']:
        raise RuntimeError('Cannot export an empty Chroma collection')
    payload = {key: rows[key] for key in ('ids', 'documents', 'metadatas')}
    payload.update(version=1, model=MODEL, embeddings=rows['embeddings'].tolist())
    return gzip.compress(json.dumps(payload, ensure_ascii=False).encode('utf-8'), mtime=0)


def decode_snapshot(blob):
    # Operator-side export/publish validation. Server startup uses the streaming
    # path below, never this whole-document decoder.
    data = json.loads(gzip.decompress(blob))
    if data.get('version') != 1 or data.get('model') != MODEL:
        raise RuntimeError('Unsupported snapshot format or embedding model')
    count = len(data['ids'])
    if not count or len(set(data['ids'])) != count or any(
            len(data[key]) != count for key in ('documents', 'metadatas', 'embeddings')):
        raise RuntimeError('Invalid snapshot record counts')
    if any(len(vector) != 1536 for vector in data['embeddings']):
        raise RuntimeError('Snapshot must use 1536-dimensional embeddings')
    for meta in data['metadatas']:
        if (not meta or not {'source', 'page', 'permission'} <= meta.keys()
                or meta['permission'] not in ('EMPLOYEE', 'SECURITY', 'ADMIN')):
            raise RuntimeError('Snapshot is missing source or permission metadata')
    return data


def publish_snapshot(blob):
    decode_snapshot(blob)
    digest = hashlib.sha256(blob).hexdigest()
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute('''CREATE TABLE IF NOT EXISTS rag_snapshot (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    sha256 TEXT NOT NULL, payload BYTEA NOT NULL)''')
                cur.execute('''INSERT INTO rag_snapshot VALUES (1, %s, %s)
                    ON CONFLICT (id) DO UPDATE SET sha256=EXCLUDED.sha256,
                    payload=EXCLUDED.payload''', (digest, blob))
    finally:
        conn.close()


def _read_value(events, first):
    """Build one array item, not the snapshot's complete top-level arrays."""
    builder = ijson.common.ObjectBuilder()
    event, value = first
    builder.event(event, value)
    depth = int(event in ('start_map', 'start_array'))
    while depth:
        _, event, value = next(events)
        builder.event(event, value)
        depth += int(event in ('start_map', 'start_array'))
        depth -= int(event in ('end_map', 'end_array'))
    return builder.value


def _validate_item(column, value):
    if column in ('ids', 'documents') and not isinstance(value, str):
        raise RuntimeError('Snapshot IDs and documents must be strings')
    if column == 'ids' and not value:
        raise RuntimeError('Snapshot ID must not be empty')
    if column == 'metadatas':
        if (not isinstance(value, dict) or not {'source', 'page', 'permission'} <= value.keys()
                or value['permission'] not in ('EMPLOYEE', 'SECURITY', 'ADMIN')):
            raise RuntimeError('Snapshot is missing source or permission metadata')
    if column == 'embeddings':
        if (not isinstance(value, list) or len(value) != 1536
                or any(type(x) not in (int, float) or not math.isfinite(x) for x in value)):
            raise RuntimeError('Snapshot must use finite 1536-dimensional embeddings')


def _spool_snapshot(path, spool):
    """Validate the unchanged v1 format before touching Chroma.

    Top-level arrays may occur in any order. Split them into temporary JSONL
    files so only one vector/record is parsed at once. These files contain
    document text and live only inside a private TemporaryDirectory.
    """
    header, fields, ids = {}, set(), set()
    counts = {}
    with ExitStack() as stack:
        outputs = {key: stack.enter_context((spool / key).open('w', encoding='utf-8'))
                   for key in COLUMNS}
        compressed = stack.enter_context(gzip.open(path, 'rb'))
        events = iter(ijson.parse(compressed, use_float=True))
        if next(events) != ('', 'start_map', None):
            raise RuntimeError('Snapshot must be a JSON object')
        for prefix, event, key in events:
            if (prefix, event) == ('', 'end_map'):
                # Exhaust the parser to check trailing JSON and gzip CRC.
                if next(events, None) is not None:
                    raise RuntimeError('Unexpected trailing snapshot data')
                break
            if prefix or event != 'map_key' or key in fields:
                raise RuntimeError('Invalid or duplicate snapshot field')
            fields.add(key)
            _, event, value = next(events)
            if key in ('version', 'model'):
                if event not in ('number', 'string'):
                    raise RuntimeError('Invalid snapshot header')
                header[key] = value
                continue
            if key not in COLUMNS or event != 'start_array':
                raise RuntimeError('Invalid snapshot column')
            counts[key] = 0
            for _, event, value in events:
                if event == 'end_array':
                    break
                item = _read_value(events, (event, value))
                _validate_item(key, item)
                if key == 'ids':
                    if item in ids:
                        raise RuntimeError('Duplicate snapshot ID')
                    ids.add(item)
                outputs[key].write(json.dumps(item, ensure_ascii=True, allow_nan=False) + '\n')
                counts[key] += 1
    if header != {'version': 1, 'model': MODEL}:
        raise RuntimeError('Unsupported snapshot format or embedding model')
    if set(counts) != set(COLUMNS) or not counts['ids'] or len(set(counts.values())) != 1:
        raise RuntimeError('Invalid snapshot record counts')
    return ids


def _restore_file(path, digest, directory, spool):
    with path.open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != digest:
            raise RuntimeError('Snapshot checksum mismatch')
    expected_ids = _spool_snapshot(path, spool)
    store = collection(directory)
    marker = (store.metadata or {}).get('snapshot_sha256')
    # Refuse to replace a local corpus or older snapshot silently. A partial
    # restore can be retried because upserts use the original stable IDs.
    existing = set(store.get(include=[])['ids'])
    if (marker and marker != digest) or not existing <= expected_ids:
        raise RuntimeError('Use a new CHROMA_DIR for the new snapshot version')
    if marker == digest and existing == expected_ids:
        return store.count()
    with ExitStack() as stack:
        inputs = {key: stack.enter_context((spool / key).open(encoding='utf-8'))
                  for key in COLUMNS}
        while True:
            batch = {key: [json.loads(line) for line in islice(stream, BATCH_SIZE)]
                     for key, stream in inputs.items()}
            if not batch['ids']:
                break
            store.upsert(**batch)
            del batch
    if store.count() != len(expected_ids):
        raise RuntimeError('Incomplete snapshot restore')
    store.modify(metadata={**(store.metadata or {}), 'snapshot_sha256': digest})
    return store.count()


def restore_snapshot(blob, digest, directory):
    """Compatibility entry point; accepts bytes or a psycopg2 memoryview."""
    with tempfile.TemporaryDirectory(prefix='rag-restore-') as temporary:
        spool = Path(temporary)
        path = spool / 'snapshot.gz'
        path.write_bytes(blob)
        return _restore_file(path, digest, directory, spool)


def _download_snapshot(path):
    # Write psycopg2's buffer directly; release row/result/connection before
    # decompression and Chroma allocation. No bytes(row[1]) duplicate.
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT sha256, payload FROM rag_snapshot WHERE id=1')
            row = cur.fetchone()
            if not row:
                raise RuntimeError('Publish the retrieval snapshot before starting the backend')
            path.write_bytes(row[1])
            return row[0]
    finally:
        conn.close()


def restore_on_startup():
    if os.getenv('CHROMA_RESTORE_FROM_DB', 'false').lower() != 'true':
        if os.getenv('APP_ENV', '').lower() == 'production' and not collection(chroma_directory()).count():
            raise RuntimeError('Production Chroma is empty; configure snapshot restore or a populated persistent disk')
        return
    with tempfile.TemporaryDirectory(prefix='rag-restore-') as temporary:
        spool = Path(temporary)
        path = spool / 'snapshot.gz'
        digest = _download_snapshot(path)
        count = _restore_file(path, digest, chroma_directory(), spool)
    print(f'Chroma snapshot ready: {count} chunks')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['export', 'publish'])
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    if args.action == 'export':
        # Exclusive creation protects an earlier operator backup.
        with args.file.open('xb') as output:
            output.write(export_snapshot(chroma_directory()))
        print('Snapshot exported; keep it private (it contains document text)')
    else:
        publish_snapshot(args.file.read_bytes())
        print('Snapshot published to the configured PostgreSQL database')
