import random
import pymysql
import math
import os
import time
from datetime import datetime

from django.shortcuts import render, redirect
from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.core.exceptions import ValidationError
from django.conf import settings
from django.core.cache import cache


from .models import Movie, UserInfo, Comment, Collect, Board, Rating, CfRec
from django.db.models import Q

from myapp.pagination import Pagination

from django.views.decorators.csrf import csrf_exempt

# 登录表单
class LoginForm(forms.Form):
    username = forms.CharField(
        required=True,
        min_length=3,
        max_length=18,
        error_messages={
            "required": "用户名不可为空!",
            "min_length": "用户名不能低于三位!",
            "max_length": "用户名不能超过18位!"
        }
    )
    password = forms.CharField(
        required=True,
        error_messages={
            "required": "密码不可以为空",
        }
    )


MAX_LOGIN_FAILED_TIMES = 3
LOGIN_LOCK_SECONDS = 10 * 60


def _login_failed_key(username):
    return f"login_failed:{username}"


def _login_lock_key(username):
    return f"login_lock_until:{username}"


def _get_lock_remaining_seconds(username):
    lock_until = cache.get(_login_lock_key(username))
    if not lock_until:
        return 0
    remaining = int(lock_until - time.time())
    return remaining if remaining > 0 else 0


def _record_login_failed(username):
    failed_key = _login_failed_key(username)
    failed_count = cache.get(failed_key, 0) + 1
    if failed_count >= MAX_LOGIN_FAILED_TIMES:
        cache.set(_login_lock_key(username), time.time() + LOGIN_LOCK_SECONDS, timeout=LOGIN_LOCK_SECONDS)
        cache.delete(failed_key)
        return True
    cache.set(failed_key, failed_count, timeout=LOGIN_LOCK_SECONDS)
    return False


def _clear_login_failed(username):
    cache.delete(_login_failed_key(username))
    cache.delete(_login_lock_key(username))


def login_user(request):
    if request.method == "GET":
        return render(request, 'login.html')

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")

            # 连续输错3次锁定10分钟
            lock_remaining = _get_lock_remaining_seconds(username)
            if lock_remaining > 0:
                remain_minutes = math.ceil(lock_remaining / 60)
                messages.error(request, f'登录失败次数过多，账号已锁定，请 {remain_minutes} 分钟后再试')
                return HttpResponseRedirect('/login/')
            
            try:
                # 首先尝试使用Django的authenticate函数（处理哈希密码）
                user = authenticate(request, username=username, password=password)
                
                if user is not None:
                    # 哈希密码验证成功
                    login(request, user)
                    request.session.set_expiry(None)
                    _clear_login_failed(username)
                    return redirect('/front_index/')
                else:
                    # 哈希密码验证失败，尝试兼容明文密码
                    try:
                        # 直接从数据库获取用户信息
                        config = {
                            'host': 'localhost',
                            'user': 'root',
                            'password': '123456',
                            'database': 'django_movie',
                            'charset': 'utf8mb4',
                            'cursorclass': pymysql.cursors.DictCursor
                        }
                        
                        connection = pymysql.connect(**config)
                        with connection.cursor() as cursor:
                            # 检查用户是否存在
                            check_sql = "SELECT * FROM myapp_userinfo WHERE username = %s"
                            cursor.execute(check_sql, (username,))
                            user_data = cursor.fetchone()
                            
                            if user_data and user_data['password'] == password:
                                # 明文密码验证成功，更新为哈希密码
                                user_obj = UserInfo.objects.get(username=username)
                                user_obj.set_password(password)  # 设置哈希密码
                                user_obj.save()
                                
                                # 重新认证并登录
                                user = authenticate(request, username=username, password=password)
                                if user:
                                    login(request, user)
                                    request.session.set_expiry(None)
                                    _clear_login_failed(username)
                                    return redirect('/front_index/')
                            
                        # 所有验证都失败
                        locked_now = _record_login_failed(username)
                        if locked_now:
                            messages.error(request, '登录失败3次，账号已锁定10分钟，请稍后再试')
                        else:
                            messages.error(request, '用户名或密码错误')
                        return HttpResponseRedirect('/login/')
                        
                    except Exception as e:
                        # 兼容验证失败
                        locked_now = _record_login_failed(username)
                        if locked_now:
                            messages.error(request, '登录失败3次，账号已锁定10分钟，请稍后再试')
                        else:
                            messages.error(request, '用户名或密码错误')
                        return HttpResponseRedirect('/login/')
                
            except Exception as e:
                messages.error(request, f'登录失败：{str(e)}')
                return HttpResponseRedirect('/login/')
        else:
            error_msg = '; '.join([v[0] for v in form.errors.values()])
            messages.error(request, f'表单验证失败：{error_msg}')
            return render(request, 'login.html', {'form': form})

    return HttpResponseRedirect('/login/')


# 注册表单
class RegisterForm(forms.Form):
    username = forms.CharField(
        required=True,
        min_length=3,
        max_length=18,
        error_messages={
            "required": "用户名不可为空!",
            "min_length": "用户名不能低于三位!",
            "max_length": "用户名不能超过18位!"
        }
    )
    password1 = forms.CharField(
        required=True,
        min_length=3,
        max_length=18,
        error_messages={
            "required": "密码不可为空!",
            "min_length": "密码不能低于三位!",
            "max_length": "密码不能超过18位!"
        }
    )
    password2 = forms.CharField(
        required=True,
        error_messages={
            "required": "确认密码不可为空!"
        }
    )
    email = forms.EmailField(
        required=True,
        error_messages={
            "required": "邮箱不可以为空!"
        },
    )
    # 可选：添加昵称字段，和UserInfo模型匹配
    nickname = forms.CharField(
        required=False,
        max_length=255,
        label="用户昵称"
    )

    def clean_password2(self):
        if 'password1' in self.cleaned_data and 'password2' in self.cleaned_data:
            pwd1 = self.cleaned_data["password1"]
            pwd2 = self.cleaned_data["password2"]
            if pwd1 != pwd2:
                raise ValidationError("两次输入的密码不一致，请重新输入!")
        return self.cleaned_data["password2"]


def register_user(request):
    if request.method == "GET":
        return render(request, "register.html")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password1"]
            email = form.cleaned_data["email"]
            nickname = form.cleaned_data.get("nickname", username)  # 昵称默认=用户名

            # 检查用户名/邮箱是否存在（匹配UserInfo的unique字段）
            if UserInfo.objects.filter(username=username).exists():
                messages.error(request, '你输入的用户名已存在!')
                return HttpResponseRedirect('/register/')
            if UserInfo.objects.filter(email=email).exists():
                messages.error(request, '你输入的邮箱已经被注册过!')
                return HttpResponseRedirect('/register/')

            # 生成用户ID
            user_ID = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))
            # 创建用户（匹配UserInfo模型字段）
            user = UserInfo.objects.create_user(
                username=username,
                password=password,
                email=email,
                user_ID=user_ID,
                nickname=nickname  # 传递昵称
            )
            messages.success(request, '注册成功，请登录!')
            return HttpResponseRedirect('/login/')
        else:
            error_msg = '; '.join([v[0] for v in form.errors.values()])
            messages.error(request, f'注册失败：{error_msg}')
            return render(request, 'register.html', {'form': form})

    return HttpResponseRedirect('/register/')


