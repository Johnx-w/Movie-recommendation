import os
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie.settings')
django.setup()

from myapp.models import UserInfo
from datetime import datetime
import random

# 检查是否已存在root用户
try:
    existing_user = UserInfo.objects.filter(username='root').first()
    
    if existing_user:
        print("超级管理员root已存在，无需创建")
    else:
        # 生成用户ID
        user_ID = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))
        
        # 创建超级管理员账户（使用create_user方法，自动处理密码哈希）
        user = UserInfo.objects.create_user(
            username='root',
            password='123456',
            email='root@example.com',
            user_ID=user_ID,
            nickname='超级管理员',
            sex=1,
            is_staff=True,
            is_superuser=True,
            is_active=True
        )
        
        print("超级管理员root创建成功！")
        print("用户名: root")
        print("密码: 123456")
        print("邮箱: root@example.com")
        print("权限: 超级管理员")
        print("密码格式: 加密存储")
        
except Exception as e:
    print(f"创建超级管理员失败: {str(e)}")
