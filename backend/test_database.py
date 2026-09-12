"""Opt-in integration tests against PostgreSQL, using an isolated temporary schema."""
import os
import unittest
from uuid import uuid4
from unittest.mock import patch

from psycopg2 import sql
import database


@unittest.skipUnless(os.getenv('RUN_DB_TESTS') == '1', 'Set RUN_DB_TESTS=1 to use PostgreSQL')
class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.connect = database.get_db_connection
        self.schema = 'test_rag_' + uuid4().hex
        self.admin = self.connect()
        self.admin.autocommit = True
        with self.admin.cursor() as cur:
            cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))

        def isolated_connection():
            conn = self.connect()
            with conn.cursor() as cur:
                cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(self.schema)))
            conn.commit()
            return conn

        self.patcher = patch.object(database, 'get_db_connection', side_effect=isolated_connection)
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        try:
            with self.admin.cursor() as cur:
                cur.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        finally:
            self.admin.close()

    def test_new_database_and_username_statistics(self):
        database.create_users_table()
        database.create_chat_logs_table()
        database.save_log('question', 'answer', 'source', 'POLICY', True, 0, 0, 'alice')
        database.create_chat_logs_table()
        conn = database.get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT username, COUNT(*) FROM chat_logs GROUP BY username')
                self.assertEqual(cur.fetchall(), [('alice', 1)])
                cur.execute('SELECT COUNT(*) FROM users')
                self.assertEqual(cur.fetchone(), (0,))
        finally:
            conn.close()

    def test_legacy_table_keeps_existing_logs(self):
        database.create_chat_logs_table()
        database.save_log('old question', 'answer', 'source', 'POLICY', True, 0, 0)
        conn = database.get_db_connection()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute('ALTER TABLE chat_logs DROP COLUMN username')
            database.create_chat_logs_table()
            database.save_log('new question', 'answer', 'source', 'POLICY', True, 0, 0, 'bob')
            with conn.cursor() as cur:
                cur.execute('SELECT question, username FROM chat_logs ORDER BY id')
                self.assertEqual(cur.fetchall(), [('old question', None), ('new question', 'bob')])
        finally:
            conn.close()


if __name__ == '__main__':
    unittest.main()