def logout_user(request):
    logout(request)
    return redirect('/front_index/')


# 首页（匹配Movie模型的date字段，消除排序错误）
def index(request):
    # 按发布日期倒序取前8条（热映），按评分倒序取前8条（高分）
    queryset_hot = Movie.objects.order_by('-date')[:8]
    queryset_high = Movie.objects.order_by('-score')[:8]
    return render(request, 'front_index.html', {
        "queryset_hot": queryset_hot,
        "queryset_high": queryset_high
    })


# 首页别名（和index逻辑统一，避免混乱）
def front_index(request):
    return index(request)  # 直接复用index逻辑，减少冗余


# 排行榜（支持分页）
def rank(request):
    # 获取当前标签页和页码
    tab = request.GET.get('tab', 'home')  # 默认显示总榜单
    page = request.GET.get('page', '1')  # 默认显示第一页
    
    # 定义每页显示的电影数量
    page_size = 10
    
    # 根据标签页获取对应的电影查询集
    if tab == 'home':
        # 总榜单：按评分排序
        queryset = Movie.objects.order_by('-score')
    elif tab == 'action':
        queryset = Movie.objects.filter(types__contains="动作").order_by('-score')
    elif tab == 'comedy':
        queryset = Movie.objects.filter(types__contains="喜剧").order_by('-score')
    elif tab == 'love':
        queryset = Movie.objects.filter(types__contains="爱情").order_by('-score')
    elif tab == 'scienceFiction':
        queryset = Movie.objects.filter(types__contains="科幻").order_by('-score')
    elif tab == 'terror':
        queryset = Movie.objects.filter(types__contains="恐怖").order_by('-score')
    elif tab == 'plot':
        queryset = Movie.objects.filter(types__contains="剧情").order_by('-score')
    elif tab == 'war':
        queryset = Movie.objects.filter(types__contains="战争").order_by('-score')
    elif tab == 'crime':
        queryset = Movie.objects.filter(types__contains="犯罪").order_by('-score')
    elif tab == 'thriller':
        queryset = Movie.objects.filter(types__contains="惊悚").order_by('-score')
    elif tab == 'cartoon':
        queryset = Movie.objects.filter(types__contains="动画").order_by('-score')
    elif tab == 'history':
        queryset = Movie.objects.filter(types__contains="历史").order_by('-score')
    else:
        # 默认总榜单
        queryset = Movie.objects.order_by('-score')
    
    # 分页处理
    page_object = Pagination(request, queryset, page_size=page_size, page_param="page")
    
    # 根据标签页设置当前激活的标签
    context = {
        "active_tab": tab,
        "page_queryset": page_object.page_queryset,
        "page_string": page_object.html(),
    }
    
    return render(request, 'front_rank.html', context)


def depot(request, *args, **kwargs):
    if not kwargs:
        kwargs = {
            'depot_type_ID': '0',
            'depot_region_ID': '0',
            'depot_time_ID': '0',
        }

    # 首先从kwargs中取出相应的id
    type_ID = kwargs.get('depot_type_ID')
    region_ID = kwargs.get('depot_region_ID')
    time_ID = kwargs.get('depot_time_ID')

    type_list = [{"ID": 1, "type": '动作'}, {"ID": 2, "type": '喜剧'}, {"ID": 3, "type": '爱情'},
                 {"ID": 4, "type": '科幻'}, {"ID": 5, "type": '恐怖'}, {"ID": 6, "type": '剧情'},
                 {"ID": 7, "type": '战争'}, {"ID": 8, "type": '犯罪'}, {"ID": 9, "type": '惊悚'},
                 {"ID": 10, "type": '冒险'}, {"ID": 11, "type": '悬疑'}, {"ID": 12, "type": '武侠'},
                 {"ID": 13, "type": '奇幻'}, {"ID": 14, "type": '动画'}, {"ID": 15, "type": '历史'}, ]
    region_list = [{"ID": 1, "region": '大陆'}, {"ID": 2, "region": '香港'}, {"ID": 3, "region": '台湾'},
                   {"ID": 4, "region": '美国'}, {"ID": 5, "region": '法国'}, {"ID": 6, "region": '英国'},
                   {"ID": 7, "region": '日本'}, {"ID": 8, "region": '韩国'}, {"ID": 9, "region": '德国'},
                   {"ID": 10, "region": '泰国'}, {"ID": 11, "region": '印度'}, {"ID": 12, "region": '意大利'},
                   {"ID": 13, "region": '西班牙'}, {"ID": 14, "region": '加拿大'}, ]
    time_list = [{"ID": 1, "time": '2024'}, {"ID": 2, "time": '2023'}, {"ID": 3, "time": "2022"},
                 {"ID": 4, "time": '2021'}, {"ID": 5, "time": '2020'}, {"ID": 6, "time": '2019'},
                 {"ID": 7, "time": "2018"}, {"ID": 8, "time": '2017'}, {"ID": 9, "time": '2016'},
                 {"ID": 10, "time": '2015'}, {"ID": 11, "time": '2014'}, {"ID": 12, "time": "其他"}]

    type_name = '全部'
    region_name = '全部'
    time_name = '全部'
    if type_ID == '0':
        type = ''
    else:
        type_int = int(type_ID)
        type = type_list[type_int - 1].get("type")
        type_name = type_list[type_int - 1].get("type")
    if region_ID == '0':
        region = ''
    else:
        region_int = int(region_ID)
        region = region_list[region_int - 1].get("region")
        region_name = region_list[region_int - 1].get("region")
    if time_ID == '0':
        time = ''
    else:
        time_int = int(time_ID)
        time = time_list[time_int - 1].get("time")
        time_name = time_list[time_int - 1].get("time")

    queryset = Movie.objects.filter(
        Q(types__contains=type) & Q(regions__contains=region) & Q(date__contains=time)
    )

    return render(
        request,
        'front_depot.html',
        {'type_list': type_list,
         'region_list': region_list,
         'time_list': time_list,
         'queryset': queryset,
         'kwargs': kwargs,
         'type_name': type_name,
         'region_name': region_name,
         'time_name': time_name
         }
    )


def details(request, uid):
    movie_information = Movie.objects.filter(id=uid)
    # 优化：避免空查询集导致的循环报错
    if not movie_information.exists():
        messages.error(request, "影片不存在！")
        return redirect('/front_index/')

    movie_obj = movie_information.first()
    movie_name = movie_obj.title
    movie_ID = movie_obj.id

    queryset = Comment.objects.filter(movie=movie_name).order_by('-comment_time')
    request.session["info"] = {'movie_ID': movie_ID, 'ID': uid}

    # 优化：用户未登录时避免查询收藏（防止匿名用户报错）
    collect = Collect.objects.none()
    if request.user.is_authenticated:
        collect = Collect.objects.filter(Q(collect_user=request.user.username) & Q(collect_movie=movie_name))

    page_object = Pagination(request, queryset)
    context = {
        "movie_name": movie_name,
        "collect": collect,
        "movie_information": movie_information,
        "queryset": page_object.page_queryset,  # 分页的数据
        "page_string": page_object.html()  # 页码
    }
    print('context', context)
    return render(request, 'front_details.html', context)


