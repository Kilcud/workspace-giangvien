import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server


class AppTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_db = server.DB_PATH
        server.DB_PATH = Path(self.temp.name) / 'test.sqlite3'
        server.LOGIN_ATTEMPTS.clear()
        server.initialize()
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = ''
        self.csrf = ''
        self.request('POST', '/api/setup', {'username': 'admin', 'password': 'testing-password',
                                          'display_name': 'Quản trị', 'demo': True})
        _, session = self.request('GET', '/api/session')
        self.csrf = session['user']['csrf']

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join()
        server.DB_PATH = self.previous_db
        self.temp.cleanup()

    def request(self, method, path, data=None, headers=None):
        client = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        payload = json.dumps(data).encode() if data is not None else None
        req_headers = {'Content-Type': 'application/json', 'Cookie': self.cookie, 'X-CSRF-Token': self.csrf}
        req_headers.update(headers or {})
        client.request(method, path, payload, req_headers)
        response = client.getresponse()
        status = response.status
        if response.getheader('Set-Cookie'):
            self.cookie = response.getheader('Set-Cookie').split(';')[0]
        raw = response.read()
        result = json.loads(raw) if 'application/json' in response.getheader('Content-Type', '') else raw
        client.close()
        return status, result

    def data(self):
        return self.request('GET', '/api/data')[1]

    def new_task(self):
        task = dict(self.data()['tasks'][0])
        task.update(title='Công việc kiểm tra', status='pending', due_date='2027-01-15')
        return task

    def login_as(self, role, person_id=None):
        if role in ('lecturer', 'leader') and person_id is None:
            person_id = 7 if role == 'leader' else 1
        status, _ = self.request('POST', '/api/users', {'username': role, 'display_name': role,
                     'password': 'testing-password', 'role': role, 'person_id': person_id})
        self.assertEqual(status, 201)
        status, _ = self.request('POST', '/api/login', {'username': role, 'password': 'testing-password'})
        self.assertEqual(status, 200)
        self.csrf = self.request('GET', '/api/session')[1]['user']['csrf']

    def test_setup_and_demo(self):
        data = self.data()
        self.assertEqual(len(data['tasks']), 12)
        self.assertEqual(sum(p['is_lecturer'] for p in data['people']), 6)
        self.assertTrue(any(p['is_lecturer'] and not any(t['assignee_id'] == p['id'] for t in data['tasks']) for p in data['people']))
        self.assertEqual(self.request('POST', '/api/setup', {})[0], 409)

    def test_crud_and_persistence(self):
        status, result = self.request('POST', '/api/tasks', self.new_task())
        self.assertEqual(status, 201)
        tid = result['id']
        task = next(t for t in self.data()['tasks'] if t['id'] == tid)
        task.update(title='Đã sửa', status='completed')
        self.assertEqual(self.request('PUT', f'/api/tasks/{tid}', task)[0], 200)
        server.initialize()
        updated = next(t for t in self.data()['tasks'] if t['id'] == tid)
        self.assertEqual(updated['status'], 'completed')
        self.assertEqual(updated['title'], 'Đã sửa')
        self.assertEqual(updated['version'], 2)
        self.assertEqual(self.request('DELETE', f'/api/tasks/{tid}')[0], 200)
        self.assertFalse(any(t['id'] == tid for t in self.data()['tasks']))

    def test_stale_edit_rejected(self):
        task = self.data()['tasks'][0]
        self.assertEqual(self.request('PUT', f"/api/tasks/{task['id']}", task)[0], 200)
        self.assertEqual(self.request('PUT', f"/api/tasks/{task['id']}", task)[0], 409)

    def test_invalid_inputs_do_not_change_data(self):
        for change in ({'title': ''}, {'due_date': '2026-02-30'}, {'assignee_id': 9999},
                       {'status': 'other'}, {'notes': 'x' * 5001}, {'leader_id': 1}):
            task = self.new_task()
            task.update(change)
            with self.subTest(change=list(change)):
                self.assertEqual(self.request('POST', '/api/tasks', task)[0], 400)
        self.assertEqual(len(self.data()['tasks']), 12)

    def test_anonymous_access_denied(self):
        self.assertEqual(self.request('GET', '/api/data', headers={'Cookie': ''})[0], 401)
        self.assertEqual(self.request('POST', '/api/tasks', self.new_task(), {'Cookie': ''})[0], 401)

    def test_csrf_and_origin(self):
        self.assertEqual(self.request('POST', '/api/tasks', self.new_task(), {'X-CSRF-Token': ''})[0], 403)
        self.assertEqual(self.request('POST', '/api/login', {}, {'Origin': 'https://external.example'})[0], 403)
        self.assertEqual(self.request('POST', '/api/tasks', self.new_task(), {'Sec-Fetch-Site': 'cross-site'})[0], 403)

    def test_viewer_read_only(self):
        task = self.new_task()
        self.login_as('viewer')
        self.assertEqual(self.request('GET', '/api/data')[0], 200)
        self.assertEqual(self.request('POST', '/api/tasks', task)[0], 403)
        self.assertEqual(self.request('DELETE', '/api/tasks/1')[0], 403)
        self.assertEqual(self.request('POST', '/api/people', {'name': 'X'})[0], 403)
        self.assertNotEqual(self.request('GET', '/api/users')[0], 200)

    def test_leader_role(self):
        self.login_as('leader')
        self.assertEqual(self.request('POST', '/api/tasks', self.new_task())[0], 201)
        self.assertEqual(self.request('POST', '/api/people', {'name': 'X'})[0], 403)
        self.assertEqual(self.request('POST', '/api/users', {})[0], 403)

    def test_people_lifecycle(self):
        self.assertEqual(self.request('DELETE', '/api/people/1')[0], 409)
        status, result = self.request('POST', '/api/people', {'name': 'Giảng viên mới', 'is_lecturer': True})
        self.assertEqual(status, 201)
        pid = result['id']
        self.assertEqual(self.request('PUT', f'/api/people/{pid}', {'name': 'Đã nghỉ', 'is_lecturer': True, 'active': False})[0], 200)
        task = self.new_task()
        task['assignee_id'] = pid
        self.assertEqual(self.request('POST', '/api/tasks', task)[0], 400)
        self.assertEqual(self.request('DELETE', f'/api/people/{pid}')[0], 200)

    def test_admin_cannot_lock_self(self):
        self.assertEqual(self.request('PUT', '/api/users/1', {'display_name': 'Quản trị', 'role': 'viewer', 'active': True})[0], 400)
        self.assertEqual(self.request('PUT', '/api/users/1', {'display_name': 'Quản trị', 'role': 'admin', 'active': False})[0], 400)

    def test_password_change_invalidates_session(self):
        old_cookie = self.cookie
        status, _ = self.request('PUT', '/api/password', {'current_password': 'testing-password', 'password': 'new-password-test'})
        self.assertEqual(status, 200)
        self.assertIsNone(self.request('GET', '/api/session', headers={'Cookie': old_cookie})[1]['user'])
        self.assertIsNotNone(self.request('GET', '/api/session')[1]['user'])

    def test_login_rate_limit(self):
        for _ in range(10):
            self.assertEqual(self.request('POST', '/api/login', {'username': 'admin', 'password': 'wrong'})[0], 401)
        self.assertEqual(self.request('POST', '/api/login', {'username': 'admin', 'password': 'testing-password'})[0], 429)

    def test_no_database_or_path_traversal_exposure(self):
        self.assertEqual(self.request('GET', '/data/workspace.sqlite3')[0], 404)
        self.assertEqual(self.request('GET', '/../server.py')[0], 404)
        self.assertEqual(self.request('GET', '/')[0], 200)

    def test_lecturer_only_receives_own_tasks(self):
        all_tasks = self.data()['tasks']
        self.login_as('lecturer')
        data = self.data()
        self.assertEqual(len(data['tasks']), 4)
        self.assertTrue(all(t['assignee_id'] == 1 for t in data['tasks']))
        serialized = json.dumps(data, ensure_ascii=False)
        for task in all_tasks:
            if task['assignee_id'] != 1:
                self.assertNotIn(task['title'], serialized)
        self.assertEqual({p['id'] for p in data['people']}, {1, 7, 8})
        self.assertEqual(self.request('GET', '/api/data?assignee_id=2&role=admin')[1]['tasks'], data['tasks'])

    def test_shared_workload_has_counts_only(self):
        original = self.request('GET', '/api/workload')[1]
        self.assertEqual(len(original['workload']), 6)
        self.assertEqual(sum(p['pending'] for p in original['workload']), 9)
        self.assertTrue(any(p['pending'] == 0 for p in original['workload']))
        for person in original['workload']:
            self.assertEqual(set(person), {'id', 'name', 'pending'})
        self.login_as('lecturer')
        self.assertEqual(self.request('GET', '/api/workload')[1], original)
        self.assertEqual(self.data()['workload'], original['workload'])
        self.assertEqual(self.request('GET', '/api/workload', headers={'Cookie': ''})[0], 401)

    def test_leader_sees_same_shared_counts(self):
        original = self.request('GET', '/api/workload')[1]
        self.login_as('leader', 7)
        self.assertEqual(self.request('GET', '/api/workload')[1], original)
        self.assertEqual(len(self.data()['tasks']), 6)

    def test_lecturer_can_update_own_allowed_fields(self):
        self.login_as('lecturer')
        task = self.data()['tasks'][0]
        status, _ = self.request('PUT', f"/api/tasks/{task['id']}",
                                {'title': 'Tên công việc đã cập nhật', 'notes': 'Tiến độ mới',
                                 'status': 'completed', 'version': task['version']})
        self.assertEqual(status, 200)
        updated = next(t for t in self.data()['tasks'] if t['id'] == task['id'])
        self.assertEqual(updated['title'], 'Tên công việc đã cập nhật')
        self.assertEqual(updated['notes'], 'Tiến độ mới')
        self.assertEqual(updated['status'], 'completed')
        for key in ('assignee_id', 'leader_id', 'due_date'):
            self.assertEqual(updated[key], task[key])
        self.assertEqual(self.request('PUT', f"/api/tasks/{task['id']}",
                         {**updated, 'status': 'pending'})[0], 200)

    def test_lecturer_cannot_change_protected_fields(self):
        self.login_as('lecturer')
        task = self.data()['tasks'][0]
        for change in ({'assignee_id': 2}, {'leader_id': 7 if task['leader_id'] != 7 else 8},
                       {'due_date': '2028-12-31'}):
            with self.subTest(field=list(change)[0]):
                self.assertEqual(self.request('PUT', f"/api/tasks/{task['id']}", {**task, **change})[0], 403)
        self.assertEqual(next(t for t in self.data()['tasks'] if t['id'] == task['id']), task)

    def test_lecturer_cannot_touch_other_tasks_or_create_delete(self):
        other = next(t for t in self.data()['tasks'] if t['assignee_id'] == 2)
        payload = self.new_task()
        self.login_as('lecturer')
        self.assertEqual(self.request('PUT', f"/api/tasks/{other['id']}", {**other, 'notes': 'Forbidden'})[0], 404)
        self.assertEqual(self.request('POST', '/api/tasks', payload)[0], 403)
        self.assertEqual(self.request('DELETE', '/api/tasks/1')[0], 403)
        self.assertEqual(self.request('POST', '/api/people', {'name': 'X'})[0], 403)
        self.assertEqual(self.request('PUT', '/api/users/1', {'role': 'admin'})[0], 403)
        self.assertNotEqual(self.request('GET', '/api/users')[0], 200)
        self.assertEqual(self.request('GET', f"/api/tasks/{other['id']}")[0], 404)

    def test_lecturer_stale_or_missing_version_rejected(self):
        self.login_as('lecturer')
        task = self.data()['tasks'][0]
        url = f"/api/tasks/{task['id']}"
        self.assertEqual(self.request('PUT', url, {'notes': 'Missing version'})[0], 409)
        self.assertEqual(self.request('PUT', url, {'notes': 'Current', 'version': task['version']})[0], 200)
        self.assertEqual(self.request('PUT', url, {'notes': 'Old', 'version': task['version']})[0], 409)

    def test_user_person_links_validated(self):
        payload = {'username': 'newlecturer', 'display_name': 'New', 'password': 'testing-password', 'role': 'lecturer'}
        self.assertEqual(self.request('POST', '/api/users', payload)[0], 400)
        self.assertEqual(self.request('POST', '/api/users', {**payload, 'person_id': 7})[0], 400)
        self.assertEqual(self.request('POST', '/api/users', {**payload, 'person_id': 999})[0], 400)
        self.assertEqual(self.request('POST', '/api/users', {**payload, 'person_id': 1})[0], 201)
        self.assertEqual(self.request('POST', '/api/users', {**payload, 'username': 'duplicate', 'person_id': 1})[0], 409)
        self.assertEqual(self.request('DELETE', '/api/people/1')[0], 409)

    def test_reassignment_updates_lecturer_visibility(self):
        admin_headers = {'Cookie': self.cookie, 'X-CSRF-Token': self.csrf}
        task = next(t for t in self.data()['tasks'] if t['assignee_id'] == 1)
        self.login_as('lecturer')
        self.assertTrue(any(t['id'] == task['id'] for t in self.data()['tasks']))
        self.assertEqual(self.request('PUT', f"/api/tasks/{task['id']}", {**task, 'assignee_id': 2}, admin_headers)[0], 200)
        self.assertFalse(any(t['id'] == task['id'] for t in self.data()['tasks']))
        self.assertEqual(self.request('PUT', f"/api/tasks/{task['id']}", task)[0], 404)

    def test_leader_can_edit_assignment_and_deadline(self):
        self.login_as('leader', 7)
        task = self.data()['tasks'][0]
        payload = {**task, 'assignee_id': 6, 'leader_id': 7, 'due_date': '2027-02-15'}
        self.assertEqual(self.request('PUT', f"/api/tasks/{task['id']}", payload)[0], 200)
        updated = next(t for t in self.data()['tasks'] if t['id'] == task['id'])
        for field in ('assignee_id', 'leader_id', 'due_date'):
            self.assertEqual(updated[field], payload[field])

    def test_leader_only_sees_own_assignments(self):
        all_tasks = self.data()['tasks']
        self.login_as('leader', 7)
        data = self.data()
        self.assertEqual(len(data['tasks']), 6)
        self.assertTrue(all(t['leader_id'] == 7 for t in data['tasks']))
        serialized = json.dumps(data, ensure_ascii=False)
        for task in all_tasks:
            if task['leader_id'] != 7:
                self.assertNotIn(task['title'], serialized)
        self.assertNotIn(8, {p['id'] for p in data['people']})
        self.assertEqual(self.request('GET', '/api/data?leader_id=8&role=admin')[1]['tasks'], data['tasks'])

    def test_leader_cannot_modify_or_delete_other_leader_tasks(self):
        other = next(t for t in self.data()['tasks'] if t['leader_id'] == 8)
        self.login_as('leader', 7)
        self.assertEqual(self.request('PUT', f"/api/tasks/{other['id']}", {**other, 'leader_id': 7})[0], 404)
        self.assertEqual(self.request('DELETE', f"/api/tasks/{other['id']}")[0], 404)
        with server.connection() as db:
            actual = db.execute('SELECT leader_id,version FROM tasks WHERE id=?', (other['id'],)).fetchone()
        self.assertEqual(tuple(actual), (8, other['version']))

    def test_new_tasks_always_start_pending(self):
        for role in ('admin', 'leader'):
            if role == 'leader':
                self.login_as('leader', 7)
            for supplied_status in (None, 'completed'):
                with self.subTest(role=role, supplied_status=supplied_status):
                    payload = self.new_task()
                    if supplied_status is None:
                        payload.pop('status')
                    else:
                        payload['status'] = supplied_status
                    status, result = self.request('POST', '/api/tasks', payload)
                    self.assertEqual(status, 201)
                    created = next(t for t in self.data()['tasks'] if t['id'] == result['id'])
                    self.assertEqual(created['status'], 'pending')
                    self.assertEqual(self.request('PUT', f"/api/tasks/{created['id']}",
                                     {**created, 'status': 'completed'})[0], 200)
                    updated = next(t for t in self.data()['tasks'] if t['id'] == created['id'])
                    self.assertEqual(updated['status'], 'completed')

    def test_new_task_leader_is_derived_from_login(self):
        self.login_as('leader', 7)
        payload = self.new_task()
        payload.pop('leader_id')
        status, result = self.request('POST', '/api/tasks', payload)
        self.assertEqual(status, 201)
        created = next(t for t in self.data()['tasks'] if t['id'] == result['id'])
        self.assertEqual(created['leader_id'], 7)
        self.assertEqual(created['leader_name'], 'PGS. Trần Văn Bình')
        self.assertEqual(self.request('POST', '/api/tasks', {**payload, 'leader_id': 8})[0], 403)
        self.assertEqual(self.request('PUT', f"/api/tasks/{created['id']}", {**created, 'leader_id': 8})[0], 403)
        self.assertEqual(self.request('DELETE', f"/api/tasks/{created['id']}")[0], 200)

    def test_admin_can_transfer_leader_and_access_moves(self):
        headers = {'Cookie': self.cookie, 'X-CSRF-Token': self.csrf}
        task = next(t for t in self.data()['tasks'] if t['leader_id'] == 7)
        self.login_as('leader', 7)
        self.assertEqual(self.request('PUT', f"/api/tasks/{task['id']}", {**task, 'leader_id': 8}, headers)[0], 200)
        self.assertNotIn(task['id'], {t['id'] for t in self.data()['tasks']})
        self.assertEqual(self.request('PUT', f"/api/tasks/{task['id']}", task)[0], 404)
        self.assertEqual(len(self.request('GET', '/api/data', headers=headers)[1]['tasks']), 12)

    def test_leader_account_requires_correct_person_link(self):
        payload = {'username': 'lead2', 'display_name': 'Leader', 'role': 'leader', 'password': 'testing-password'}
        self.assertEqual(self.request('POST', '/api/users', payload)[0], 400)
        self.assertEqual(self.request('POST', '/api/users', {**payload, 'person_id': 1})[0], 400)
        self.assertEqual(self.request('POST', '/api/users', {**payload, 'person_id': 8})[0], 201)

    def test_inactive_leader_loses_access(self):
        headers = {'Cookie': self.cookie, 'X-CSRF-Token': self.csrf}
        self.login_as('leader', 7)
        self.assertEqual(self.request('PUT', '/api/people/7',
                         {'name': 'PGS. Trần Văn Bình', 'is_leader': True, 'active': False}, headers)[0], 200)
        self.assertEqual(self.request('GET', '/api/data')[0], 401)
        self.assertEqual(self.request('POST', '/api/login', {'username': 'leader', 'password': 'testing-password'})[0], 401)

    def test_person_link_change_invalidates_old_session(self):
        admin_headers = {'Cookie': self.cookie, 'X-CSRF-Token': self.csrf}
        self.login_as('lecturer')
        current = self.request('GET', '/api/session')[1]['user']
        self.assertEqual(self.request('PUT', f"/api/users/{current['id']}",
                          {'display_name': 'Lecturer', 'role': 'lecturer', 'person_id': 2, 'active': True}, admin_headers)[0], 200)
        self.assertEqual(self.request('GET', '/api/data')[0], 401)

    def test_inactive_lecturer_loses_access(self):
        admin_headers = {'Cookie': self.cookie, 'X-CSRF-Token': self.csrf}
        self.login_as('lecturer')
        self.assertEqual(self.request('PUT', '/api/people/1',
                         {'name': 'Nguyễn Minh Anh', 'is_lecturer': True, 'active': False}, admin_headers)[0], 200)
        self.assertEqual(self.request('GET', '/api/data')[0], 401)
        self.assertEqual(self.request('POST', '/api/login', {'username': 'lecturer', 'password': 'testing-password'})[0], 401)

    def test_legacy_schema_migration_preserves_data(self):
        with server.connection() as db:
            before = tuple(db.execute('SELECT id,username,password_hash FROM users').fetchone())
            db.commit()
            db.execute('PRAGMA foreign_keys=OFF')
            db.executescript("""BEGIN;
                CREATE TABLE legacy_users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    display_name TEXT NOT NULL,password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin','leader','viewer')),active INTEGER NOT NULL DEFAULT 1);
                INSERT INTO legacy_users SELECT id,username,display_name,password_hash,role,active FROM users;
                DROP TABLE users;
                ALTER TABLE legacy_users RENAME TO users;
                COMMIT;""")
        server.initialize()
        server.initialize()
        with server.connection() as db:
            self.assertEqual(tuple(db.execute('SELECT id,username,password_hash FROM users').fetchone()), before)
            self.assertIsNone(db.execute('PRAGMA foreign_key_check').fetchone())
        self.assertEqual(len(self.data()['tasks']), 12)
        self.assertEqual(self.request('GET', '/api/session')[1]['user']['role'], 'admin')
        self.assertEqual(self.request('POST', '/api/users', {'username': 'migrated', 'display_name': 'Migrated',
                          'role': 'lecturer', 'person_id': 1, 'password': 'testing-password'})[0], 201)

    def test_bundled_fonts_and_styles(self):
        for weight in ('Regular', 'Medium', 'SemiBold', 'Bold'):
            with self.subTest(weight=weight):
                status, body = self.request('GET', f'/fonts/BeVietnamPro-{weight}.ttf')
                self.assertEqual(status, 200)
                self.assertTrue(body.startswith(b'\x00\x01\x00\x00'))
        status, css = self.request('GET', '/styles.css?v=2')
        self.assertEqual(status, 200)
        self.assertIn(b'Be Vietnam Pro', css)
        self.assertNotIn(b'https://', css)
        self.assertEqual(self.request('GET', '/fonts/../../../server.py')[0], 404)

    def test_audit_records_changes(self):
        self.request('POST', '/api/tasks', self.new_task())
        with server.connection() as db:
            row = db.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 1').fetchone()
        self.assertEqual(row['user_id'], 1)
        self.assertEqual(row['action'], 'POST tasks')


if __name__ == '__main__':
    unittest.main()
