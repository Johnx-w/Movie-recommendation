"""
后台管理模块：电影管理、用户管理、管理员管理、评论管理

包含表单类：MovieModelForm、UserModelForm
"""
import random
import os
from datetime import datetime

from django.shortcuts import render, redirect
from django import forms
from django.contrib import messages
from django.http import JsonResponse

from ..models import Movie, UserInfo, Comment, Board
from ..pagination import Pagination


# ============================================================
# MovieModelForm
# ============================================================
class MovieModelForm(forms.ModelForm):
    TYPE_CHOICES = [
        ('动作', '动作'), ('喜剧', '喜剧'), ('爱情', '爱情'),
        ('科幻', '科幻'), ('恐怖', '恐怖'), ('剧情', '剧情'),
        ('战争', '战争'), ('犯罪', '犯罪'), ('惊悚', '惊悚'),
        ('冒险', '冒险'), ('悬疑', '悬疑'), ('武侠', '武侠'),
        ('奇幻', '奇幻'), ('动画', '动画'), ('历史', '历史')
    ]
    REGION_CHOICES = [
        ('大陆', '大陆'), ('香港', '香港'), ('台湾', '台湾'),
        ('美国', '美国'), ('法国', '法国'), ('英国', '英国'),
        ('日本', '日本'), ('韩国', '韩国'), ('德国', '德国'),
        ('泰国', '泰国'), ('印度', '印度'), ('意大利', '意大利'),
        ('西班牙', '西班牙'), ('加拿大', '加拿大')
    ]

    types = forms.ChoiceField(choices=TYPE_CHOICES, label='类型', required=False)
    regions = forms.ChoiceField(choices=REGION_CHOICES, label='地区', required=False)
    director = forms.CharField(label='导演', required=False, max_length=255)
    poster_file = forms.FileField(label='海报文件', required=False)

    class Meta:
        model = Movie
        fields = ['title', 'director', 'actors', 'types', 'regions', 'score', 'date', 'poster', 'summary']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'poster_file':
                field.widget.attrs = {"class": "form-control", "placeholder": field.label}
        self.fields['poster_file'].widget.attrs = {"class": "form-control-file"}
        self.fields['date'].widget.attrs = {"class": "form-control", "type": "date"}


# ============================================================
# UserModelForm
# ============================================================
class UserModelForm(forms.ModelForm):
    class Meta:
        model = UserInfo
        fields = ["password"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs = {"class": "form-control", "placeholder": field.label}


# ============================================================
# 后台首页
# ============================================================
def admin_index(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        messages.error(request, "权限不足，无法访问此页面")
        return redirect('/front_index/')

    current_time = datetime.now()
    context = {
        "movie_num": Movie.objects.count(),
        "board_num": Board.objects.count(),
        "user_num": UserInfo.objects.count(),
        "comment_num": Comment.objects.count(),
        "current_time": current_time,
        "latest_movies": Movie.objects.order_by('-id')[:10]
    }
    return render(request, 'admin_index.html', context)


# ============================================================
# 电影管理
# ============================================================
def admin_movie(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        messages.error(request, "权限不足，无法访问此页面")
        return redirect('/front_index/')

    data_dict = {}
    search_data = request.GET.get('search', "")
    if search_data:
        data_dict["title__contains"] = search_data
    queryset = Movie.objects.filter(**data_dict)
    page_object = Pagination(request, queryset)
    return render(request, 'admin_movie.html', {
        "form": MovieModelForm(),
        "search_data": search_data,
        "queryset": page_object.page_queryset,
        "page_string": page_object.html()
    })


def admin_movie_add(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"status": False, "error": "权限不足"})

    try:
        form = MovieModelForm(data=request.POST, files=request.FILES)
        if form.is_valid():
            director = request.POST.get('director', '')

            # 海报文件上传
            poster_path = request.POST.get('poster', 'assets/movie_posters/default.jpg')
            if 'poster_file' in request.FILES:
                poster_file = request.FILES['poster_file']
                upload_dir = os.path.join('static', 'assets', 'movie_posters')
                os.makedirs(upload_dir, exist_ok=True)
                file_ext = os.path.splitext(poster_file.name)[1]
                file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}{file_ext}"
                with open(os.path.join(upload_dir, file_name), 'wb+') as f:
                    for chunk in poster_file.chunks():
                        f.write(chunk)
                poster_path = f"assets/movie_posters/{file_name}"

            Movie.objects.create(
                title=request.POST.get('title', ''),
                director=director,
                actors=request.POST.get('actors', ''),
                types=request.POST.get('types', ''),
                regions=request.POST.get('regions', ''),
                score=request.POST.get('score') or None,
                date=request.POST.get('date') or None,
                poster=poster_path,
                summary=request.POST.get('summary', '')
            )
            return JsonResponse({"status": True})
        else:
            return JsonResponse({"status": False, 'error': form.errors})
    except Exception as e:
        return JsonResponse({"status": False, 'error': f"添加电影失败: {str(e)}"})


def admin_movie_delete(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"status": False, "error": "权限不足"})

    uid = request.GET.get('uid')
    if not Movie.objects.filter(id=uid).exists():
        return JsonResponse({"status": False, 'error': "删除失败,数据不存在。"})
    Movie.objects.filter(id=uid).delete()
    return JsonResponse({"status": True})