def collect(request):
    # 校验用户是否登录
    if not request.user.is_authenticated:
        return HttpResponse('请先登录')

    collect_user = request.user.username
    collect_movie = request.GET.get('movie_name')

    # 校验参数是否存在
    if not collect_movie:
        return HttpResponse('参数错误')

    queryset_collect = Collect.objects.filter(collect_user=collect_user)
    # 优化：使用get_or_create/filter.exists() 避免DoesNotExist异常
    try:
        list_movie = Movie.objects.get(title=collect_movie)
    except Movie.DoesNotExist:
        return HttpResponse('影片不存在')

    if queryset_collect.filter(collect_movie=collect_movie).exists():
        queryset_collect.filter(collect_movie=collect_movie).delete()  # 取消收藏
        # 取消收藏后重新生成推荐
        generate_recommendations(request.user.id)
        return HttpResponse('🤍 收藏')
    else:
        Collect.objects.create(
            collect_movie=collect_movie,
            collect_user=collect_user,
            movie_information=list_movie
        )
        # 收藏后重新生成推荐
        generate_recommendations(request.user.id)
        return HttpResponse('❤️ 取消收藏')


def comment_add(request):
    # 校验用户是否登录
    if not request.user.is_authenticated:
        messages.error(request, "请先登录后再发表评论！")
        return redirect('/login/')

    try:
        comment_score = request.GET.get('score', '')
        comment_discussion = request.GET.get('discuss', '')

        # 校验参数
        if not comment_score or not comment_discussion:
            messages.error(request, "评分和评论内容不能为空！")
            return redirect(request.META.get('HTTP_REFERER', '/front_index/'))

        # 校验session
        if "info" not in request.session:
            messages.error(request, "参数错误，请重新进入影片详情页！")
            return redirect('/front_index/')

        id = request.session["info"]["ID"]
        movie_ID = request.session["info"]["movie_ID"]
        comment_ID = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))

        # 优化：使用first()替代循环
        user_obj = UserInfo.objects.filter(username=request.user.username).first()
        if not user_obj:
            messages.error(request, "用户信息异常！")
            return redirect('/login/')

        # 获取电影名称
        movie_obj = Movie.objects.get(id=movie_ID)
        movie_name = movie_obj.title

        Comment.objects.create(
            comment_score=comment_score,
            discussion=comment_discussion,
            comment_user=request.user.username,
            movie=movie_name,
            comment_ID=comment_ID
        )

        # 修复：使用正确的URL路径
        return redirect(f'/movie/{id}/details/')  # 使用正确的URL路径格式
    # 精准捕获异常，而非宽泛的except
    except Exception as e:
        messages.error(request, f"发表评论失败：{str(e)}")
        return redirect(request.META.get('HTTP_REFERER', '/front_index/'))


def get_user_type_vector(user_id):
    """获取用户的类型偏好向量"""
    type_vector = {}
    all_types = ['动作', '喜剧', '爱情', '科幻', '恐怖', '剧情', '战争', '犯罪', '惊悚', '冒险', '悬疑', '武侠', '奇幻', '动画', '历史']
    
    # 初始化所有类型为0
    for t in all_types:
        type_vector[t] = 0
    
    # 获取用户的评分数据
    user_ratings = Rating.objects.filter(user_id=user_id)
    for rating in user_ratings:
        try:
            movie = Movie.objects.get(id=rating.movie_id)
            if movie.types:
                types = movie.types.split(' ')
                for t in types:
                    if t in type_vector:
                        type_vector[t] += rating.score * 0.1  # 评分权重
        except:
            pass
    
    # 获取用户的收藏数据（收藏权重更高）
    user = UserInfo.objects.get(id=user_id)
    user_collects = Collect.objects.filter(collect_user=user.username)
    for collect in user_collects:
        if collect.movie_information and collect.movie_information.types:
            types = collect.movie_information.types.split(' ')
            for t in types:
                if t in type_vector:
                    type_vector[t] += 1.0  # 收藏权重更高
    
    return type_vector


def calculate_similarity(user_id1, user_id2):
    """计算两个用户之间的相似度（基于类型偏好和共同电影）"""
    # 获取两个用户的评分数据
    user1_ratings = Rating.objects.filter(user_id=user_id1).values('movie_id', 'score')
    user2_ratings = Rating.objects.filter(user_id=user_id2).values('movie_id', 'score')
    
    # 获取两个用户的收藏数据（收藏视为10分）
    user1_collects = Collect.objects.filter(collect_user=UserInfo.objects.get(id=user_id1).username)
    user2_collects = Collect.objects.filter(collect_user=UserInfo.objects.get(id=user_id2).username)
    
    # 构建用户1的评分和收藏数据
    user1_scores = {}
    for rating in user1_ratings:
        user1_scores[rating['movie_id']] = rating['score']
    for collect in user1_collects:
        if collect.movie_information:
            user1_scores[collect.movie_information.id] = 10.0  # 收藏视为10分
    
    # 构建用户2的评分和收藏数据
    user2_scores = {}
    for rating in user2_ratings:
        user2_scores[rating['movie_id']] = rating['score']
    for collect in user2_collects:
        if collect.movie_information:
            user2_scores[collect.movie_information.id] = 10.0  # 收藏视为10分
    
    # 找出共同的电影
    common_movies = set(user1_scores.keys()) & set(user2_scores.keys())
    
    # 计算基于电影的相似度
    movie_similarity = 0
    if common_movies:
        # 计算平均评分
        user1_avg = sum(user1_scores.values()) / len(user1_scores)
        user2_avg = sum(user2_scores.values()) / len(user2_scores)

        # 计算皮尔逊相关系数
        numerator = 0
        denominator1 = 0
        denominator2 = 0

        for movie_id in common_movies:
            diff1 = user1_scores[movie_id] - user1_avg
            diff2 = user2_scores[movie_id] - user2_avg
            numerator += diff1 * diff2
            denominator1 += diff1 ** 2
            denominator2 += diff2 ** 2

        if denominator1 != 0 and denominator2 != 0:
            movie_similarity = numerator / (math.sqrt(denominator1) * math.sqrt(denominator2))
    
    # 计算基于类型偏好的相似度（余弦相似度）
    user1_type_vector = get_user_type_vector(user_id1)
    user2_type_vector = get_user_type_vector(user_id2)
    
    # 计算余弦相似度
    dot_product = 0
    norm1 = 0
    norm2 = 0
    
    for t in user1_type_vector:
        dot_product += user1_type_vector[t] * user2_type_vector[t]
        norm1 += user1_type_vector[t] ** 2
        norm2 += user2_type_vector[t] ** 2
    
    type_similarity = 0
    if norm1 > 0 and norm2 > 0:
        type_similarity = dot_product / (math.sqrt(norm1) * math.sqrt(norm2))
    
    # 综合相似度：电影相似度占60%，类型偏好相似度占40%
    # 如果没有共同电影，则完全依赖类型偏好
    if common_movies:
        return 0.6 * movie_similarity + 0.4 * type_similarity
    else:
        return type_similarity


