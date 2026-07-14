"""
个人中心模块：用户信息、评论列表、收藏列表、留言板
"""
import random
from datetime import datetime

from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponseRedirect

from ..models import Movie, UserInfo, Comment, Collect, Board
from ..pagination import Pagination


def center(request):
    if not request.user.is_authenticated:
        messages.error(request, "请先登录")
        return redirect('/login/')

    queryset_user = UserInfo.objects.filter(username=request.user.username)
    queryset_comment = Comment.objects.filter(comment_user=request.user.username)
    queryset_collect = Collect.objects.filter(collect_user=request.user.username)

    # 为每个评论附加电影信息
    comment_list = list(queryset_comment)
    for comment in comment_list:
        try:
            comment.movie_info = Movie.objects.filter(title=comment.movie).first()
        except Exception:
            comment.movie_info = None

    page_object = Pagination(request, comment_list)

    return render(request, 'front_center.html', {
        "queryset_user": queryset_user,
        "queryset_collect": queryset_collect,
        "queryset": page_object.page_queryset,
        "page_string": page_object.html()
    })


def board_add(request):
    board_mes = request.GET.get('boardMessage', '')
    if not board_mes:
        messages.warning(request, '留言失败,请输入内容')
        return HttpResponseRedirect('/center/')

    board_ID = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))
    Board.objects.create(
        board_message=board_mes,
        board_user=request.user.username,
        board_ID=board_ID
    )
    messages.success(request, '留言成功')
    return HttpResponseRedirect('/center/')
