#!/usr/bin/env python3
# 测试管理员密码哈希修复是否有效

import requests
import json

# 测试添加管理员功能
def test_add_admin():
    print("测试添加管理员功能...")
    
    # 先登录一个管理员账号获取csrf token
    login_url = 'http://127.0.0.1:8000/login/'
    admin_url = 'http://127.0.0.1:8000/admin_admins/'
    add_url = 'http://127.0.0.1:8000/admin_admin_add/'
    
    # 会话对象
    session = requests.Session()
    
    # 获取登录页面，提取csrf token
    login_page = session.get(login_url)
    csrf_token = None
    
    # 简单提取csrf token（实际项目中可能需要更复杂的解析）
    if 'csrfmiddlewaretoken' in login_page.text:
        import re
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login_page.text)
        if match:
            csrf_token = match.group(1)
    
    if not csrf_token:
        print("无法获取csrf token")
        return False
    
    # 登录管理员账号
    login_data = {
        'username': 'root',  # 使用已存在的超级管理员账号
        'password': '123456',
        'csrfmiddlewaretoken': csrf_token
    }
    
    login_response = session.post(login_url, data=login_data, headers={'Referer': login_url})
    
    if '/front_index/' not in login_response.url:
        print("管理员登录失败")
        return False
    
    # 获取管理页面，提取新的csrf token
    admin_page = session.get(admin_url)
    csrf_token = None
    if 'csrfmiddlewaretoken' in admin_page.text:
        import re
        match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', admin_page.text)
        if match:
            csrf_token = match.group(1)
    
    if not csrf_token:
        print("无法获取管理页面的csrf token")
        return False
    
    # 测试添加新管理员
    test_username = 'test_admin_' + str(int(time.time()))
    test_email = test_username + '@example.com'
    
    add_data = {
        'csrfmiddlewaretoken': csrf_token,
        'username': test_username,
        'password': '123456',
        'email': test_email,
        'nickname': '测试管理员',
        'is_superuser': 'false'
    }
    
    add_response = session.post(add_url, data=add_data, headers={'Referer': admin_url})
    
    try:
        result = add_response.json()
        if result.get('status'):
            print(f"添加管理员成功: {test_username}")
            
            # 测试新管理员登录
            session2 = requests.Session()
            login_page2 = session2.get(login_url)
            csrf_token2 = None
            if 'csrfmiddlewaretoken' in login_page2.text:
                import re
                match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', login_page2.text)
                if match:
                    csrf_token2 = match.group(1)
            
            if csrf_token2:
                login_data2 = {
                    'username': test_username,
                    'password': '123456',
                    'csrfmiddlewaretoken': csrf_token2
                }
                
                login_response2 = session2.post(login_url, data=login_data2, headers={'Referer': login_url})
                
                if '/front_index/' in login_response2.url:
                    print(f"新管理员登录成功: {test_username}")
                    return True
                else:
                    print(f"新管理员登录失败: {test_username}")
                    return False
            else:
                print("无法获取登录页面的csrf token")
                return False
        else:
            print(f"添加管理员失败: {result.get('error')}")
            return False
    except json.JSONDecodeError:
        print("添加管理员响应不是JSON格式")
        return False

if __name__ == "__main__":
    import time
    success = test_add_admin()
    if success:
        print("测试通过！管理员密码哈希修复成功。")
    else:
        print("测试失败！管理员密码哈希修复可能存在问题。")
