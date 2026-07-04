#!/usr/bin/env python3
import random
import os
import django

# 设置Django环境
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "movie.settings")
django.setup()

from myapp.models import UserInfo, Movie, Rating, Collect

def generate_test_data():
    # 获取所有电影
    movies = list(Movie.objects.all())
    if not movies:
        print("没有电影数据，请先添加电影")
        return
    
    # 生成测试用户
    test_users = []
    for i in range(1, 11):  # 生成10个测试用户
        username = f'testuser{i}'
        email = f'test{i}@example.com'
        
        # 检查用户是否已存在
        if not UserInfo.objects.filter(username=username).exists():
            user = UserInfo.objects.create_user(
                username=username,
                password='123456',
                email=email,
                user_ID=f'test{i}',
                nickname=f'测试用户{i}'
            )
            test_users.append(user)
            print(f"创建用户 {username}")
        else:
            user = UserInfo.objects.get(username=username)
            test_users.append(user)
            print(f"用户 {username} 已存在，使用现有用户")
    
    # 为每个用户生成评分和收藏
    for user in test_users:
        # 每个用户评分10-20部电影
        rated_movies = random.sample(movies, random.randint(10, 20))
        for movie in rated_movies:
            # 生成3-10分的随机评分
            score = round(random.uniform(3, 10), 1)
            
            # 检查评分是否已存在
            if not Rating.objects.filter(user=user, movie=movie).exists():
                Rating.objects.create(
                    user=user,
                    movie=movie,
                    score=score
                )
        print(f"为用户 {user.username} 生成了 {len(rated_movies)} 条评分")
        
        # 为每个用户收藏3-5部电影
        collected_movies = random.sample(rated_movies, random.randint(3, 5))
        for movie in collected_movies:
            if not Collect.objects.filter(collect_user=user.username, collect_movie=movie.title).exists():
                Collect.objects.create(
                    collect_user=user.username,
                    collect_movie=movie.title,
                    movie_information=movie
                )
        print(f"为用户 {user.username} 收藏了 {len(collected_movies)} 部电影")
    
    print("测试数据生成完成！")

if __name__ == "__main__":
    generate_test_data()