def get_cold_start_recommendations(user_id, top_n=10):
    """冷启动兜底推荐：基于用户类型偏好的热门高分 + 新片优先"""
    # 获取用户已评分和已收藏的电影
    rated_movie_ids = set(Rating.objects.filter(user_id=user_id).values_list('movie_id', flat=True))
    collected_movie_ids = set()
    user_collects = Collect.objects.filter(collect_user=UserInfo.objects.get(id=user_id).username)
    for collect in user_collects:
        if collect.movie_information:
            collected_movie_ids.add(collect.movie_information.id)
    
    exclude_movie_ids = rated_movie_ids | collected_movie_ids
    
    # 分析用户的类型偏好
    user_preferred_types = {}
    # 分析已评分电影的类型
    for movie_id in rated_movie_ids:
        try:
            movie = Movie.objects.get(id=movie_id)
            if movie.types:
                types = movie.types.split(' ')
                for type in types:
                    user_preferred_types[type] = user_preferred_types.get(type, 0) + 1
        except:
            pass
    
    # 分析已收藏电影的类型（权重更高）
    for movie_id in collected_movie_ids:
        try:
            movie = Movie.objects.get(id=movie_id)
            if movie.types:
                types = movie.types.split(' ')
                for type in types:
                    user_preferred_types[type] = user_preferred_types.get(type, 0) + 2  # 收藏权重更高
        except:
            pass
    
    # 根据类型偏好排序
    sorted_types = sorted(user_preferred_types.items(), key=lambda x: x[1], reverse=True)
    preferred_types = [t[0] for t in sorted_types[:2]]  # 取前两个偏好类型
    
    # 优先推荐用户偏好类型的电影
    if preferred_types:
        # 先获取偏好类型的电影
        preferred_movies = list(
            Movie.objects.filter(types__icontains=preferred_types[0])
            .exclude(id__in=exclude_movie_ids)
            .order_by('-score', '-date')
            .values_list('id', flat=True)
        )
        
        # 如果第一个偏好类型的电影不够，添加第二个偏好类型的电影
        if len(preferred_movies) < top_n and len(preferred_types) > 1:
            second_preferred_movies = list(
                Movie.objects.filter(types__icontains=preferred_types[1])
                .exclude(id__in=exclude_movie_ids | set(preferred_movies))
                .order_by('-score', '-date')
                .values_list('id', flat=True)
            )
            preferred_movies.extend(second_preferred_movies)
        
        # 如果偏好类型的电影不够，添加其他热门电影
        if len(preferred_movies) < top_n:
            other_movies = list(
                Movie.objects.exclude(id__in=exclude_movie_ids | set(preferred_movies))
                .order_by('-score', '-date')
                .values_list('id', flat=True)[:top_n - len(preferred_movies)]
            )
            preferred_movies.extend(other_movies)
        
        return preferred_movies[:top_n]
    else:
        # 如果没有偏好类型，返回热门高分电影
        return list(
            Movie.objects.exclude(id__in=exclude_movie_ids)
            .order_by('-score', '-date')
            .values_list('id', flat=True)[:top_n]
        )


def generate_recommendations(user_id, top_n=10):
    """基于用户的协同过滤生成推荐（包含类型偏好加权）"""
    try:
        current_user = UserInfo.objects.get(id=user_id)
        other_users = UserInfo.objects.exclude(id=user_id)

        # 获取当前用户的类型偏好
        current_user_type_vector = get_user_type_vector(user_id)
        
        similarities = []
        for other_user in other_users:
            sim = calculate_similarity(user_id, other_user.id)
            if sim > 0:
                similarities.append((other_user.id, sim))

        if not similarities:
            return []   # 没有相似用户

        similarities.sort(key=lambda x: x[1], reverse=True)
        K = 5
        top_similar_users = similarities[:K]

        # 获取用户已评分和已收藏的电影，这些电影不应该被推荐
        current_user_rated_movies = set(Rating.objects.filter(user_id=user_id).values_list('movie_id', flat=True))
        current_user_collected_movies = set()
        user_collects = Collect.objects.filter(collect_user=current_user.username)
        for collect in user_collects:
            if collect.movie_information:
                current_user_collected_movies.add(collect.movie_information.id)
        
        # 合并已评分和已收藏的电影
        exclude_movies = current_user_rated_movies | current_user_collected_movies
        
        candidate_movies = {}

        for user_id_sim, sim_score in top_similar_users:
            # 获取相似用户的评分
            user_ratings = Rating.objects.filter(user_id=user_id_sim)
            for rating in user_ratings:
                if rating.movie_id not in exclude_movies:
                    # 基础分数
                    base_score = sim_score * rating.score
                    
                    # 根据类型偏好加权
                    try:
                        movie = Movie.objects.get(id=rating.movie_id)
                        if movie.types:
                            types = movie.types.split(' ')
                            type_bonus = 0
                            for t in types:
                                if t in current_user_type_vector and current_user_type_vector[t] > 0:
                                    type_bonus += current_user_type_vector[t] * 0.5  # 类型偏好加成
                            base_score += type_bonus
                    except:
                        pass
                    
                    candidate_movies[rating.movie_id] = candidate_movies.get(rating.movie_id, 0) + base_score
            
            # 获取相似用户的收藏（收藏视为10分）
            sim_user_collects = Collect.objects.filter(collect_user=UserInfo.objects.get(id=user_id_sim).username)
            for collect in sim_user_collects:
                if collect.movie_information and collect.movie_information.id not in exclude_movies:
                    # 基础分数
                    base_score = sim_score * 10.0
                    
                    # 根据类型偏好加权
                    if collect.movie_information.types:
                        types = collect.movie_information.types.split(' ')
                        type_bonus = 0
                        for t in types:
                            if t in current_user_type_vector and current_user_type_vector[t] > 0:
                                type_bonus += current_user_type_vector[t] * 0.5  # 类型偏好加成
                        base_score += type_bonus
                    
                    candidate_movies[collect.movie_information.id] = candidate_movies.get(collect.movie_information.id, 0) + base_score

        if not candidate_movies:
            return []   # 没有候选电影

        sorted_candidates = sorted(candidate_movies.items(), key=lambda x: x[1], reverse=True)
        top_recommendations = sorted_candidates[:top_n]

        # 保存推荐结果到CfRec表
        CfRec.objects.filter(user_id=user_id).delete()
        for movie_id, score in top_recommendations:
            CfRec.objects.create(user_id=user_id, movie_id=movie_id, rating=score)

        return [movie_id for movie_id, _ in top_recommendations]

    except Exception as e:
        print(f"协同过滤推荐生成错误: {str(e)}")
        return []

