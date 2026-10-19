import psycopg2
from datetime import datetime
import settings
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "security_rag"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        port=int(os.getenv("DB_PORT", "5432")),
        sslmode=os.getenv('DB_SSLMODE', 'require' if os.getenv('APP_ENV', '').lower() == 'production' else 'prefer'),
        connect_timeout=15
    )

# 유저 테이블 생성
def create_users_table():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            hashed_password VARCHAR(255) NOT NULL,
            role VARCHAR(20) DEFAULT 'EMPLOYEE',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()
    print("✅ users 테이블 생성 완료")

# 로그 테이블 생성 및 기존 스키마 보완
def create_chat_logs_table():
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS chat_logs (
                        id SERIAL PRIMARY KEY,
                        question TEXT,
                        answer TEXT,
                        sources TEXT,
                        question_type VARCHAR(20),
                        is_valid BOOLEAN,
                        retry_count INTEGER,
                        retrieve_count INTEGER,
                        username VARCHAR(50),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    ALTER TABLE chat_logs
                    ADD COLUMN IF NOT EXISTS username VARCHAR(50)
                """)
    finally:
        conn.close()


# 유저 조회
def get_user(username: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username, hashed_password, role FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "hashed_password": row[2], "role": row[3]}
    return None

# 유저 생성
def create_user(username: str, hashed_password: str, role: str = "EMPLOYEE"):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO users (username, hashed_password, role)
        VALUES (%s, %s, %s)
    """, (username, hashed_password, role))
    conn.commit()
    cur.close()
    conn.close()
    print("✅ 유저 생성 완료")

# 로그 저장
def save_log(question, answer, sources, question_type, is_valid, retry_count, retrieve_count, username="anonymous"):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO chat_logs 
        (question, answer, sources, question_type, is_valid, retry_count, retrieve_count, created_at, username)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (question, answer, sources, question_type, is_valid, retry_count, retrieve_count, datetime.now(), username))
    conn.commit()
    cur.close()
    conn.close()

if __name__ == "__main__":
    create_users_table()
    create_chat_logs_table()
