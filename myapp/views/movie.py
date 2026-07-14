"""
前台电影模块：首页、排行榜、分类筛选、电影详情、搜索、收藏、评论、评分
"""
import random
import os
from datetime import datetime

from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Q

from ..models import Movie, UserInfo, Comment, Collect, Rating
from ..pagination import Pagination


# ============================================================
# 首页
# ============================================================
def index(request):
    queryset_hot = Movie.objects.order_by('-date')[:8]
    queryset_high = Movie.objects.order_by('-score')[:8]
    return render(request, 'front_index.html', {
        "queryset_hot": queryset_hot,
        "queryset_high": queryset_high
    })


def front_index(request):
    return index(request)


# ============================================================
# 排行榜
# ============================================================
def rank(request):
    tab = request.GET.get('tab', 'home')
    page_size = 10

    # 类型 → QuerySet 映射
    type_tabs = {
        'action': '动作', 'comedy': '喜剧', 'love': '爱情',
        'scienceFiction': '科幻', 'terror': '恐怖', 'plot': '剧情',
        'war': '战争', 'crime': '犯罪', 'thriller': '惊悚',
        'cartoon': '动画', 'history': '历史',
    }

    if tab == 'home':
        queryset = Movie.objects.order_by('-score')
    elif tab in type_tabs:
        queryset = Movie.objects.filter(types__contains=type_tabs[tab]).order_by('-score')
    else:
        queryset = Movie.objects.order_by('-score')

    page_object = Pagination(request, queryset, page_size=page_size, page_param="page")

    return render(request, 'front_rank.html', {
        "active_tab": tab,
        "page_queryset": page_object.page_queryset,
        "page_string": page_object.html(),
    })


# ============================================================
# 电影库（分类筛选）
# ============================================================
def depot(request, *args, **kwargs):
    if not kwargs:
        kwargs = {
            'depot_type_ID': '0',
            'depot_region_ID': '0',
            'depot_time_ID': '0',
        }

    type_ID = kwargs.get('depot_type_ID')
    region_ID = kwargs.get('depot_region_ID')
    time_ID = kwargs.get('depot_time_ID')

    type_list = [{"ID": 1, "type": '动作'}, {"ID": 2, "type": '喜剧'}, {"ID": 3, "type": '爱情'},
                 {"ID": 4, "type": '科幻'}, {"ID": 5, "type": '恐怖'}, {"ID": 6, "type": '剧情'},
                 {"ID": 7, "type": '战争'}, {"ID": 8, "type": '犯罪'}, {"ID": 9, "type": '惊悚'},
                 {"ID": 10, "type": '冒险'}, {"ID": 11, "type": '悬疑'}, {"ID": 12, "type": '武侠'},
                 {"ID": 13, "type": '奇幻'}, {"ID": 14, "type": '动画'}, {"ID": 15, "type": '历史'}]
    region_list = [{"ID": 1, "region": '大陆'}, {"ID": 2, "region": '香港'}, {"ID": 3, "region": '台湾'},
                   {"ID": 4, "region": '美国'}, {"ID": 5, "region": '法国'}, {"ID": 6, "region": '英国'},
                   {"ID": 7, "region": '日本'}, {"ID": 8, "region": '韩国'}, {"ID": 9, "region": '德国'},
                   {"ID": 10, "region": '泰国'}, {"ID": 11, "region": '印度'}, {"ID": 12, "region": '意大利'},
                   {"ID": 13, "region": '西班牙'}, {"ID": 14, "region": '加拿大'}]
    time_list = [{"ID": 1, "time": '2024'}, {"ID": 2, "time": '2023'}, {"ID": 3, "time": "2022"},
                 {"ID": 4, "time": '2021'}, {"ID": 5, "time": '2020'}, {"ID": 6, "time": '2019'},
                 {"ID": 7, "time": "2018"}, {"ID": 8, "time": '2017'}, {"ID": 9, "time": '2016'},
                 {"ID": 10, "time": '2015'}, {"ID": 11, "time": '2014'}, {"ID": 12, "time": "其他"}]

    type_name = _get_list_item(type_list, type_ID, 'type')
    region_name = _get_list_item(region_list, region_ID, 'region')
    time_name = _get_list_item(time_list, time_ID, 'time')

    type_val = '' if type_ID == '0' else type_list[int(type_ID) - 1].get("type", '')
    region_val = '' if region_ID == '0' else region_list[int(region_ID) - 1].get("region", '')
    time_val = '' if time_ID == '0' else time_list[int(time_ID) - 1].get("time", '')

    queryset = Movie.objects.filter(
        Q(types__contains=type_val) & Q(regions__contains=region_val) & Q(date__contains=time_val)
    )

    return render(request, 'front_depot.html', {
        'type_list': type_list,
        'region_list': region_list,
        'time_list': time_list,
        'queryset': queryset,
        'kwargs': kwargs,
        'type_name': type_name,
        'region_name': region_name,
        'time_name': time_name
    })


def _get_list_item(items, id_str, key):
    """从列表项中按 ID 取 display 名称，ID='0' 返回'全部'"""
    if id_str == '0':
        return '全部'
    try:
        idx = int(id_str) - 1
        return items[idx].get(key, '全部')
    except (IndexError, ValueError):
        return '全部'