def recommend(request):
    try:
        if not request.user.is_authenticated:
            return redirect('/login/')

        user_id = request.user.id
        top_n = 10

        # 获取用户已收藏的电影，这些电影不应该被推荐
        current_user = UserInfo.objects.get(id=user_id)
        current_user_collected_movies = set()
        user_collects = Collect.objects.filter(collect_user=current_user.username)
        for collect in user_collects:
            if collect.movie_information:
                current_user_collected_movies.add(collect.movie_information.id)

        # 1. 优先实时生成协同过滤推荐
        realtime_rec_ids = generate_recommendations(user_id, top_n=top_n)

        if realtime_rec_ids:
            # 实时生成成功，直接使用
            recommended_movie_ids = realtime_rec_ids
        else:
            # 2. 实时生成失败（无相似用户/无候选电影/异常），尝试从 CfRec 表读取缓存
            cf_rec_ids = list(
                CfRec.objects.filter(user_id=user_id)
                .order_by('-rating')
                .values_list('movie_id', flat=True)[:top_n]
            )
            if cf_rec_ids:
                # 从缓存中排除已收藏的电影
                recommended_movie_ids = [movie_id for movie_id in cf_rec_ids if movie_id not in current_user_collected_movies]
            else:
                # 3. 缓存也没有，使用冷启动兜底推荐（热门高分等）
                recommended_movie_ids = get_cold_start_recommendations(user_id, top_n=top_n)
                # 可选：将冷启动结果也保存到 CfRec 表，以便下次直接使用
                CfRec.objects.filter(user_id=user_id).delete()
                for idx, movie_id in enumerate(recommended_movie_ids):
                    CfRec.objects.create(user_id=user_id, movie_id=movie_id, rating=float(top_n - idx))

        # 确保最终推荐结果中不包含已收藏的电影
        recommended_movie_ids = [movie_id for movie_id in recommended_movie_ids if movie_id not in current_user_collected_movies]
        
        # 如果过滤后推荐数量不足，从冷启动推荐中补充
        if len(recommended_movie_ids) < top_n:
            cold_start_ids = get_cold_start_recommendations(user_id, top_n=top_n)
            # 过滤掉已收藏的电影和已经在推荐列表中的电影
            additional_ids = [movie_id for movie_id in cold_start_ids 
                            if movie_id not in current_user_collected_movies 
                            and movie_id not in recommended_movie_ids]
            recommended_movie_ids.extend(additional_ids)
            # 截取前top_n个
            recommended_movie_ids = recommended_movie_ids[:top_n]

        # 获取电影详情并保持顺序
        movie_map = {movie.id: movie for movie in Movie.objects.filter(id__in=recommended_movie_ids)}
        data_list = [movie_map[movie_id] for movie_id in recommended_movie_ids if movie_id in movie_map]

        print(f'推荐数据：{data_list}')
        return render(request, 'front_recommendation.html', {'data_list': data_list})

    except Exception as e:
        print(f'推荐功能错误：{str(e)}')
        return render(request, 'front_recommendation.html', {'data_list': []})


def result(request):
    """搜索结果页面"""
    search_keyword = request.GET.get('search', '')
    if search_keyword:
        # 模糊搜索：支持按电影名、演员名检索
        keyword = search_keyword.strip()
        queryset = Movie.objects.filter(
            Q(title__icontains=keyword) |
            Q(actors__icontains=keyword)
        ).distinct()
    else:
        queryset = Movie.objects.none()
    
    context = {
        'search_keyword': search_keyword,
        'queryset': queryset,

        'count': queryset.count()
    }
    return render(request, 'front_result.html', context)


def center(request):
    # 检查用户是否登录
    if not request.user.is_authenticated:
        messages.error(request, "请先登录")
        return redirect('/login/')
    
    queryset_user = UserInfo.objects.filter(username=request.user.username)
    queryset_comment = Comment.objects.filter(comment_user=request.user.username)
    queryset_collect = Collect.objects.filter(collect_user=request.user.username)
    
    # 为每个评论添加对应的电影信息
    comment_list = list(queryset_comment)
    for comment in comment_list:
        # 根据电影名称查询电影信息
        try:
            movie = Movie.objects.filter(title=comment.movie).first()
            comment.movie_info = movie
        except Exception as e:
            comment.movie_info = None
    
    # 分页处理
    page_object = Pagination(request, comment_list)

    context = {
        "queryset_user": queryset_user,
        "queryset_collect": queryset_collect,
        "queryset": page_object.page_queryset, # 分完页的数据
        "page_string": page_object.html() # 页码
    }

    return render(request, 'front_center.html', context)


def board_add(request):
    board_mes = request.GET.get('boardMessage', '')
    if not board_mes:
        messages.warning(request, '留言失败,请输入内容')
        return HttpResponseRedirect('/center/')
    else:
        board_ID = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))
        Board.objects.create(board_message=board_mes, board_user=request.user.username, board_ID=board_ID)
        messages.success(request, '留言成功')
        return HttpResponseRedirect('/center/')


def admin_index(request):
    time = datetime.now()
    movie_num = Movie.objects.count()
    board_num = Board.objects.count()
    user_num = UserInfo.objects.count()
    comment_num = Comment.objects.count()  # 修复：添加括号
    # 获取最近更新的电影（按id倒序取前10条）
    latest_movies = Movie.objects.order_by('-id')[:10]
    context = {
        "movie_num": movie_num,
        "board_num": board_num,
        "user_num": user_num,
        "comment_num": comment_num,
        "current_time": time,
        "latest_movies": latest_movies
    }
    return render(request, 'admin_index.html', context)

class MovieModelForm(forms.ModelForm):
    # 定义类型选择项
    TYPE_CHOICES = [
        ('动作', '动作'), ('喜剧', '喜剧'), ('爱情', '爱情'),
        ('科幻', '科幻'), ('恐怖', '恐怖'), ('剧情', '剧情'),
        ('战争', '战争'), ('犯罪', '犯罪'), ('惊悚', '惊悚'),
        ('冒险', '冒险'), ('悬疑', '悬疑'), ('武侠', '武侠'),
        ('奇幻', '奇幻'), ('动画', '动画'), ('历史', '历史')
    ]
    
    # 定义地区选择项
    REGION_CHOICES = [
        ('大陆', '大陆'), ('香港', '香港'), ('台湾', '台湾'),
        ('美国', '美国'), ('法国', '法国'), ('英国', '英国'),
        ('日本', '日本'), ('韩国', '韩国'), ('德国', '德国'),
        ('泰国', '泰国'), ('印度', '印度'), ('意大利', '意大利'),
        ('西班牙', '西班牙'), ('加拿大', '加拿大')
    ]
    
    # 替换原有字段为选择字段
    types = forms.ChoiceField(choices=TYPE_CHOICES, label='类型', required=False)
    regions = forms.ChoiceField(choices=REGION_CHOICES, label='地区', required=False)
    
    # 添加director字段（数据库中存在但模型中未定义）
    director = forms.CharField(label='导演', required=False, max_length=255)
    
    # 添加文件选择器字段用于海报上传
    poster_file = forms.FileField(label='海报文件', required=False)
    
    class Meta:
        model = Movie
        fields = ['title', 'director', 'actors', 'types', 'regions', 'score', 'date', 'poster', 'summary']  # 包含director字段

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 循环找到所有的插件，添加了class="form-control"
        for name, field in self.fields.items():
            if name != 'poster_file':  # 为除了poster_file之外的字段添加样式
                field.widget.attrs = {"class": "form-control", "placeholder": field.label}
        # 为poster_file字段添加特殊样式
        self.fields['poster_file'].widget.attrs = {"class": "form-control-file"}
        # 为date字段添加日期选择器样式
        self.fields['date'].widget.attrs = {"class": "form-control", "type": "date"}

def admin_movie(request):
    """查询所有电影并分页展示"""
    data_dict = {}
    search_data = request.GET.get('search', "")
    if search_data:
        data_dict["title__contains"] = search_data  # 修复：使用正确的字段名title
    queryset = Movie.objects.filter(**data_dict)
    page_object = Pagination(request, queryset)
    form = MovieModelForm()
    context = {
        "form": form,
        "search_data": search_data,
        "queryset": page_object.page_queryset,  # 分页后的数据
        "page_string": page_object.html()  # 分页码
    }
    return render(request, 'admin_movie.html', context)

