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
    def test_startup_releases_db_before_restore_and_removes_temporary_files(self):
        blob = gzip.compress(json.dumps(self.payload()).encode())
        digest = hashlib.sha256(blob).hexdigest()
        closed, paths = [], []
        class Cursor:
            def __enter__(self): return self
            def __exit__(self, *args): closed.append('cursor')
            def execute(self, query): pass
            def fetchone(self): return digest, memoryview(blob)
        class Connection:
            def cursor(self): return Cursor()
            def close(self): closed.append('connection')
        def restore(path, actual_digest, directory, spool):
            self.assertEqual(closed, ['cursor', 'connection'])
            self.assertEqual(path.read_bytes(), blob)
            self.assertEqual(actual_digest, digest)
            paths.append(spool)
            raise RuntimeError('simulated failure')
        with patch.object(snapshot, 'get_db_connection', return_value=Connection()), \
             patch.object(snapshot, '_restore_file', side_effect=restore), \
             patch.dict(os.environ, {'CHROMA_RESTORE_FROM_DB': 'true'}):
            with self.assertRaisesRegex(RuntimeError, 'simulated failure'):
                snapshot.restore_on_startup()
        self.assertFalse(paths[0].exists())

    def payload(self, count=1):
        return {'model': snapshot.MODEL, 'version': 1,
                'embeddings': [[0.1] * 1536 for _ in range(count)],
                'metadatas': [{'source': '한글📄.pdf', 'page': i + 1,
                              'permission': 'EMPLOYEE'} for i in range(count)],
                'documents': ['한국어 English 📄 ' + str(i) for i in range(count)],
                'ids': [str(i) for i in range(count)]}

    def restore_payload(self, data, directory):
        blob = gzip.compress(json.dumps(data, ensure_ascii=False).encode())
        return snapshot.restore_snapshot(memoryview(blob), hashlib.sha256(blob).hexdigest(), directory)

    def test_streaming_batches_and_interrupted_restore(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            store = snapshot.collection(directory)
            original_upsert = store.upsert
            batches = []
            def interrupted(**batch):
                batches.append(len(batch['ids']))
                if len(batches) == 2:
                    raise RuntimeError('simulated interruption')
                return original_upsert(**batch)
            with patch.object(snapshot, 'collection', return_value=store):
                with patch.object(store, 'upsert', side_effect=interrupted):
                    with self.assertRaisesRegex(RuntimeError, 'interruption'):
                        self.restore_payload(self.payload(130), directory)
                self.assertEqual(batches, [128, 2])
                self.assertEqual(store.count(), 128)
                self.assertNotIn('snapshot_sha256', store.metadata or {})
                with patch.object(snapshot, 'decode_snapshot', side_effect=AssertionError('full decode')):
                    with patch.object(snapshot.gzip, 'decompress', side_effect=AssertionError('full gzip')):
                        self.assertEqual(self.restore_payload(self.payload(130), directory), 130)
                self.assertEqual(store.count(), 130)
                self.assertIsNotNone(store.metadata['snapshot_sha256'])

    def test_invalid_payload_never_opens_chroma(self):
        broken = []
        data = self.payload(2); data['ids'][1] = data['ids'][0]; broken.append(data)
        data = self.payload(); data['documents'] = []; broken.append(data)
        data = self.payload(); data['embeddings'][0].pop(); broken.append(data)
        data = self.payload(); data['embeddings'][0][0] = float('inf'); broken.append(data)
        data = self.payload(); data['metadatas'][0].pop('permission'); broken.append(data)
        data = self.payload(); data['model'] = 'other-model'; broken.append(data)
        for data in broken:
            with self.subTest(data_type=list(data)):
                with patch.object(snapshot, 'collection') as create:
                    with self.assertRaises((RuntimeError, ValueError, snapshot.ijson.JSONError)):
                        self.restore_payload(data, 'must-not-open')
                    create.assert_not_called()

    def test_corrupt_gzip_duplicate_fields_and_trailing_json_fail_closed(self):
        text = json.dumps(self.payload(), ensure_ascii=False)
        blobs = [gzip.compress(text.encode())[:-4],
                 gzip.compress((text[:-1] + ',"version":1}').encode()),
                 gzip.compress((text + '{}').encode())]
        for blob in blobs:
            with patch.object(snapshot, 'collection') as create:
                with self.assertRaises((RuntimeError, ValueError, EOFError, snapshot.ijson.JSONError)):
                    snapshot.restore_snapshot(blob, hashlib.sha256(blob).hexdigest(), 'must-not-open')
                create.assert_not_called()

    def test_new_snapshot_does_not_overwrite_existing_version(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            self.restore_payload(self.payload(), directory)
            data = self.payload(); data['documents'] = ['changed']
            with self.assertRaisesRegex(RuntimeError, 'new CHROMA_DIR'):
                self.restore_payload(data, directory)
            self.assertEqual(snapshot.collection(directory).get()['documents'], self.payload()['documents'])

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
