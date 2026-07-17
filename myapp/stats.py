"""
统计查询：ORM + pymysql 原生 SQL 混用

常规 CRUD / 列表仍走 Django ORM；看板类聚合统计走 pymysql 一次往返，
避免多次 ORM .count() / 拉全表再在 Python 里聚合。
连接信息来自 settings.DATABASES，与业务库同一套 .env 配置。
"""
import pymysql
from django.conf import settings


def _get_connection():
    db = settings.DATABASES['default']
    return pymysql.connect(
        host=db.get('HOST') or 'localhost',
        user=db.get('USER') or 'root',
        password=db.get('PASSWORD') or '',
        database=db.get('NAME') or 'django_movie',
        port=int(db.get('PORT') or 3306),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_dashboard_stats():
    """
    一条复合 SQL 取出仪表盘汇总指标（一次往返）。
    """
    sql = """
        SELECT
            (SELECT COUNT(*) FROM myapp_movie) AS movie_num,
            (SELECT COUNT(*) FROM myapp_userinfo) AS user_num,
            (SELECT COUNT(*) FROM myapp_comment) AS comment_num,
            (SELECT COUNT(*) FROM myapp_board) AS board_num,
            (SELECT COUNT(*) FROM myapp_rating) AS rating_num,
            (SELECT COUNT(*) FROM myapp_collect) AS collect_num,
            (SELECT ROUND(AVG(score), 2) FROM myapp_movie WHERE score IS NOT NULL) AS avg_movie_score
    """
    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(sql)
            row = cur.fetchone() or {}
        return {
            'movie_num': int(row.get('movie_num') or 0),
            'user_num': int(row.get('user_num') or 0),
            'comment_num': int(row.get('comment_num') or 0),
            'board_num': int(row.get('board_num') or 0),
            'rating_num': int(row.get('rating_num') or 0),
            'collect_num': int(row.get('collect_num') or 0),
            'avg_movie_score': float(row['avg_movie_score']) if row.get('avg_movie_score') is not None else None,
        }
    finally:
        if conn is not None:
            conn.close()


def get_type_distribution(limit=8):
    """
    按电影 types 字段 GROUP BY，取数量最多的若干类。
    （types 为库中原始标签字符串；多标签并存时按整串分组。）
    """
    limit = max(1, min(int(limit), 50))
    sql = """
        SELECT types AS type_name, COUNT(*) AS cnt
        FROM myapp_movie
        WHERE types IS NOT NULL AND types <> ''
        GROUP BY types
        ORDER BY cnt DESC
        LIMIT %s
    """
    conn = None
    try:
        conn = _get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, (limit,))
            rows = cur.fetchall() or []
        return [
            {'type_name': r['type_name'], 'cnt': int(r['cnt'])}
            for r in rows
        ]
    finally:
        if conn is not None:
            conn.close()
