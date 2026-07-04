#!/usr/bin/env python3
# 测试密码哈希和认证功能

import pymysql
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import authenticate
from django.conf import settings
import os

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie.settings')
import django
django.setup()

from myapp.models import UserInfo

# 测试密码哈希
print("测试密码哈希...")
password = '123456'
hashed_password = make_password(password)
print(f"原始密码: {password}")
print(f"哈希密码: {hashed_password}")
print(f"验证密码: {check_password(password, hashed_password)}")

# 测试从数据库读取密码并验证
print("\n测试从数据库读取密码...")

# 数据库连接配置
config = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'database': 'django_movie',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor
}

try:
    connection = pymysql.connect(**config)
    with connection.cursor() as cursor:
        # 查询最近添加的管理员
        sql = "SELECT username, password FROM myapp_userinfo WHERE is_staff = 1 ORDER BY registration DESC LIMIT 1"
        cursor.execute(sql)
        result = cursor.fetchone()
        
        if result:
            username = result['username']
            db_password = result['password']
            print(f"数据库中的用户名: {username}")
            print(f"数据库中的密码: {db_password}")
            print(f"密码长度: {len(db_password)}")
            print(f"密码是否以$开头: {'$' in db_password}")
            
            # 测试密码验证
            print(f"使用check_password验证: {check_password('123456', db_password)}")
            
            # 测试authenticate函数
            print("\n测试authenticate函数...")
            user = authenticate(username=username, password='123456')
            if user:
                print(f"authenticate成功: {user.username}")
            else:
                print("authenticate失败")
        else:
            print("没有找到管理员用户")
finally:
    if 'connection' in locals() and connection:
        connection.close()