# ============================================================
# 电影详情
# ============================================================
def details(request, uid):
    movie_information = Movie.objects.filter(id=uid)
    if not movie_information.exists():
        messages.error(request, "影片不存在！")
        return redirect('/front_index/')

    movie_obj = movie_information.first()
    movie_name = movie_obj.title
    movie_ID = movie_obj.id

    queryset = Comment.objects.filter(movie=movie_name).order_by('-comment_time')
    request.session["info"] = {'movie_ID': movie_ID, 'ID': uid}

    collect = Collect.objects.none()
    if request.user.is_authenticated:
        collect = Collect.objects.filter(
            Q(collect_user=request.user.username) & Q(collect_movie=movie_name))

    page_object = Pagination(request, queryset)
    return render(request, 'front_details.html', {
        "movie_name": movie_name,
        "collect": collect,
        "movie_information": movie_information,
        "queryset": page_object.page_queryset,
        "page_string": page_object.html()
    })


# ============================================================
# 收藏 / 取消收藏
# ============================================================
def collect(request):
    if not request.user.is_authenticated:
        return HttpResponse('请先登录')

    collect_user = request.user.username
    collect_movie = request.GET.get('movie_name')
    if not collect_movie:
        return HttpResponse('参数错误')

    queryset_collect = Collect.objects.filter(collect_user=collect_user)
    try:
        list_movie = Movie.objects.get(title=collect_movie)
    except Movie.DoesNotExist:
        return HttpResponse('影片不存在')

    if queryset_collect.filter(collect_movie=collect_movie).exists():
        queryset_collect.filter(collect_movie=collect_movie).delete()
        # 触发推荐刷新
        from .recommend import generate_recommendations
        generate_recommendations(request.user.id)
        return HttpResponse('🤍 收藏')
    else:
        Collect.objects.create(
            collect_movie=collect_movie,
            collect_user=collect_user,
            movie_information=list_movie
        )
        from .recommend import generate_recommendations
        generate_recommendations(request.user.id)
        return HttpResponse('❤️ 取消收藏')


# ============================================================
# 添加评论
# ============================================================
def comment_add(request):
    if not request.user.is_authenticated:
        messages.error(request, "请先登录后再发表评论！")
        return redirect('/login/')

    try:
        comment_score = request.GET.get('score', '')
        comment_discussion = request.GET.get('discuss', '')

        if not comment_score or not comment_discussion:
            messages.error(request, "评分和评论内容不能为空！")
            return redirect(request.META.get('HTTP_REFERER', '/front_index/'))

        if "info" not in request.session:
            messages.error(request, "参数错误，请重新进入影片详情页！")
            return redirect('/front_index/')

        uid = request.session["info"]["ID"]
        movie_ID = request.session["info"]["movie_ID"]
        comment_ID = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))

        user_obj = UserInfo.objects.filter(username=request.user.username).first()
        if not user_obj:
            messages.error(request, "用户信息异常！")
            return redirect('/login/')

        movie_obj = Movie.objects.get(id=movie_ID)
        movie_name = movie_obj.title

        Comment.objects.create(
            comment_score=comment_score,
            discussion=comment_discussion,
            comment_user=request.user.username,
            movie=movie_name,
            comment_ID=comment_ID
        )

        return redirect(f'/movie/{uid}/details/')
    except Exception as e:
        messages.error(request, f"发表评论失败：{str(e)}")
        return redirect(request.META.get('HTTP_REFERER', '/front_index/'))


# ============================================================
# 搜索
# ============================================================
def result(request):
    search_keyword = request.GET.get('search', '')
    if search_keyword:
        keyword = search_keyword.strip()
        queryset = Movie.objects.filter(
            Q(title__icontains=keyword) | Q(actors__icontains=keyword)
        ).distinct()
    else:
        queryset = Movie.objects.none()

    return render(request, 'front_result.html', {
        'search_keyword': search_keyword,
        'queryset': queryset,
        'count': queryset.count()
    })


# ============================================================
# 电影评分（AJAX）
# ============================================================
def rate_movie(request):
    if not request.user.is_authenticated:
        return JsonResponse({"status": False, "error": "请先登录"})

    if request.method == 'GET':
        movie_id = request.GET.get('movie_id')
        if not movie_id:
            return JsonResponse({"status": False, "error": "参数错误"})
        try:
            rating = Rating.objects.get(user=request.user, movie_id=movie_id)
            return JsonResponse({"status": True, "score": rating.score})
        except Rating.DoesNotExist:
            return JsonResponse({"status": True, "score": 0})

    elif request.method == 'POST':
        movie_id = request.POST.get('movie_id')
        score = request.POST.get('score')

        if not movie_id or not score:
            return JsonResponse({"status": False, "error": "参数错误"})

        try:
            score = float(score)
            if score < 0 or score > 10:
                return JsonResponse({"status": False, "error": "评分必须在0-10之间"})

            Rating.objects.update_or_create(
                user=request.user,
                movie_id=movie_id,
                defaults={'score': score}
            )

            from .recommend import generate_recommendations
            generate_recommendations(request.user.id)

            return JsonResponse({"status": True, "score": score})
        except Exception as e:
            return JsonResponse({"status": False, "error": str(e)})

    return JsonResponse({"status": False, "error": "请求方法错误"})