@csrf_exempt
def admin_movie_add(request):
    """添加电影"""
    try:
        form = MovieModelForm(data=request.POST, files=request.FILES)  # 修复：添加files参数支持文件上传
        if form.is_valid():
            # 获取director字段值
            director = request.POST.get('director', '')
            
            # 处理海报文件上传
            if 'poster_file' in request.FILES:
                poster_file = request.FILES['poster_file']
                # 确保上传目录存在
                upload_dir = os.path.join('static', 'assets', 'movie_posters')
                os.makedirs(upload_dir, exist_ok=True)
                # 生成唯一文件名
                file_ext = os.path.splitext(poster_file.name)[1]
                file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}{file_ext}"
                # 保存文件
                file_path = os.path.join(upload_dir, file_name)
                try:
                    with open(file_path, 'wb+') as destination:
                        for chunk in poster_file.chunks():
                            destination.write(chunk)
                    # 使用pymysql直接插入电影记录，包括director字段
                    config = {
                        'host': 'localhost',
                        'user': 'root',
                        'password': '123456',
                        'database': 'django_movie',
                        'charset': 'utf8mb4',
                        'cursorclass': pymysql.cursors.DictCursor
                    }
                    connection = pymysql.connect(**config)
                    with connection.cursor() as cursor:
                        # 插入电影记录
                        insert_sql = """
                        INSERT INTO myapp_movie (title, director, actors, types, regions, score, date, poster, summary)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        values = (
                            request.POST.get('title', ''),
                            director,
                            request.POST.get('actors', ''),
                            request.POST.get('types', ''),
                            request.POST.get('regions', ''),
                            request.POST.get('score', None),
                            request.POST.get('date', None),
                            f"assets/movie_posters/{file_name}",
                            request.POST.get('summary', '')
                        )
                        cursor.execute(insert_sql, values)
                        connection.commit()
                except Exception as e:
                    return JsonResponse({"status": False, 'error': f"文件保存失败: {str(e)}"})
            else:
                # 没有上传海报，使用默认值
                # 使用pymysql直接插入电影记录，包括director字段
                config = {
                    'host': 'localhost',
                    'user': 'root',
                    'password': '123456',
                    'database': 'django_movie',
                    'charset': 'utf8mb4',
                    'cursorclass': pymysql.cursors.DictCursor
                }
                connection = pymysql.connect(**config)
                with connection.cursor() as cursor:
                    # 插入电影记录
                    insert_sql = """
                    INSERT INTO myapp_movie (title, director, actors, types, regions, score, date, poster, summary)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    values = (
                        request.POST.get('title', ''),
                        director,
                        request.POST.get('actors', ''),
                        request.POST.get('types', ''),
                        request.POST.get('regions', ''),
                        request.POST.get('score', None),
                        request.POST.get('date', None),
                        request.POST.get('poster', 'assets/movie_posters/default.jpg'),
                        request.POST.get('summary', '')
                    )
                    cursor.execute(insert_sql, values)
                    connection.commit()
            return JsonResponse({"status": True})
        else:
            return JsonResponse({"status": False, 'error': form.errors})
    except Exception as e:
        return JsonResponse({"status": False, 'error': f"添加电影失败: {str(e)}"})

def admin_movie_delete(request):
    """删除电影"""
    uid = request.GET.get('uid')
    exists = Movie.objects.filter(id=uid).exists()  # 修复：使用id字段
    if not exists:
        return JsonResponse({"status": False, 'error': "删除失败,数据不存在。"})

    Movie.objects.filter(id=uid).delete()  # 修复：使用id字段
    return JsonResponse({"status": True})

def admin_movie_detail(request):
    """电影详情"""
    uid = request.GET.get("uid")
    try:
        # 确保uid被转换为整数类型
        movie_id = int(uid)
        row_object = Movie.objects.filter(id=movie_id).first()
        if not row_object:
            return JsonResponse({"status": False, 'error': "数据不存在。"})
        
        # 获取director字段（数据库中存在但模型中未定义）
        director = ""
        try:
            config = {
                'host': 'localhost',
                'user': 'root',
                'password': '123456',
                'database': 'django_movie',
                'charset': 'utf8mb4',
                'cursorclass': pymysql.cursors.DictCursor
            }
            connection = pymysql.connect(**config)
            with connection.cursor() as cursor:
                select_sql = "SELECT director FROM myapp_movie WHERE id = %s"
                cursor.execute(select_sql, (movie_id,))
                result = cursor.fetchone()
                if result:
                    director = result.get('director', '')
        except Exception as e:
            # 获取director失败不影响其他数据
            pass
    except (ValueError, TypeError):
        return JsonResponse({"status": False, 'error': "无效的电影ID。"})

    # 从数据库中获取到一个对象 row_object
    result = {
        "status": True,
        "data": {
            "title": row_object.title,
            "director": director,
            "actors": row_object.actors,
            "types": row_object.types,
            "regions": row_object.regions,
            "date": row_object.date.strftime('%Y-%m-%d') if row_object.date else '',
            "score": row_object.score,
            "poster": row_object.poster,
            "summary": row_object.summary
        }
    }
    return JsonResponse(result)

@csrf_exempt
def admin_movie_edit(request):
    """编辑电影"""
    uid = request.GET.get("uid")
    row_object = Movie.objects.filter(id=uid).first()  # 修复：使用id字段
    if not row_object:
        return JsonResponse({"status": False, 'tips': "数据不存在,请刷新重试。"})

    form = MovieModelForm(data=request.POST, files=request.FILES, instance=row_object)  # 修复：添加files参数支持文件上传
    if form.is_valid():
        form.save()
        return JsonResponse({"status": True})

    return JsonResponse({"status": False, 'error': form.errors})

