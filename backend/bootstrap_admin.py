"""Operator-only local command to promote the first existing user to administrator."""
import argparse
from database import get_db_connection, create_users_table


def bootstrap_admin(username):
    conn = get_db_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute('LOCK TABLE users IN EXCLUSIVE MODE')
                cur.execute("SELECT 1 FROM users WHERE role='ADMIN' LIMIT 1")
                if cur.fetchone():
                    raise ValueError('관리자가 이미 있습니다. 관리자 전용 역할 변경 API를 사용하세요.')
                cur.execute("UPDATE users SET role='ADMIN' WHERE username=%s", (username,))
                if not cur.rowcount:
                    raise ValueError('먼저 일반 회원가입으로 계정을 생성하세요.')
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('username')
    args = parser.parse_args()
    create_users_table()
    bootstrap_admin(args.username)
    print('최초 관리자 권한 부여 완료')
