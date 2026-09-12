import os
from pathlib import Path
import subprocess
import sys
import unittest
from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient
from psycopg2 import sql
import database
import bootstrap_admin
import main
from settings import allowed_origins


class ConfigurationTests(unittest.TestCase):
    def test_production_ignores_local_dotenv(self):
        env = os.environ.copy()
        env['APP_ENV'] = 'production'
        env.pop('SECRET_KEY', None)
        env.pop('PYTHON_DOTENV_DISABLED', None)
        result = subprocess.run([sys.executable, '-c', 'import auth'],
                                cwd=Path(__file__).parent, env=env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'SECRET_KEY is required', result.stderr)

    def test_missing_or_blank_secret_stops_server(self):
        for secret in (None, '   '):
            env = os.environ.copy()
            env['PYTHON_DOTENV_DISABLED'] = '1'
            env['OPENAI_API_KEY'] = 'test-placeholder'
            env.pop('SECRET_KEY', None)
            if secret is not None:
                env['SECRET_KEY'] = secret
            result = subprocess.run([sys.executable, '-c', 'import main'], cwd=Path(__file__).parent,
                                    env=env, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'SECRET_KEY is required', result.stderr)

    def test_production_cors_requires_explicit_https(self):
        for origins in ('', '*', 'https://*.example.com', 'http://example.com', 'https://example.com/path'):
            with patch.dict(os.environ, {'APP_ENV': 'production', 'CORS_ORIGINS': origins}):
                with self.assertRaises(RuntimeError):
                    allowed_origins()
        with patch.dict(os.environ, {'APP_ENV': 'production', 'CORS_ORIGINS': 'https://example.com,https://other.example.com'}):
            self.assertEqual(allowed_origins(), ['https://example.com', 'https://other.example.com'])


@unittest.skipUnless(os.getenv('RUN_DB_TESTS') == '1', 'Set RUN_DB_TESTS=1 to use PostgreSQL')
class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.original_connect = database.get_db_connection
        self.schema = 'security_test_' + uuid4().hex
        self.owner = self.original_connect()
        self.owner.autocommit = True
        with self.owner.cursor() as cur:
            cur.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        def connect():
            conn = self.original_connect()
            with conn.cursor() as cur:
                cur.execute(sql.SQL('SET search_path TO {}').format(sql.Identifier(self.schema)))
            conn.commit()
            return conn
        self.patches = [patch.object(module, 'get_db_connection', side_effect=connect)
                        for module in (database, main, bootstrap_admin)]
        for patched in self.patches:
            patched.start()
        self.client_context = TestClient(main.app)
        self.client = self.client_context.__enter__()

    def tearDown(self):
        self.client_context.__exit__(None, None, None)
        for patched in reversed(self.patches):
            patched.stop()
        with self.owner.cursor() as cur:
            cur.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.owner.close()

    def login(self, name):
        response = self.client.post('/login', data={'username': name, 'password': 'test-only-password'})
        self.assertEqual(response.status_code, 200)
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    def test_registration_roles_logs_and_dashboard(self):
        c = self.client
        for name in ('alice', 'bob', 'operator'):
            self.assertEqual(c.post('/register', json={'username': name, 'password': 'test-only-password', 'role': 'ADMIN'}).status_code, 200)
            self.assertEqual(database.get_user(name)['role'], 'EMPLOYEE')
        alice, bob = self.login('alice'), self.login('bob')
        self.assertEqual(c.patch('/admin/users/alice/role', json={'role': 'ADMIN'}).status_code, 401)
        self.assertEqual(c.patch('/admin/users/alice/role', headers=alice, json={'role': 'ADMIN'}).status_code, 403)
        bootstrap_admin.bootstrap_admin('operator')
        with self.assertRaises(ValueError):
            bootstrap_admin.bootstrap_admin('alice')
        admin = self.login('operator')
        self.assertEqual(c.patch('/admin/users/bob/role', headers=admin, json={'role': 'SECURITY'}).status_code, 200)
        self.assertEqual(c.get('/me', headers=bob).json()['role'], 'SECURITY')
        self.assertEqual(c.patch('/admin/users/alice/role', headers=bob, json={'role': 'ADMIN'}).status_code, 403)
        self.assertEqual(c.patch('/admin/users/alice/role', headers=admin, json={'role': 'INVALID'}).status_code, 422)
        self.assertEqual(c.patch('/admin/users/missing/role', headers=admin, json={'role': 'ADMIN'}).status_code, 404)
        self.assertEqual(c.patch('/admin/users/operator/role', headers=admin, json={'role': 'EMPLOYEE'}).status_code, 400)
        for name in ('alice', 'bob', 'operator'):
            database.save_log(name, 'test answer', 'source', 'POLICY', True, 0, 0, name)
        self.assertEqual(c.get('/logs').status_code, 401)
        self.assertEqual([x['question'] for x in c.get('/logs', headers=alice).json()], ['alice'])
        self.assertEqual([x['question'] for x in c.get('/logs', headers=bob).json()], ['bob'])
        self.assertEqual(len(c.get('/logs', headers=admin).json()), 3)
        self.assertEqual(c.get('/dashboard', headers=alice).status_code, 403)
        self.assertEqual(c.get('/dashboard', headers=bob).status_code, 403)
        self.assertEqual(c.get('/dashboard', headers=admin).json()['total'], 3)
        self.assertEqual(c.patch('/admin/users/bob/role', headers=admin, json={'role': 'ADMIN'}).status_code, 200)
        self.assertEqual(c.get('/dashboard', headers=bob).status_code, 200)
        self.assertEqual(c.patch('/admin/users/bob/role', headers=admin, json={'role': 'EMPLOYEE'}).status_code, 200)
        self.assertEqual(c.get('/dashboard', headers=bob).status_code, 403)
        self.assertEqual(c.options('/ask', headers={'Origin': 'http://localhost:5173', 'Access-Control-Request-Method': 'POST'}).status_code, 200)
        response = c.options('/ask', headers={'Origin': 'https://untrusted.example', 'Access-Control-Request-Method': 'POST'})
        self.assertNotIn('access-control-allow-origin', response.headers)


if __name__ == '__main__':
    unittest.main()