class UserModelForm(forms.ModelForm):
    class Meta:
        model = UserInfo
        fields = ["password"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs = {"class": "form-control", "placeholder": field.label}

def admin_users(request):
    """用户管理页面"""
    # 权限控制：只有超级管理员可以访问
    if not request.user.is_authenticated or not request.user.is_superuser:
        messages.error(request, "权限不足，只有超级管理员可以管理用户")
        return redirect('/front_index/')

    data_dict = {}
    search_data = request.GET.get('search', "")
    if search_data:
        data_dict["username__contains"] = search_data

    queryset = UserInfo.objects.filter(**data_dict)
    page_object = Pagination(request, queryset)
    form = UserModelForm()
    context = {
        "form": form,
        "search_data": search_data,
        "queryset": page_object.page_queryset,
        "page_string": page_object.html()
    }
    return render(request, 'admin_users.html', context)

def admin_users_delete(request):
    """删除用户"""
    # 权限控制：只有超级管理员可以操作
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({"status": False, "error": "权限不足，只有超级管理员可以删除用户"})

    uid = request.GET.get('uid')
    try:
        # 使用pymysql直接连接数据库删除用户，绕过Django ORM的MySQL兼容性问题
        # 数据库连接配置
        config = {
            'host': 'localhost',
            'user': 'root',
            'password': '123456',
            'database': 'django_movie',
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }
        
        connection = pymysql.connect(**config)
        with connection.cursor() as cursor:
            # 检查用户是否已存在
            check_sql = "SELECT * FROM myapp_userinfo WHERE user_ID = %s"
            cursor.execute(check_sql, (uid,))
            if not cursor.fetchone():
                return JsonResponse({"status": False, 'error': "删除失败,数据不存在."})
            
            # 删除用户记录
            delete_sql = "DELETE FROM myapp_userinfo WHERE user_ID = %s"
            cursor.execute(delete_sql, (uid,))
            connection.commit()
        
        return JsonResponse({"status": True})
    except Exception as e:
        return JsonResponse({"status": False, 'error': str(e)})

def admin_users_reset(request):
    """重置用户密码"""
    # 权限控制：只有超级管理员可以操作
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({"status": False, "error": "权限不足，只有超级管理员可以重置用户密码"})

    uid = request.GET.get('uid')
    try:
        # 使用Django的make_password函数对密码进行哈希处理
        from django.contrib.auth.hashers import make_password
        hashed_password = make_password('123456')
        
        # 使用pymysql直接连接数据库重置密码，绕过Django ORM的MySQL兼容性问题
        # 数据库连接配置
        config = {
            'host': 'localhost',
            'user': 'root',
            'password': '123456',
            'database': 'django_movie',
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }
        
        connection = pymysql.connect(**config)
        with connection.cursor() as cursor:
            # 检查用户是否已存在
            check_sql = "SELECT * FROM myapp_userinfo WHERE user_ID = %s"
            cursor.execute(check_sql, (uid,))
            if not cursor.fetchone():
                return JsonResponse({"status": False, 'error': "重置失败,数据不存在."})
            
            # 更新用户密码
            update_sql = "UPDATE myapp_userinfo SET password = %s WHERE user_ID = %s"
            cursor.execute(update_sql, (hashed_password, uid))
            connection.commit()
        
        return JsonResponse({"status": True})
    except Exception as e:
        return JsonResponse({"status": False, 'error': str(e)})


def admin_admins(request):
    """管理员管理页面"""
    # 权限控制：只有管理员可以访问
    if not request.user.is_authenticated or not request.user.is_staff:
        messages.error(request, "权限不足，无法访问此页面")
        return redirect('/front_index/')
    
    # 获取所有管理员用户（is_staff=True）
    data_dict = {}
    search_data = request.GET.get('search', "")
    if search_data:
        data_dict["username__contains"] = search_data
    
    queryset = UserInfo.objects.filter(is_staff=True, **data_dict)
    page_object = Pagination(request, queryset)
    form = UserModelForm()
    
    context = {
        "form": form,
        "search_data": search_data,
        "queryset": page_object.page_queryset,
        "page_string": page_object.html()
    }
    
    return render(request, 'admin_admins.html', context)





@csrf_exempt
def admin_admin_add(request):
    """添加管理员"""
    # 权限控制：只有管理员可以访问
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"status": False, "error": "权限不足"})
    
    # 获取表单数据
    username = request.POST.get("username")
    password = request.POST.get("password")
    email = request.POST.get("email")
    nickname = request.POST.get("nickname", username)
    is_superuser = request.POST.get("is_superuser", "false").lower() == "true"
    
    # 验证参数
    if not username or not password or not email:
        return JsonResponse({"status": False, "error": "用户名、密码和邮箱不能为空"})
    
    # 权限控制：只有超级管理员可以创建超级管理员
    if is_superuser and not request.user.is_superuser:
        return JsonResponse({"status": False, "error": "权限不足，无法创建超级管理员"})
    
    try:
        # 生成用户ID
        user_ID = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))
        
        # 使用Django的make_password函数对密码进行哈希处理
        from django.contrib.auth.hashers import make_password
        hashed_password = make_password(password)
        
        # 使用pymysql直接连接数据库创建用户，绕过Django ORM的MySQL兼容性问题
        # 数据库连接配置
        config = {
            'host': 'localhost',
            'user': 'root',
            'password': '123456',
            'database': 'django_movie',
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }
        
        connection = pymysql.connect(**config)
        with connection.cursor() as cursor:
            # 检查用户是否已存在
            check_sql = "SELECT * FROM myapp_userinfo WHERE username = %s"
            cursor.execute(check_sql, (username,))
            if cursor.fetchone():
                return JsonResponse({"status": False, "error": "用户名已存在"})
            
            check_sql = "SELECT * FROM myapp_userinfo WHERE email = %s"
            cursor.execute(check_sql, (email,))
            if cursor.fetchone():
                return JsonResponse({"status": False, "error": "邮箱已存在"})
            
            # 插入用户记录
            insert_sql = """
            INSERT INTO myapp_userinfo (
                user_ID, username, nickname, email, password, sex, 
                is_staff, is_superuser, is_active, registration
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                user_ID, username, nickname, email, 
                hashed_password, 1, True, is_superuser, True, datetime.now()
            )
            
            cursor.execute(insert_sql, values)
            connection.commit()
        
        return JsonResponse({"status": True})
    except Exception as e:
        return JsonResponse({"status": False, "error": str(e)})


class AdminModelForm(forms.ModelForm):
    """管理员添加表单"""
    class Meta:
        model = UserInfo
        fields = ["username", "password", "email", "nickname"]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs = {"class": "form-control", "placeholder": field.label}


def admin_admin_delete(request):
    """删除管理员"""
    # 权限控制：只有超级管理员可以删除管理员
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({"status": False, "error": "权限不足，只有超级管理员可以删除管理员"})
    
    uid = request.GET.get('uid')
    try:
        # 使用pymysql直接连接数据库删除管理员，绕过Django ORM的MySQL兼容性问题
        # 数据库连接配置
        config = {
            'host': 'localhost',
            'user': 'root',
            'password': '123456',
            'database': 'django_movie',
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }
        
        connection = pymysql.connect(**config)
        with connection.cursor() as cursor:
            # 检查管理员是否已存在
            check_sql = "SELECT * FROM myapp_userinfo WHERE user_ID = %s"
            cursor.execute(check_sql, (uid,))
            user_data = cursor.fetchone()
            if not user_data:
                return JsonResponse({"status": False, 'error': "删除失败,数据不存在."})
            
            # 权限控制：只有超级管理员可以删除超级管理员
            if user_data['is_superuser'] and not request.user.is_superuser:
                return JsonResponse({"status": False, 'error': "权限不足，无法删除超级管理员"})
            
            # 不允许删除当前登录的超级管理员
            if user_data['is_superuser'] and user_data['username'] == request.user.username:
                return JsonResponse({"status": False, 'error': "无法删除当前登录的超级管理员"})
            
            # 删除管理员记录
            delete_sql = "DELETE FROM myapp_userinfo WHERE user_ID = %s"
            cursor.execute(delete_sql, (uid,))
            connection.commit()
        
        return JsonResponse({"status": True})
    except Exception as e:
        return JsonResponse({"status": False, 'error': str(e)})


def rate_movie(request):
    """电影评分功能"""
    if not request.user.is_authenticated:
        return JsonResponse({"status": False, "error": "请先登录"})
    
    # GET请求：获取用户对电影的评分
    if request.method == 'GET':
        movie_id = request.GET.get('movie_id')
        if not movie_id:
            return JsonResponse({"status": False, "error": "参数错误"})
        
        try:
            rating = Rating.objects.get(user=request.user, movie_id=movie_id)
            return JsonResponse({"status": True, "score": rating.score})
        except Rating.DoesNotExist:
            return JsonResponse({"status": True, "score": 0})
        except Exception as e:
            return JsonResponse({"status": False, "error": str(e)})
    
    # POST请求：提交评分
    elif request.method == 'POST':
        movie_id = request.POST.get('movie_id')
        score = request.POST.get('score')
        
        if not movie_id or not score:
            return JsonResponse({"status": False, "error": "参数错误"})
        
        try:
            score = float(score)
            if score < 0 or score > 10:
                return JsonResponse({"status": False, "error": "评分必须在0-10之间"})
            
            # 查找或创建评分记录
            rating, created = Rating.objects.update_or_create(
                user=request.user,
                movie_id=movie_id,
                defaults={'score': score}
            )
            
            # 重新生成推荐
            generate_recommendations(request.user.id)
            
            # 返回评分结果，包括评分值
            return JsonResponse({"status": True, "score": score})
        except Exception as e:
            return JsonResponse({"status": False, "error": str(e)})
    
    return JsonResponse({"status": False, "error": "请求方法错误"})


def admin_admin_reset(request):
    """重置管理员密码"""
    # 权限控制：只有管理员可以访问
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"status": False, "error": "权限不足"})
    
    uid = request.GET.get('uid')
    try:
        # 使用Django的make_password函数对密码进行哈希处理
        from django.contrib.auth.hashers import make_password
        hashed_password = make_password('123456')
        
        # 使用pymysql直接连接数据库重置密码，绕过Django ORM的MySQL兼容性问题
        # 数据库连接配置
        config = {
            'host': 'localhost',
            'user': 'root',
            'password': '123456',
            'database': 'django_movie',
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor
        }
        
        connection = pymysql.connect(**config)
        with connection.cursor() as cursor:
            # 检查管理员是否已存在
            check_sql = "SELECT * FROM myapp_userinfo WHERE user_ID = %s"
            cursor.execute(check_sql, (uid,))
            user_data = cursor.fetchone()
            if not user_data:
                return JsonResponse({"status": False, 'error': "重置失败,数据不存在."})
            
            # 普通管理员只能重置自己的密码，不能操作超级管理员和其他普通管理员
            if not request.user.is_superuser and user_data['username'] != request.user.username:
                return JsonResponse({"status": False, "error": "权限不足，普通管理员只能重置自己的密码"})

            # 权限控制：只有超级管理员可以重置超级管理员的密码
            if user_data['is_superuser'] and not request.user.is_superuser:
                return JsonResponse({"status": False, "error": "权限不足，无法重置超级管理员的密码"})
            
            # 更新管理员密码
            update_sql = "UPDATE myapp_userinfo SET password = %s WHERE user_ID = %s"
            cursor.execute(update_sql, (hashed_password, uid))
            connection.commit()
        
        return JsonResponse({"status": True})
    except Exception as e:
        return JsonResponse({"status": False, 'error': str(e)})


# def calculate_similarity(user_id1, user_id2):
#     """计算两个用户之间的相似度（皮尔逊相关系数）"""
#     # 获取两个用户都评分过的电影
#     user1_ratings = Rating.objects.filter(user_id=user_id1).values('movie_id', 'score')
#     user2_ratings = Rating.objects.filter(user_id=user_id2).values('movie_id', 'score')
#
#     # 找出共同评分的电影
#     common_movies = set()
#     user1_scores = {}
#     user2_scores = {}
#
#     for rating in user1_ratings:
#         user1_scores[rating['movie_id']] = rating['score']
#         common_movies.add(rating['movie_id'])
#
#     for rating in user2_ratings:
#         if rating['movie_id'] in common_movies:
#             user2_scores[rating['movie_id']] = rating['score']
#
#     # 如果没有共同评分的电影，相似度为0
#     if not common_movies:
#         return 0
#
#     # 计算平均评分
#     user1_avg = sum(user1_scores.values()) / len(user1_scores)
#     user2_avg = sum(user2_scores.values()) / len(user2_scores)
#
#     # 计算皮尔逊相关系数
#     numerator = 0
#     denominator1 = 0
#     denominator2 = 0
#
#     for movie_id in common_movies:
#         if movie_id in user1_scores and movie_id in user2_scores:
#             diff1 = user1_scores[movie_id] - user1_avg
#             diff2 = user2_scores[movie_id] - user2_avg
#             numerator += diff1 * diff2
#             denominator1 += diff1 ** 2
#             denominator2 += diff2 ** 2
#
#     if denominator1 == 0 or denominator2 == 0:
#         return 0
#
#     return numerator / (math.sqrt(denominator1) * math.sqrt(denominator2))
# filter(user_id=user_id_sim)
#             for rating in user_ratings:
#                 if rating.movie_id not in current_user_rated_movies:
#                     if rating.movie_id not in candidate_movies:
#                         candidate_movies[rating.movie_id] = 0
#                     # 加权累加评分
#                     candidate_movies[rating.movie_id] += sim_score * rating.score
#
#         # 按推荐分数排序
#         sorted_candidates = sorted(candidate_movies.items(), key=lambda x: x[1], reverse=True)
#
#         # 获取前N个推荐电影
#         top_recommendations = sorted_candidates[:top_n]
#
#         # 冷启动兜底：没有相似用户/没有候选电影时，回退到热门高分推荐
#         if not top_recommendations:
#             fallback_ids = get_cold_start_recommendations(user_id, top_n=top_n)
#             CfRec.objects.filter(user_id=user_id).delete()
#             for idx, movie_id in enumerate(fallback_ids):
#                 CfRec.objects.create(user_id=user_id, movie_id=movie_id, rating=float(top_n - idx))
#             return fallback_ids
#
#         # 保存推荐结果到CfRec表
#         CfRec.objects.filter(user_id=user_id).delete()  # 清除旧推荐
#         for movie_id, score in top_recommendations:
#             CfRec.objects.create(user_id=user_id, movie_id=movie_id, rating=score)
#
#         return [movie_id for movie_id, _ in top_recommendations]
#     except Exception as e:
#         print(f"推荐生成错误: {str(e)}")
#         return []


def admin_comments(request):
    """评论管理页面"""
    # 权限控制：只有管理员可以访问
    if not request.user.is_authenticated or not request.user.is_staff:
        messages.error(request, "权限不足，无法访问此页面")
        return redirect('/front_index/')
    
    # 获取评论数据
    queryset = Comment.objects.order_by('-comment_time')
    
    # 分页处理
    page = request.GET.get('page', '1')
    page_size = 10
    page_object = Pagination(request, queryset, page_size=page_size, page_param="page")
    
    context = {
        "queryset": page_object.page_queryset,
        "page_string": page_object.html(),
    }
    
    return render(request, 'admin_comments.html', context)


def admin_comment_delete(request):
    """删除评论"""
    # 权限控制：只有管理员可以操作
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"status": False, "error": "权限不足，无法删除评论"})
    
    comment_id = request.GET.get('comment_id')
    if not comment_id:
        return JsonResponse({"status": False, "error": "参数错误"})
    
    try:
        # 查找并删除评论
        comment = Comment.objects.filter(comment_ID=comment_id).first()
        if not comment:
            return JsonResponse({"status": False, "error": "评论不存在"})
        
        comment.delete()
        return JsonResponse({"status": True})
    except Exception as e:
        return JsonResponse({"status": False, "error": str(e)})
