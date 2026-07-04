import pymysql
import json
from datetime import datetime

# 数据库配置（保留你的配置）
db_config = {
    'host': 'localhost',
    'user': 'root',
    'passwd': '123456',
    'db': 'django_movie',
    'charset': 'utf8mb4'
}


def parse_date(date_str):
    """处理日期格式，兼容纯年份（如2003）和标准日期"""
    if not date_str:
        return None
    # 先处理纯年份
    if len(date_str.strip()) == 4 and date_str.isdigit():
        return f"{date_str}-01-01"
    # 处理标准日期格式
    formats = ["%Y-%m-%d", "%Y/%m/%d", "%Y年%m月%d日"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except:
            continue
    return None


def main():
    success_count = 0
    fail_count = 0
    conn = None
    cur = None

    try:
        # 1. 建立数据库连接
        conn = pymysql.connect(**db_config)
        cur = conn.cursor()

        # ！！！新增：先清空旧数据（避免重复导入，可选）
        # cur.execute("TRUNCATE TABLE `myapp_movie`;")
        # conn.commit()
        # print("已清空旧数据，开始重新导入...")

        # 2. 逐行读取 ur.txt（注意路径：如果sql.py在spiders目录，直接读ur.txt即可）
        with open('ur.txt', 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # 3. 遍历解析每一行
        for idx, line in enumerate(lines):
            line_num = idx + 1
            line = line.strip()
            if not line:
                continue

            try:
                # 解析JSON
                movie = json.loads(line)

                # ========== 核心修改1：提取豆瓣电影ID（关键！） ==========
                movie_id = movie.get('id', '').strip()
                if not movie_id:
                    fail_count += 1
                    print(f"【跳过】第{line_num}条数据无豆瓣ID")
                    continue

                # 提取字段
                title = movie.get('title', '').strip()
                if not title:
                    fail_count += 1
                    print(f"【跳过】第{line_num}条数据无标题")
                    continue

                # 评分转浮点数
                score = None
                score_str = movie.get('score', '')
                if score_str and score_str.replace('.', '').isdigit():
                    score = float(score_str)

                # 日期处理（结果赋值给release_date变量，后续传给date字段）
                release_date = parse_date(movie.get('release_date', ''))

                # 其他字段
                poster = movie.get('cover_url', '').strip()  # 暂时存豆瓣链接，后续替换
                actors_list = movie.get('actors', [])
                actors = ' '.join([a.strip() for a in actors_list]) if actors_list else ''
                regions_list = movie.get('regions', [])
                regions = ' '.join([r.strip() for r in regions_list]) if regions_list else ''
                types_list = movie.get('types', [])
                movie_type = ' '.join([t.strip() for t in types_list]) if types_list else ''
                summary = ''

                # ========== 核心修改2：INSERT语句添加id字段 ==========
                sql = """
                    INSERT INTO `myapp_movie` 
                    (`id`,`title`,`score`,`date`,`poster`,`actors`,`regions`,`types`,`summary`) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                # 执行SQL：第一个参数是movie_id（豆瓣ID）
                cur.execute(sql, (movie_id, title, score, release_date, poster, actors, regions, movie_type, summary))
                success_count += 1
                print(f"【成功】第{line_num}条：{movie_id} - {title}")

            except json.JSONDecodeError as e:
                fail_count += 1
                print(f"【解析失败】第{line_num}条 | 错误：invalid syntax | 数据片段：{line[:100]}...")
            except pymysql.Error as e:
                fail_count += 1
                title = movie.get('title', '未知') if 'movie' in locals() else '未知'
                movie_id = movie.get('id', '未知') if 'movie' in locals() else '未知'
                print(f"【数据库失败】第{line_num}条 | ID：{movie_id} | 标题：{title} | 错误：{e}")
                conn.rollback()
            except Exception as e:
                fail_count += 1
                print(f"【未知失败】第{line_num}条 | 错误：{e} | 数据片段：{line[:100]}...")

        # 批量提交
        conn.commit()
        print(f"\n===== 最终统计 ======")
        print(f"成功插入：{success_count} 条")
        print(f"失败插入：{fail_count} 条")
        print(f"====================")

    except pymysql.Error as e:
        print(f"【数据库连接失败】错误：{e}")
    finally:
        # 关闭连接
        if cur:
            cur.close()
        if conn:
            conn.close()


if __name__ == '__main__':
    main()