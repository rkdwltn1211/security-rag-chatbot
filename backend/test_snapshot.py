import gzip
import hashlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from uuid import uuid4
from psycopg2 import sql

import chroma_snapshot as snapshot
import database


class SnapshotTests(unittest.TestCase):
    def test_restore_retry_and_disk_loss_preserve_vectors_and_metadata(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
            source = snapshot.collection(Path(root) / 'source')
            meta = {'source': '스캔.pdf', 'page': 2, 'permission': 'EMPLOYEE'}
            vector = [0.1] * 1536
            source.add(ids=['ocr-page'], documents=['한국어 English OCR'],
                       metadatas=[meta], embeddings=[vector])
            blob = snapshot.export_snapshot(Path(root) / 'source')
            digest = hashlib.sha256(blob).hexdigest()
            for folder in ('first-start', 'first-start', 'lost-disk-new-start'):
                target = Path(root) / folder
                self.assertEqual(snapshot.restore_snapshot(blob, digest, target), 1)
                result = snapshot.collection(target).query(query_embeddings=[vector], n_results=1)
                self.assertEqual(result['documents'], [['한국어 English OCR']])
                self.assertEqual(result['metadatas'], [[meta]])
            with self.assertRaisesRegex(RuntimeError, 'checksum'):
                snapshot.restore_snapshot(blob, 'invalid', Path(root) / 'bad')
            data = snapshot.decode_snapshot(blob)
            data['metadatas'][0].pop('permission')
            with self.assertRaisesRegex(RuntimeError, 'permission'):
                snapshot.decode_snapshot(gzip.compress(json.dumps(data).encode()))

    def test_empty_production_corpus_fails_closed(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
            with patch.dict(os.environ, {'APP_ENV': 'production', 'CHROMA_DIR': root,
                                         'CHROMA_RESTORE_FROM_DB': 'false'}):
                with self.assertRaisesRegex(RuntimeError, 'empty'):
                    snapshot.restore_on_startup()

    @unittest.skipUnless(os.getenv('RUN_DB_TESTS') == '1', 'Requires local PostgreSQL')
    def test_postgres_publish_and_startup_restore(self):
        connect = database.get_db_connection
        owner = connect()
        owner.autocommit = True
        schema = 'snapshot_test_' + uuid4().hex
        with owner.cursor() as cur:
            cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
        def isolated():
            conn = connect()
            with conn.cursor() as cur:
                cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(schema)))
            conn.commit()
            return conn
        try:
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as root:
                source = Path(root) / 'source'
                snapshot.collection(source).add(ids=['test'], documents=['OCR 한국어'],
                    embeddings=[[0.1] * 1536],
                    metadatas=[{'source': 'scan.pdf', 'page': 1, 'permission': 'EMPLOYEE'}])
                with patch.object(snapshot, 'get_db_connection', side_effect=isolated):
                    blob = snapshot.export_snapshot(source)
                    snapshot.publish_snapshot(blob)
                    snapshot.publish_snapshot(blob)
                    for target in ('boot', 'reboot'):
                        with patch.dict(os.environ, {'CHROMA_DIR': str(Path(root) / target),
                                                     'CHROMA_RESTORE_FROM_DB': 'true'}):
                            snapshot.restore_on_startup()
                            self.assertEqual(snapshot.collection(Path(root) / target).count(), 1)
        finally:
            with owner.cursor() as cur:
                cur.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(schema)))
            owner.close()
