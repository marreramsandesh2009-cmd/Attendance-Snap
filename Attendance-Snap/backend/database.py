import os
from mysql.connector import pooling

_pool = None


def get_connection():
    global _pool

    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="attendance_snap_pool",
            pool_size=5,
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "attendance_snap"),
            autocommit=False,
        )

    return _pool.get_connection()


def query(sql, args=(), fetch=False):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(sql, args)

        if fetch:
            return cursor.fetchall()

        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()
