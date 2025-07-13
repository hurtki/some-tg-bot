import sqlite3
import datetime
from typing import Optional, List, Tuple
from .logger import logger


class Database:
    def __init__(self, db_path: str = 'bot.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Создание таблиц при первом запуске"""
        with sqlite3.connect(self.db_path) as conn:
            # users table 
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    is_banned BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # posts table 
            conn.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    text_content TEXT NOT NULL,
                    has_photo BOOLEAN DEFAULT FALSE,
                    photo_file_id TEXT,
                    is_anonymous BOOLEAN DEFAULT FALSE,
                    status TEXT DEFAULT 'pending',
                    admin_decision_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    published_at TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id),
                    FOREIGN KEY (admin_decision_by) REFERENCES users (telegram_id)
                )
            ''')
            
            
            # MIGRATION №1 TO POSTS TABLE
            # ADD has_video FIELD (BOOLEAN, DEFAULT: FALSE)
            # ADD video_file_id FIELD (TEXT, DEFAULT: NULL)

            add_column_if_not_exists(conn, "posts", "has_video", "BOOLEAN DEFAULT FALSE")
            add_column_if_not_exists(conn, "posts", "video_file_id", "TEXT")

            # admin table 
            conn.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    added_by INTEGER
                )
            ''')
            
            # indexes 
            conn.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id)')
    
    # === WORK WITH USERS ===
    
    def add_user(self, telegram_id: int, username: str = None, first_name: str = None):
        """Функция проверяет наличие пользователя и либо его обновляет либо создает
        Возвращает True если новый, False если просто был обновлен
        """
        with sqlite3.connect(self.db_path) as conn:
            # checking if user exists 
            exists = conn.execute(
                'SELECT 1 FROM users WHERE telegram_id = ?', 
                (telegram_id,)
            ).fetchone()
            
            if exists:
                # if exists, updating only first_name и last_activity
                conn.execute('''
                    UPDATE users 
                    SET username = ?, first_name = ?, last_activity = ?
                    WHERE telegram_id = ?
                ''', (username, first_name, datetime.datetime.now(), telegram_id))
                return False
            else:
                # if not exists just creating a new one
                conn.execute('''
                    INSERT INTO users 
                    (telegram_id, username, first_name, last_activity) 
                    VALUES (?, ?, ?, ?)
                ''', (telegram_id, username, first_name, datetime.datetime.now()))
                return True
        
    def get_user(self, telegram_id: int) -> Optional[dict]:
        """Getting user"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM users WHERE telegram_id = ?', 
                (telegram_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def ban_user(self, telegram_id: int):
        """Ban user"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'UPDATE users SET is_banned = TRUE WHERE telegram_id = ?',
                (telegram_id,)
            )
    
    def unban_user(self, telegram_id: int):
        """Unban user"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'UPDATE users SET is_banned = FALSE WHERE telegram_id = ?',
                (telegram_id,)
            )
    
    def is_user_banned(self, telegram_id: int) -> bool:
        """Checking if user banned"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT is_banned FROM users WHERE telegram_id = ?',
                (telegram_id,)
            )
            result = cursor.fetchone()
            return bool(result[0]) if result else False
    
    def get_all_users(self) -> List[int]:
        """Getting all users"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT telegram_id FROM users WHERE is_banned = FALSE'
            )
            return [row[0] for row in cursor.fetchall()]
    
    # === WORKING WITH POSTS ===
    
    def create_post(self, user_id: int, text_content: str, has_photo: bool = False, has_video: bool = False, 
                   photo_file_id: str = None, video_file_id: str = None, is_anonymous: bool = False) -> int:
        """create new post"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO posts 
                (user_id, text_content, has_photo, has_video, photo_file_id, video_file_id, is_anonymous) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, text_content, has_photo, has_video, photo_file_id, video_file_id, is_anonymous))
            return cursor.lastrowid
    
    def get_post(self, post_id: int) -> Optional[dict]:
        """get post data"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT p.*, u.username, u.first_name 
                FROM posts p 
                LEFT JOIN users u ON p.user_id = u.telegram_id 
                WHERE p.id = ?
            ''', (post_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def approve_post(self, post_id: int, admin_id: int):
        """aprove post"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE posts 
                SET status = 'approved', admin_decision_by = ?, 
                    reviewed_at = ?, published_at = ?
                WHERE id = ?
            ''', (admin_id, datetime.datetime.now(), datetime.datetime.now(), post_id))
    
    def reject_post(self, post_id: int, admin_id: int):
        """reject post"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE posts 
                SET status = 'rejected', admin_decision_by = ?, reviewed_at = ?
                WHERE id = ?
            ''', (admin_id, datetime.datetime.now(), post_id))
    
    def get_pending_posts(self) -> List[dict]:
        """get pending posts"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute('''
                SELECT p.*, u.username, u.first_name 
                FROM posts p 
                LEFT JOIN users u ON p.user_id = u.telegram_id 
                WHERE p.status = 'pending'
                ORDER BY p.created_at ASC
            ''')
            return [dict(row) for row in cursor.fetchall()]
    
    # === WORK WITH ADMINS ===
    
    def add_admin(self, telegram_id: int, username: str = None, added_by: int = None):
        """Добавление админа"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR IGNORE INTO admins (telegram_id, username, added_by) 
                VALUES (?, ?, ?)
            ''', (telegram_id, username, added_by))
    
    def is_admin(self, telegram_id: int) -> bool:
        """Проверка на админа"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT 1 FROM admins WHERE telegram_id = ?',
                (telegram_id,)
            )
            return cursor.fetchone() is not None
    
    def remove_admin(self, telegram_id: int):
        """Удаление админа"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'DELETE FROM admins WHERE telegram_id = ?',
                (telegram_id,)
            )
    
    # === STATISTICS ===
    
    def get_stats(self) -> dict:
        """Получение статистики"""
        with sqlite3.connect(self.db_path) as conn:
            # all users count 
            users_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            
            # all posts count
            total_posts = conn.execute('SELECT COUNT(*) FROM posts').fetchone()[0]
            
            # all aproved posts count
            approved_posts = conn.execute(
                'SELECT COUNT(*) FROM posts WHERE status = "approved"'
            ).fetchone()[0]
            
            # pending posts
            pending_posts = conn.execute(
                'SELECT COUNT(*) FROM posts WHERE status = "pending"'
            ).fetchone()[0]
            
            return {
                'users_count': users_count,
                'total_posts': total_posts,
                'approved_posts': approved_posts,
                'pending_posts': pending_posts
            }
    
    def get_user_posts_count(self, telegram_id: int) -> int:
        """User posts count"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT COUNT(*) FROM posts WHERE user_id = ?',
                (telegram_id,)
            )
            return cursor.fetchone()[0]

# ======= UTILS =======

def add_column_if_not_exists(conn, table, column, col_def):
    cursor = conn.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
        logger.info(f"Column {column} added to {table}")
    else:
        logger.info(f"✔️ Column {column} already exists in {table}")


db = Database()