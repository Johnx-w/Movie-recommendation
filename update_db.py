import pymysql

# 连接数据库
conn = pymysql.connect(
    host='localhost',
    user='root',
    password='123456',
    database='django_movie',
    charset='utf8mb4'
)
cursor = conn.cursor()

try:

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS myapp_cfrec (
        id BIGINT AUTO_INCREMENT PRIMARY KEY,
        user_id BIGINT NOT NULL,
        movie_id BIGINT NOT NULL,
        rating DOUBLE NOT NULL,
        FOREIGN KEY (user_id) REFERENCES myapp_userinfo(id),
        FOREIGN KEY (movie_id) REFERENCES myapp_movie(id),
        UNIQUE INDEX unique_user_movie (user_id, movie_id)
    )
    ''')
    print('Created myapp_cfrec table successfully')
    

    cursor.execute('SHOW COLUMNS FROM myapp_rating LIKE "user_id"')
    if not cursor.fetchone():
        cursor.execute('ALTER TABLE myapp_rating ADD COLUMN user_id BIGINT NOT NULL, ADD COLUMN movie_id BIGINT NOT NULL')
        cursor.execute('ALTER TABLE myapp_rating ADD CONSTRAINT fk_rating_user FOREIGN KEY (user_id) REFERENCES myapp_userinfo(id), ADD CONSTRAINT fk_rating_movie FOREIGN KEY (movie_id) REFERENCES myapp_movie(id), ADD UNIQUE INDEX unique_user_movie (user_id, movie_id)')
        print('Updated myapp_rating table successfully')
    else:
        print('myapp_rating table already has user_id column')
    

    cursor.execute('SHOW COLUMNS FROM myapp_rec LIKE "user_id"')
    if not cursor.fetchone():
        cursor.execute('ALTER TABLE myapp_rec ADD COLUMN user_id BIGINT NOT NULL, ADD COLUMN movie_id BIGINT NOT NULL')
        cursor.execute('ALTER TABLE myapp_rec ADD CONSTRAINT fk_rec_user FOREIGN KEY (user_id) REFERENCES myapp_userinfo(id), ADD CONSTRAINT fk_rec_movie FOREIGN KEY (movie_id) REFERENCES myapp_movie(id), ADD UNIQUE INDEX unique_user_movie (user_id, movie_id)')
        print('Updated myapp_rec table successfully')
    else:
        print('myapp_rec table already has user_id column')
    
    # 提交更改
    conn.commit()
    print('Database tables updated successfully')
except Exception as e:
    print(f'Error: {e}')
    conn.rollback()
finally:
    # 关闭连接
    cursor.close()
    conn.close()
