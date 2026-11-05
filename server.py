#!/usr/bin/env python3
"""Ứng dụng nội bộ, chỉ dùng thư viện chuẩn Python 3.10+."""
import argparse
import csv
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from datetime import date, timedelta
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get('WORKSPACE_DB', str(ROOT / 'data' / 'workspace.sqlite3')))
SESSION_SECONDS = 12 * 60 * 60
LOGIN_ATTEMPTS = {}


def connection():
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db


def initialize():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with connection() as db:
        db.execute('PRAGMA journal_mode = WAL')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
            display_name TEXT NOT NULL, password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin','leader','lecturer','viewer')),
            active INTEGER NOT NULL DEFAULT 1,
            person_id INTEGER REFERENCES people(id));
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY, name TEXT NOT NULL,
            is_lecturer INTEGER NOT NULL DEFAULT 1,
            is_leader INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL,
            assignee_id INTEGER NOT NULL REFERENCES people(id),
            leader_id INTEGER NOT NULL REFERENCES people(id),
            due_date TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','completed')),
            notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            version INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
            csrf TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit (
            id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id),
            action TEXT NOT NULL, object_id INTEGER,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE INDEX IF NOT EXISTS tasks_assignee ON tasks(assignee_id);
        CREATE INDEX IF NOT EXISTS tasks_due ON tasks(due_date);
        ''')
        # Rebuild the old CHECK constraint while preserving user IDs and child references.
        schema = db.execute("SELECT sql FROM sqlite_master WHERE name='users'").fetchone()[0]
        if "'lecturer'" not in schema:
            db.commit()
            db.execute('PRAGMA foreign_keys = OFF')
            try:
                db.execute('BEGIN IMMEDIATE')
                columns = {row['name'] for row in db.execute('PRAGMA table_info(users)')}
                db.execute("""CREATE TABLE users_v2 (
                    id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    display_name TEXT NOT NULL, password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('admin','leader','lecturer','viewer')),
                    active INTEGER NOT NULL DEFAULT 1,
                    person_id INTEGER REFERENCES people(id))""")
                link_column = 'person_id' if 'person_id' in columns else 'NULL'
                db.execute('INSERT INTO users_v2 SELECT id,username,display_name,password_hash,role,active,' + link_column + ' FROM users')
                db.execute('DROP TABLE users')
                db.execute('ALTER TABLE users_v2 RENAME TO users')
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.execute('PRAGMA foreign_keys = ON')
        db.execute('CREATE UNIQUE INDEX IF NOT EXISTS users_person ON users(person_id) WHERE person_id IS NOT NULL')
        if db.execute('PRAGMA foreign_key_check').fetchone():
            raise RuntimeError('Database foreign key validation failed')
        db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))


def workload_summary(db):
    # Public within the organization: names and pending counts only, never task metadata.
    return [dict(row) for row in db.execute("""SELECT p.id,p.name,COUNT(t.id) pending
        FROM people p LEFT JOIN tasks t ON t.assignee_id=p.id AND t.status='pending'
        GROUP BY p.id HAVING (p.is_lecturer=1 AND p.active=1) OR COUNT(t.id)>0
        ORDER BY pending DESC,p.name COLLATE NOCASE""")]


def password_hash(password):
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return salt + ':' + digest


def password_matches(password, stored):
    salt, expected = stored.split(':')
    digest = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return hmac.compare_digest(digest, expected)


def required_text(data, key, limit=200):
    value = data.get(key)
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > limit:
        raise ValueError(f'Trường {key} phải có từ 1 đến {limit} ký tự.')
    return value.strip()


def valid_password(data):
    value = data.get('password', '')
    if not isinstance(value, str) or not 10 <= len(value) <= 128:
        raise ValueError('Mật khẩu cần có từ 10 đến 128 ký tự.')
    return value


def seed_demo(db):
    names = [('Nguyễn Minh Anh', 1, 0), ('Trần Hoàng Nam', 1, 0),
             ('Lê Thu Hà', 1, 0), ('Phạm Quang Huy', 1, 0),
             ('Đỗ Ngọc Linh', 1, 0), ('Vũ Đức Thành', 1, 0),
             ('PGS. Trần Văn Bình', 0, 1), ('TS. Nguyễn Thị Mai', 0, 1)]
    ids = []
    for name, lecturer, leader in names:
        ids.append(db.execute('INSERT INTO people(name,is_lecturer,is_leader) VALUES (?,?,?)',
                              (name, lecturer, leader)).lastrowid)
    titles = ['Xây dựng đề cương học phần An toàn thông tin', 'Hoàn thiện báo cáo tự đánh giá học kỳ',
              'Tổ chức seminar nghiên cứu khoa học', 'Rà soát ngân hàng câu hỏi học phần',
              'Hướng dẫn sinh viên nghiên cứu khoa học', 'Cập nhật tài liệu thực hành mạng máy tính',
              'Chuẩn bị hồ sơ kiểm định chương trình', 'Tổng hợp kế hoạch giảng dạy học kỳ II',
              'Phản biện đề cương luận văn cao học', 'Báo cáo tiến độ đề tài cấp cơ sở',
              'Tư vấn tuyển sinh chương trình đào tạo', 'Nghiệm thu bài giảng điện tử']
    for i, title in enumerate(titles):
        person = [0, 1, 2, 0, 3, 1, 4, 0, 2, 3, 0, 1][i]
        db.execute('INSERT INTO tasks(title,assignee_id,leader_id,due_date,status,notes) VALUES (?,?,?,?,?,?)',
                   (title, ids[person], ids[6 + i % 2],
                    (date.today() + timedelta(days=[5, -3, 9, 2, 14, -1, 7, 3, -5, 12, 6, 1][i])).isoformat(),
                    'completed' if i in (3, 8, 11) else 'pending', 'Dữ liệu minh họa, có thể chỉnh sửa hoặc xóa.'))
    db.execute("INSERT OR REPLACE INTO settings VALUES ('demo','1')")


class Handler(BaseHTTPRequestHandler):
    server_version = 'FacultyWorkspace'

    def log_message(self, fmt, *args):
        # Không ghi URL/query, mật khẩu hoặc nội dung công việc vào nhật ký truy cập.
        pass

    def send(self, status, value, cookie=None, content_type='application/json; charset=utf-8'):
        body = json.dumps(value, ensure_ascii=False).encode() if content_type.startswith('application/json') else value
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'same-origin')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(body)

    def session(self, db):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get('Cookie', ''))
            token = cookies['workspace_session'].value
        except (KeyError, ValueError):
            return None
        return db.execute('''SELECT u.id,u.username,u.display_name,u.role,u.person_id,s.csrf
            FROM sessions s JOIN users u ON s.user_id=u.id
            WHERE s.token_hash=? AND s.expires>? AND u.active=1
            AND (u.role NOT IN ('lecturer','leader') OR EXISTS (
                SELECT 1 FROM people p WHERE p.id=u.person_id AND p.active=1
                AND ((u.role='lecturer' AND p.is_lecturer=1) OR (u.role='leader' AND p.is_leader=1))))''',
                          (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()

    def new_session(self, db, user_id):
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        db.execute('DELETE FROM sessions WHERE expires < ?', (time.time(),))
        db.execute('INSERT INTO sessions VALUES (?,?,?,?)',
                   (hashlib.sha256(token.encode()).hexdigest(), user_id, csrf, time.time() + SESSION_SECONDS))
        secure = '; Secure' if os.environ.get('COOKIE_SECURE') == '1' else ''
        return 'workspace_session=' + token + '; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200' + secure

    def body(self):
        length = int(self.headers.get('Content-Length', '0'))
        if length > 65536 or length <= 0:
            raise ValueError('Nội dung yêu cầu không hợp lệ hoặc quá lớn.')
        if 'application/json' not in self.headers.get('Content-Type', ''):
            raise ValueError('Yêu cầu phải dùng định dạng JSON.')
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError('Dữ liệu không hợp lệ.')
        return data

    def same_origin(self):
        origin = self.headers.get('Origin')
        fetch_site = self.headers.get('Sec-Fetch-Site')
        if fetch_site == 'cross-site':
            return False
        if origin:
            parts = urlsplit(origin)
            return parts.scheme in ('http', 'https') and parts.netloc == self.headers.get('Host')
        return True

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith('/api/'):
            return self.api('GET', path)
        files = {'/': ('index.html', 'text/html; charset=utf-8'),
                 '/app.js': ('app.js', 'application/javascript; charset=utf-8'),
                 '/styles.css': ('styles.css', 'text/css; charset=utf-8'),
                 '/favicon.svg': ('favicon.svg', 'image/svg+xml')}
        for weight in ('Regular', 'Medium', 'SemiBold', 'Bold'):
            filename = f'fonts/BeVietnamPro-{weight}.ttf'
            files['/' + filename] = (filename, 'font/ttf')
        if path not in files:
            return self.send(404, {'error': 'Không tìm thấy trang.'})
        filename, mime = files[path]
        self.send(200, (ROOT / 'static' / filename).read_bytes(), content_type=mime)

    def do_POST(self):
        self.api('POST', urlsplit(self.path).path)

    def do_PUT(self):
        self.api('PUT', urlsplit(self.path).path)

    def do_DELETE(self):
        self.api('DELETE', urlsplit(self.path).path)

    def api(self, method, path):
        try:
            with connection() as db:
                self.route(db, method, path)
        except (ValueError, json.JSONDecodeError, OverflowError):
            self.send(400, {'error': 'Dữ liệu không hợp lệ. Kiểm tra các trường và thử lại.'})
        except sqlite3.IntegrityError:
            self.send(409, {'error': 'Dữ liệu đang được sử dụng hoặc tên đăng nhập đã tồn tại.'})
        except sqlite3.OperationalError:
            self.send(503, {'error': 'Dữ liệu đang bận. Vui lòng thử lại.'})
        except Exception:
            self.send(500, {'error': 'Có lỗi xử lý. Vui lòng thử lại hoặc liên hệ quản trị.'})

    def route(self, db, method, path):
        if method != 'GET' and not self.same_origin():
            return self.send(403, {'error': 'Nguồn yêu cầu không hợp lệ.'})
        user = self.session(db)
        if path == '/api/session' and method == 'GET':
            configured = db.execute('SELECT 1 FROM users LIMIT 1').fetchone() is not None
            return self.send(200, {'configured': configured, 'user': dict(user) if user else None})
        if path == '/api/setup' and method == 'POST':
            data = self.body()
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                return self.send(409, {'error': 'Hệ thống đã được thiết lập.'})
            username = required_text(data, 'username', 60)
            name = required_text(data, 'display_name', 100)
            password = valid_password(data)
            uid = db.execute('INSERT INTO users(username,display_name,password_hash,role) VALUES (?,?,?,?)',
                             (username, name, password_hash(password), 'admin')).lastrowid
            if data.get('demo') is True:
                seed_demo(db)
            cookie = self.new_session(db, uid)
            db.commit()
            return self.send(201, {'ok': True}, cookie=cookie)
        if path == '/api/login' and method == 'POST':
            data = self.body()
            username = required_text(data, 'username', 60)
            password = data.get('password', '')
            if not isinstance(password, str) or len(password) > 128:
                raise ValueError('Invalid password')
            now = time.time()
            for key in list(LOGIN_ATTEMPTS):
                LOGIN_ATTEMPTS[key] = [t for t in LOGIN_ATTEMPTS[key] if now - t < 300]
                if not LOGIN_ATTEMPTS[key]:
                    del LOGIN_ATTEMPTS[key]
            key = self.client_address[0]
            attempts = LOGIN_ATTEMPTS.get(key, [])
            if len(attempts) >= 10:
                return self.send(429, {'error': 'Đăng nhập sai nhiều lần. Vui lòng thử lại sau 5 phút.'})
            account = db.execute('SELECT * FROM users WHERE username=? AND active=1', (username,)).fetchone()
            linked = True
            if account and account['role'] in ('lecturer', 'leader'):
                flag = 'is_leader' if account['role'] == 'leader' else 'is_lecturer'
                linked = db.execute('SELECT 1 FROM people WHERE id=? AND active=1 AND ' + flag + '=1',
                                    (account['person_id'],)).fetchone()
            if not account or not linked or not password_matches(password, account['password_hash']):
                LOGIN_ATTEMPTS[key] = attempts + [now]
                return self.send(401, {'error': 'Tên đăng nhập hoặc mật khẩu chưa đúng.'})
            LOGIN_ATTEMPTS.pop(key, None)
            cookie = self.new_session(db, account['id'])
            db.commit()
            return self.send(200, {'ok': True}, cookie=cookie)
        if not user:
            return self.send(401, {'error': 'Vui lòng đăng nhập.'})
        if method != 'GET' and not hmac.compare_digest(self.headers.get('X-CSRF-Token', ''), user['csrf']):
            return self.send(403, {'error': 'Phiên làm việc không hợp lệ. Hãy tải lại trang.'})
        if path == '/api/logout' and method == 'POST':
            db.execute('DELETE FROM sessions WHERE user_id=? AND csrf=?', (user['id'], user['csrf']))
            db.commit()
            return self.send(200, {'ok': True}, cookie='workspace_session=; Max-Age=0; Path=/; HttpOnly; SameSite=Strict')
        if path == '/api/password' and method == 'PUT':
            data = self.body()
            current = data.get('current_password', '')
            old = db.execute('SELECT password_hash FROM users WHERE id=?', (user['id'],)).fetchone()[0]
            if not isinstance(current, str) or len(current) > 128 or not password_matches(current, old):
                return self.send(400, {'error': 'Mật khẩu hiện tại chưa đúng.'})
            db.execute('UPDATE users SET password_hash=? WHERE id=?', (password_hash(valid_password(data)), user['id']))
            db.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
            cookie = self.new_session(db, user['id'])
            db.commit()
            return self.send(200, {'ok': True}, cookie=cookie)
        if path == '/api/workload' and method == 'GET':
            return self.send(200, {'workload': workload_summary(db)})
        if path == '/api/data' and method == 'GET':
            full_access = user['role'] == 'admin'
            query = """SELECT t.*,p.name assignee_name,l.name leader_name
                FROM tasks t JOIN people p ON p.id=t.assignee_id JOIN people l ON l.id=t.leader_id"""
            params = ()
            if user['role'] == 'leader':
                query += ' WHERE t.leader_id=?'
                params = (user['person_id'],)
            elif not full_access:
                query += ' WHERE t.assignee_id=?'
                params = (user['person_id'],)
            tasks = [dict(row) for row in db.execute(query + ' ORDER BY t.id DESC', params)]
            if full_access:
                people = [dict(row) for row in db.execute('SELECT * FROM people ORDER BY name COLLATE NOCASE')]
            elif user['role'] == 'leader':
                people = [dict(row) for row in db.execute("""SELECT p.* FROM people p
                    WHERE p.is_lecturer=1 OR p.id=? OR p.id IN (
                        SELECT assignee_id FROM tasks WHERE leader_id=?)
                    ORDER BY p.name COLLATE NOCASE""", (user['person_id'], user['person_id']))]
            else:
                people = [dict(row) for row in db.execute("""SELECT p.* FROM people p
                    WHERE p.id=? OR p.id IN (SELECT leader_id FROM tasks WHERE assignee_id=?)
                    ORDER BY p.name COLLATE NOCASE""", (user['person_id'], user['person_id']))]
            demo = db.execute("SELECT value FROM settings WHERE key='demo'").fetchone()
            return self.send(200, {'tasks': tasks, 'people': people, 'workload': workload_summary(db),
                                   'demo': bool(demo and demo[0] == '1'), 'today': date.today().isoformat()})
        if path == '/api/users' and method == 'GET' and user['role'] == 'admin':
            return self.send(200, [dict(row) for row in db.execute("""SELECT u.id,u.username,u.display_name,
                u.role,u.active,u.person_id,p.name person_name FROM users u
                LEFT JOIN people p ON p.id=u.person_id ORDER BY u.id""")])
        if method == 'GET':
            return self.send(404, {'error': 'Không tìm thấy dữ liệu.'})
        if user['role'] == 'viewer':
            return self.send(403, {'error': 'Tài khoản chỉ có quyền xem.'})
        parts = path.strip('/').split('/')
        if len(parts) not in (2, 3) or parts[0] != 'api':
            return self.send(404, {'error': 'Không tìm thấy chức năng.'})
        resource = parts[1]
        oid = int(parts[2]) if len(parts) == 3 else None
        data = self.body() if method in ('POST', 'PUT') else {}
        if user['role'] == 'lecturer' and (resource != 'tasks' or method != 'PUT' or oid is None):
            return self.send(403, {'error': 'Giảng viên chỉ được cập nhật công việc được giao cho mình.'})
        db.execute('BEGIN IMMEDIATE')
        if resource == 'tasks':
            old = db.execute('SELECT * FROM tasks WHERE id=?', (oid,)).fetchone() if oid else None
            if method in ('PUT', 'DELETE') and not old:
                return self.send(404, {'error': 'Công việc không còn tồn tại.'})
            if user['role'] == 'leader':
                if old and old['leader_id'] != user['person_id']:
                    return self.send(404, {'error': 'Công việc không còn tồn tại hoặc bạn không có quyền truy cập.'})
                if method in ('POST', 'PUT'):
                    if 'leader_id' in data and str(data['leader_id']) != str(user['person_id']):
                        return self.send(403, {'error': 'Lãnh đạo phân công được cố định theo tài khoản đăng nhập.'})
                    # The authenticated identity is authoritative; never trust the client for ownership.
                    data['leader_id'] = user['person_id']
            if user['role'] == 'lecturer':
                if old['assignee_id'] != user['person_id']:
                    return self.send(404, {'error': 'Công việc không còn tồn tại hoặc bạn không có quyền truy cập.'})
                for key in ('assignee_id', 'leader_id', 'due_date'):
                    if key in data and str(data[key]) != str(old[key]):
                        return self.send(403, {'error': 'Bạn không được thay đổi người phụ trách, lãnh đạo phân công hoặc thời hạn.'})
                # Preserve immutable columns even when omitted from the request.
                data = {**dict(old), **data, 'version': data.get('version')}
            if method == 'DELETE':
                db.execute('DELETE FROM tasks WHERE id=?', (oid,))
            elif method in ('POST', 'PUT'):
                if method == 'POST' and oid is not None:
                    raise ValueError('Invalid path')
                if old and data.get('version') != old['version']:
                    return self.send(409, {'error': 'Công việc vừa được người khác cập nhật. Hãy tải lại dữ liệu trước khi sửa.'})
                title = required_text(data, 'title', 300)
                due = required_text(data, 'due_date', 10)
                if date.fromisoformat(due).isoformat() != due:
                    raise ValueError('Invalid date')
                requested_status = data.get('status', 'pending' if method == 'POST' else None)
                if requested_status not in ('pending', 'completed'):
                    raise ValueError('Invalid status')
                # New assignments always start unfinished, even if a client sends 'completed'.
                status = 'pending' if method == 'POST' else requested_status
                assignee, leader = int(data.get('assignee_id', 0)), int(data.get('leader_id', 0))
                for pid, flag, previous in [(assignee, 'is_lecturer', old['assignee_id'] if old else None),
                                            (leader, 'is_leader', old['leader_id'] if old else None)]:
                    person = db.execute('SELECT * FROM people WHERE id=?', (pid,)).fetchone()
                    if not person or (not person['active'] or not person[flag]) and pid != previous:
                        raise ValueError('Invalid person')
                notes = data.get('notes', '')
                if not isinstance(notes, str) or len(notes) > 5000:
                    raise ValueError('Invalid notes')
                values = (title, assignee, leader, due, status, notes.strip())
                if old:
                    db.execute('''UPDATE tasks SET title=?,assignee_id=?,leader_id=?,due_date=?,status=?,notes=?,
                        updated_at=CURRENT_TIMESTAMP,version=version+1 WHERE id=?''', values + (oid,))
                else:
                    oid = db.execute('INSERT INTO tasks(title,assignee_id,leader_id,due_date,status,notes) VALUES (?,?,?,?,?,?)', values).lastrowid
            else:
                return self.send(405, {'error': 'Thao tác không được hỗ trợ.'})
        elif resource == 'people':
            if user['role'] != 'admin':
                return self.send(403, {'error': 'Chỉ quản trị viên được quản lý nhân sự.'})
            old = db.execute('SELECT * FROM people WHERE id=?', (oid,)).fetchone() if oid else None
            if method in ('PUT', 'DELETE') and not old:
                return self.send(404, {'error': 'Không tìm thấy nhân sự.'})
            if method == 'DELETE':
                db.execute('DELETE FROM people WHERE id=?', (oid,))
            elif method in ('POST', 'PUT'):
                name = required_text(data, 'name', 100)
                lecturer, leader = bool(data.get('is_lecturer')), bool(data.get('is_leader'))
                if not (lecturer or leader):
                    raise ValueError('Must have a type')
                values = (name, int(lecturer), int(leader), int(bool(data.get('active', True))))
                if old:
                    db.execute('UPDATE people SET name=?,is_lecturer=?,is_leader=?,active=? WHERE id=?', values + (oid,))
                else:
                    oid = db.execute('INSERT INTO people(name,is_lecturer,is_leader,active) VALUES (?,?,?,?)', values).lastrowid
            else:
                return self.send(405, {'error': 'Thao tác không được hỗ trợ.'})
        elif resource == 'users':
            if user['role'] != 'admin':
                return self.send(403, {'error': 'Chỉ quản trị viên được quản lý tài khoản.'})
            role = data.get('role')
            if role not in ('admin', 'leader', 'lecturer', 'viewer'):
                raise ValueError('Invalid role')
            name = required_text(data, 'display_name', 100)
            person_id = data.get('person_id')
            person_id = int(person_id) if person_id not in ('', None) else None
            if role in ('lecturer', 'leader') and person_id is None:
                return self.send(400, {'error': 'Tài khoản giảng viên hoặc lãnh đạo phải gắn với nhân sự tương ứng.'})
            if person_id is not None:
                person = db.execute('SELECT * FROM people WHERE id=?', (person_id,)).fetchone()
                required_flag = 'is_leader' if role == 'leader' else 'is_lecturer'
                if not person or not person[required_flag] or (role in ('lecturer', 'leader') and not person['active']):
                    return self.send(400, {'error': 'Nhân sự được liên kết không phù hợp với quyền tài khoản.'})
            if method == 'POST' and oid is None:
                oid = db.execute('INSERT INTO users(username,display_name,password_hash,role,person_id) VALUES (?,?,?,?,?)',
                                 (required_text(data, 'username', 60), name, password_hash(valid_password(data)), role, person_id)).lastrowid
            elif method == 'PUT' and oid:
                target = db.execute('SELECT * FROM users WHERE id=?', (oid,)).fetchone()
                if not target:
                    return self.send(404, {'error': 'Không tìm thấy tài khoản.'})
                active = int(bool(data.get('active', True)))
                if oid == user['id'] and (role != 'admin' or not active):
                    return self.send(400, {'error': 'Không thể tự khóa hoặc hạ quyền tài khoản đang sử dụng.'})
                db.execute('UPDATE users SET display_name=?,role=?,active=?,person_id=? WHERE id=?', (name, role, active, person_id, oid))
                if data.get('password'):
                    db.execute('UPDATE users SET password_hash=? WHERE id=?', (password_hash(valid_password(data)), oid))
                db.execute('DELETE FROM sessions WHERE user_id=? AND user_id<>?', (oid, user['id']))
            else:
                return self.send(405, {'error': 'Thao tác không được hỗ trợ.'})
        else:
            return self.send(404, {'error': 'Không tìm thấy chức năng.'})
        db.execute('INSERT INTO audit(user_id,action,object_id) VALUES (?,?,?)', (user['id'], method + ' ' + resource, oid))
        db.commit()
        self.send(201 if method == 'POST' else 200, {'ok': True, 'id': oid})


def main():
    parser = argparse.ArgumentParser(description='Quản lý công việc giảng viên')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    initialize()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'\n  GIẢNG VIÊN WORKSPACE\n  Mở trình duyệt: http://localhost:{args.port}\n  Dữ liệu: {DB_PATH}\n  Nhấn Ctrl+C để dừng.\n', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nĐã dừng ứng dụng.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