def admin_movie_detail(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"status": False, "error": "权限不足"})

    uid = request.GET.get("uid")
    try:
        movie_id = int(uid)
        movie = Movie.objects.filter(id=movie_id).first()
        if not movie:
            return JsonResponse({"status": False, 'error': "数据不存在。"})
    except (ValueError, TypeError):
        return JsonResponse({"status": False, 'error': "无效的电影ID。"})

    return JsonResponse({
        "status": True,
        "data": {
            "title": movie.title,
            "director": movie.director or '',
            "actors": movie.actors,
            "types": movie.types,
            "regions": movie.regions,
            "date": movie.date.strftime('%Y-%m-%d') if movie.date else '',
            "score": movie.score,
            "poster": movie.poster,
            "summary": movie.summary
        }
    })


def admin_movie_edit(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"status": False, "error": "权限不足"})

    uid = request.GET.get("uid")
    movie = Movie.objects.filter(id=uid).first()
    if not movie:
        return JsonResponse({"status": False, 'tips': "数据不存在,请刷新重试。"})

    form = MovieModelForm(data=request.POST, files=request.FILES, instance=movie)
    if form.is_valid():
        form.save()
        return JsonResponse({"status": True})
    return JsonResponse({"status": False, 'error': form.errors})

# ============================================================
# 用户管理（仅超级管理员）
# ============================================================
def admin_users(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        messages.error(request, "权限不足，只有超级管理员可以管理用户")
        return redirect('/front_index/')

    data_dict = {}
    search_data = request.GET.get('search', "")
    if search_data:
        data_dict["username__contains"] = search_data

    queryset = UserInfo.objects.filter(**data_dict)
    page_object = Pagination(request, queryset)
    return render(request, 'admin_users.html', {
        "form": UserModelForm(),
        "search_data": search_data,
        "queryset": page_object.page_queryset,
        "page_string": page_object.html()
    })


def admin_users_delete(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({"status": False, "error": "权限不足"})

    uid = request.GET.get('uid')
    try:
        deleted, _ = UserInfo.objects.filter(user_ID=uid).delete()
        if deleted == 0:
            return JsonResponse({"status": False, 'error': "删除失败,数据不存在."})
        return JsonResponse({"status": True})
    except Exception as e:
        return JsonResponse({"status": False, 'error': str(e)})


def admin_users_reset(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({"status": False, "error": "权限不足"})

    uid = request.GET.get('uid')
    try:
        user = UserInfo.objects.filter(user_ID=uid).first()
        if not user:
            return JsonResponse({"status": False, 'error': "重置失败,数据不存在."})
        user.set_password('123456')
        user.save()
        return JsonResponse({"status": True})
    except Exception as e:
        return JsonResponse({"status": False, 'error': str(e)})


# ============================================================
# 管理员管理
# ============================================================
def admin_admins(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        messages.error(request, "权限不足，无法访问此页面")
        return redirect('/front_index/')

    data_dict = {}
    search_data = request.GET.get('search', "")
    if search_data:
        data_dict["username__contains"] = search_data

    queryset = UserInfo.objects.filter(is_staff=True, **data_dict)
    page_object = Pagination(request, queryset)
    return render(request, 'admin_admins.html', {
        "form": UserModelForm(),
        "search_data": search_data,
        "queryset": page_object.page_queryset,
        "page_string": page_object.html()
    })


def admin_admin_add(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"status": False, "error": "权限不足"})

    username = request.POST.get("username")
    password = request.POST.get("password")
    email = request.POST.get("email")
    nickname = request.POST.get("nickname", username)
    is_superuser = request.POST.get("is_superuser", "false").lower() == "true"

    if not username or not password or not email:
        return JsonResponse({"status": False, "error": "用户名、密码和邮箱不能为空"})
    if is_superuser and not request.user.is_superuser:
        return JsonResponse({"status": False, "error": "权限不足，无法创建超级管理员"})

    try:
        if UserInfo.objects.filter(username=username).exists():
            return JsonResponse({"status": False, "error": "用户名已存在"})
        if UserInfo.objects.filter(email=email).exists():
            return JsonResponse({"status": False, "error": "邮箱已存在"})

        user_ID = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))
        UserInfo.objects.create_user(
            username=username, password=password, email=email,
            user_ID=user_ID, nickname=nickname,
        )
        user = UserInfo.objects.get(username=username)
        user.is_staff = True
        user.is_superuser = is_superuser
        user.save()
        return JsonResponse({"status": True})
    except Exception as e:
        return JsonResponse({"status": False, "error": str(e)})


def admin_admin_delete(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({"status": False, "error": "权限不足"})

    uid = request.GET.get('uid')
    try:
        user = UserInfo.objects.filter(user_ID=uid).first()
        if not user:
            return JsonResponse({"status": False, 'error': "删除失败,数据不存在."})
        if user.is_superuser and not request.user.is_superuser:
            return JsonResponse({"status": False, 'error': "权限不足，无法删除超级管理员"})
        if user.is_superuser and user.username == request.user.username:
            return JsonResponse({"status": False, 'error': "无法删除当前登录的超级管理员"})
        user.delete()
        return JsonResponse({"status": True})
    except Exception as e:
        return JsonResponse({"status": False, 'error': str(e)})


def admin_admin_reset(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"status": False, "error": "权限不足"})

    uid = request.GET.get('uid')
    try:
        user = UserInfo.objects.filter(user_ID=uid).first()
        if not user:
            return JsonResponse({"status": False, 'error': "重置失败,数据不存在."})
        if not request.user.is_superuser and user.username != request.user.username:
            return JsonResponse({"status": False, "error": "权限不足，普通管理员只能重置自己的密码"})
        if user.is_superuser and not request.user.is_superuser:
            return JsonResponse({"status": False, "error": "权限不足，无法重置超级管理员的密码"})

        user.set_password('123456')
        user.save()
        return JsonResponse({"status": True})
    except Exception as e:
        return JsonResponse({"status": False, 'error': str(e)})


# ============================================================
# 评论管理
# ============================================================
def admin_comments(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        messages.error(request, "权限不足，无法访问此页面")
        return redirect('/front_index/')

    queryset = Comment.objects.order_by('-comment_time')
    page_object = Pagination(request, queryset, page_size=10, page_param="page")
    return render(request, 'admin_comments.html', {
        "queryset": page_object.page_queryset,
        "page_string": page_object.html(),
    })


def admin_comment_delete(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        return JsonResponse({"status": False, "error": "权限不足"})

    comment_id = request.GET.get('comment_id')
    if not comment_id:
        return JsonResponse({"status": False, "error": "参数错误"})

    try:
        comment = Comment.objects.filter(comment_ID=comment_id).first()
        if not comment:
            return JsonResponse({"status": False, "error": "评论不存在"})
        comment.delete()
        return JsonResponse({"status": True})
    except Exception as e:
        return JsonResponse({"status": False, "error": str(e)})
