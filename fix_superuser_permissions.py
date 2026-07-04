import os
import django

# 设置Django环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'movie.settings')
django.setup()

from myapp.models import UserInfo

# 修复root用户的权限设置
try:
    user = UserInfo.objects.filter(username='root').first()
    if user:
        # 手动设置权限属性
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.save()
        
        print("超级管理员权限修复成功！")
        print(f"用户: {user.username}")
        print(f"is_staff: {user.is_staff}")
        print(f"is_superuser: {user.is_superuser}")
        print(f"is_active: {user.is_active}")
    else:
        print("未找到root用户")
    
except Exception as e:
    print(f"修复权限失败: {str(e)}")
