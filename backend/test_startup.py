"""HTTP/startup wiring checks without a running DB or paid LLM calls.

Real PostgreSQL authorization/storage regressions remain in test_security.py.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi.testclient import TestClient
import main
import auth
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import time


class StartupHttpTests(unittest.TestCase):
    def test_parallel_requests_do_not_overlap_heavy_rag_work(self):
        active, maximum = 0, 0
        guard = Lock()
        def ask(question, user_role):
            nonlocal active, maximum
            with guard:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.05)
            with guard:
                active -= 1
            return {'answer': 'test', 'sources': 'scan.pdf | p.1', 'question_type': 'POLICY',
                    'is_valid': True, 'retry_count': 0, 'retrieve_count': 0}
        with patch.object(main.app.state, 'rag_ask', ask, create=True), patch.object(main, 'save_log'):
            with ThreadPoolExecutor(max_workers=2) as workers:
                futures = [workers.submit(main.ask_question, main.QuestionRequest(question='test'),
                            {'username':'test-user', 'role':'EMPLOYEE'}) for _ in range(2)]
                for future in futures:
                    self.assertEqual(future.result().sources, 'scan.pdf | p.1')
        self.assertEqual(maximum, 1)

    def test_restore_precedes_rag_and_login_question_logging_still_work(self):
        users, logs, calls = {}, [], []
        def create_user(name, password_hash, role):
            users[name] = {'username': name, 'hashed_password': password_hash, 'role': role}
        def ask(question, user_role):
            self.assertEqual(calls, ['users', 'logs', 'restore'])
            self.assertEqual(user_role, 'EMPLOYEE')
            return {'answer': 'Test answer', 'sources': 'scan.pdf | p.2',
                    'question_type': 'POLICY', 'is_valid': True,
                    'retry_count': 0, 'retrieve_count': 0}
        fake_rag = SimpleNamespace(ask=ask)
        with patch.object(main, 'create_users_table', side_effect=lambda: calls.append('users')), \
             patch.object(main, 'create_chat_logs_table', side_effect=lambda: calls.append('logs')), \
             patch.object(main, 'restore_on_startup', side_effect=lambda: calls.append('restore')), \
             patch.dict('sys.modules', {'rag_chain': fake_rag}), \
             patch.object(main, 'get_user', side_effect=users.get), \
             patch.object(auth, 'get_user', side_effect=users.get), \
             patch.object(main, 'create_user', side_effect=create_user), \
             patch.object(main, 'save_log', side_effect=lambda *args, **kwargs: logs.append((args, kwargs))):
            with TestClient(main.app) as client:
                self.assertEqual(client.post('/register', json={'username':'test-only-user',
                    'password':'test-only-password', 'role':'ADMIN'}).status_code, 200)
                self.assertEqual(users['test-only-user']['role'], 'EMPLOYEE')
                response = client.post('/login', data={'username':'test-only-user','password':'test-only-password'})
                self.assertEqual(response.status_code, 200)
                headers = {'Authorization': 'Bearer ' + response.json()['access_token']}
                self.assertEqual(client.get('/dashboard', headers=headers).status_code, 403)
                response = client.post('/ask', json={'question':'Test OCR question'}, headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['sources'], 'scan.pdf | p.2')
                self.assertEqual(logs[0][1]['username'], 'test-only-user')
                self.assertEqual(tuple(logs[0][1][key] for key in ('question', 'answer', 'sources')),
                                 ('Test OCR question','Test answer','scan.pdf | p.2'))

    def test_failed_restore_prevents_server_startup(self):
        with patch.object(main, 'create_users_table'), patch.object(main, 'create_chat_logs_table'), \
             patch.object(main, 'restore_on_startup', side_effect=RuntimeError('invalid snapshot')):
            with self.assertRaisesRegex(RuntimeError, 'invalid snapshot'):
                with TestClient(main.app):
                    self.fail('Server must not accept traffic')
