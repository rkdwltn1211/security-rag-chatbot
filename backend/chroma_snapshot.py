"""Store a static retrieval corpus in PostgreSQL; restore without embedding API calls.

Operator commands: export FILE, publish FILE. No public upload endpoint.
Run export after ingest finishes; publish uses the configured PostgreSQL database.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path

import chromadb
from settings import chroma_directory
from database import get_db_connection

MODEL = 'text-embedding-3-small'
COLLECTION = 'langchain'


def collection(directory):
    return chromadb.PersistentClient(path=str(directory)).get_or_create_collection(COLLECTION)


def export_snapshot(directory):
    rows = collection(directory).get(include=['documents', 'metadatas', 'embeddings'])
    if not rows['ids']:
        raise RuntimeError('Cannot export an empty Chroma collection')
    payload = {key: rows[key] for key in ('ids', 'documents', 'metadatas')}
    payload.update(version=1, model=MODEL, embeddings=rows['embeddings'].tolist())
    return gzip.compress(json.dumps(payload, ensure_ascii=False).encode('utf-8'), mtime=0)


def decode_snapshot(blob):
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


def restore_snapshot(blob, digest, directory):
    if hashlib.sha256(blob).hexdigest() != digest:
        raise RuntimeError('Snapshot checksum mismatch')
    data = decode_snapshot(blob)
    store = collection(directory)
    marker = (store.metadata or {}).get('snapshot_sha256')
    if marker == digest and store.count() == len(data['ids']):
        return store.count()
    # Refuse to replace a local corpus or older snapshot silently. A partial
    # restore can be retried because upserts use the original stable IDs.
    existing = set(store.get(include=[])['ids'])
    if (marker and marker != digest) or not existing <= set(data['ids']):
        raise RuntimeError('Use a new CHROMA_DIR for the new snapshot version')
    for start in range(0, len(data['ids']), 128):
        store.upsert(**{key: data[key][start:start + 128]
                        for key in ('ids', 'documents', 'metadatas', 'embeddings')})
    store.modify(metadata={**(store.metadata or {}), 'snapshot_sha256': digest})
    return store.count()


def restore_on_startup():
    if os.getenv('CHROMA_RESTORE_FROM_DB', 'false').lower() != 'true':
        if os.getenv('APP_ENV', '').lower() == 'production' and not collection(chroma_directory()).count():
            raise RuntimeError('Production Chroma is empty; configure snapshot restore or a populated persistent disk')
        return
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT sha256, payload FROM rag_snapshot WHERE id=1')
            row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        raise RuntimeError('Publish the retrieval snapshot before starting the backend')
    count = restore_snapshot(bytes(row[1]), row[0], chroma_directory())
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
