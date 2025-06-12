import sqlite3
import datetime
from typing import Optional, List, Tuple

class Database:
    def __init__(self, db_path: str = 'bot.db'):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Создание таблиц при первом запуске"""
        with sqlite3.connect(self.db_path) as conn:
            # Таблица пользователей
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
            
            # Таблица постов
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
            
            # Таблица админов
            conn.execute('''
                CREATE TABLE IF NOT EXISTS admins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    added_by INTEGER
                )
            ''')
            
            # Индексы для быстрого поиска
            conn.execute('CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_posts_status ON posts(status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts(user_id)')
    
    # === РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ===
    
    def add_user(self, telegram_id: int, username: str = None, first_name: str = None):
        """Функция проверяет наличие пользователя и либо его обновляет либо создает
        Возвращает True если новый, False если просто был обновлен
        """
        with sqlite3.connect(self.db_path) as conn:
            # Сначала проверяем, существует ли пользователь
            exists = conn.execute(
                'SELECT 1 FROM users WHERE telegram_id = ?', 
                (telegram_id,)
            ).fetchone()
            
            if exists:
                # Обновляем только username, first_name и last_activity
                conn.execute('''
                    UPDATE users 
                    SET username = ?, first_name = ?, last_activity = ?
                    WHERE telegram_id = ?
                ''', (username, first_name, datetime.datetime.now(), telegram_id))
                return False
            else:
                # Создаем нового пользователя
                conn.execute('''
                    INSERT INTO users 
                    (telegram_id, username, first_name, last_activity) 
                    VALUES (?, ?, ?, ?)
                ''', (telegram_id, username, first_name, datetime.datetime.now()))
                return True
        
    def get_user(self, telegram_id: int) -> Optional[dict]:
        """Получение пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                'SELECT * FROM users WHERE telegram_id = ?', 
                (telegram_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def ban_user(self, telegram_id: int):
        """Бан пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'UPDATE users SET is_banned = TRUE WHERE telegram_id = ?',
                (telegram_id,)
            )
    
    def unban_user(self, telegram_id: int):
        """Разбан пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'UPDATE users SET is_banned = FALSE WHERE telegram_id = ?',
                (telegram_id,)
            )
    
    def is_user_banned(self, telegram_id: int) -> bool:
        """Проверка на бан"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT is_banned FROM users WHERE telegram_id = ?',
                (telegram_id,)
            )
            result = cursor.fetchone()
            return bool(result[0]) if result else False
    
    def get_all_users(self) -> List[int]:
        """Получение всех пользователей для рассылки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT telegram_id FROM users WHERE is_banned = FALSE'
            )
            return [row[0] for row in cursor.fetchall()]
    
    # === РАБОТА С ПОСТАМИ ===
    
    def create_post(self, user_id: int, text_content: str, has_photo: bool = False, 
                   photo_file_id: str = None, is_anonymous: bool = False) -> int:
        """Создание нового поста"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                INSERT INTO posts 
                (user_id, text_content, has_photo, photo_file_id, is_anonymous) 
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, text_content, has_photo, photo_file_id, is_anonymous))
            return cursor.lastrowid
    
    def get_post(self, post_id: int) -> Optional[dict]:
        """Получение поста по ID"""
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
        """Одобрение поста"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE posts 
                SET status = 'approved', admin_decision_by = ?, 
                    reviewed_at = ?, published_at = ?
                WHERE id = ?
            ''', (admin_id, datetime.datetime.now(), datetime.datetime.now(), post_id))
    
    def reject_post(self, post_id: int, admin_id: int):
        """Отклонение поста"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                UPDATE posts 
                SET status = 'rejected', admin_decision_by = ?, reviewed_at = ?
                WHERE id = ?
            ''', (admin_id, datetime.datetime.now(), post_id))
    
    def get_pending_posts(self) -> List[dict]:
        """Получение постов на модерации"""
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
    
    # === РАБОТА С АДМИНАМИ ===
    
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
    
    # === СТАТИСТИКА ===
    
    def get_stats(self) -> dict:
        """Получение статистики"""
        with sqlite3.connect(self.db_path) as conn:
            # Общее количество пользователей
            users_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
            
            # Общее количество постов
            total_posts = conn.execute('SELECT COUNT(*) FROM posts').fetchone()[0]
            
            # Одобренные посты
            approved_posts = conn.execute(
                'SELECT COUNT(*) FROM posts WHERE status = "approved"'
            ).fetchone()[0]
            
            # Посты на модерации
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
        """Количество постов пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT COUNT(*) FROM posts WHERE user_id = ?',
                (telegram_id,)
            )
            return cursor.fetchone()[0]

db = Database()