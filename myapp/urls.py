from django.urls import path, re_path
from . import views

urlpatterns = [
    path('login/', views.login_user),
    path('register/', views.register_user),
    path('logout/', views.logout_user),

    path('', views.index),
    path('front_index/', views.front_index),

    path('rank/', views.rank),
    # path('test_rank/', views.test_rank),
    path('depot/', views.depot),
    re_path('depot-(?P<depot_type_ID>(\d+))-(?P<depot_region_ID>(\d+))-(?P<depot_time_ID>(\d+))', views.depot),

    path('movie/<int:uid>/details/', views.details),
    path('details/<int:uid>/', views.details),  # 添加支持 /details/<uid>/ 格式的访问
    path('result/', views.result),  # 添加搜索结果路径

    path('collect/', views.collect),
    path('comment/add/', views.comment_add),

    path('recommend/', views.recommend),

    path('center/', views.center),
    path('board/add/', views.board_add),

    # 后台管理URL
    path('admin_index/', views.admin_index),
    path('admin_movie/', views.admin_movie),
    path('admin_movie_add/', views.admin_movie_add),
    path('admin_movie_delete/', views.admin_movie_delete),
    path('admin_movie_detail/', views.admin_movie_detail),
    path('admin_movie_edit/', views.admin_movie_edit),
    path('admin_users/', views.admin_users),
    path('admin_users_delete/', views.admin_users_delete),
    path('admin_users_reset/', views.admin_users_reset),
    
    # 管理员管理URL（仅超级管理员可访问）
    path('admin_admins/', views.admin_admins),
    path('admin_admin_add/', views.admin_admin_add),
    path('admin_admin_delete/', views.admin_admin_delete),
    path('admin_admin_reset/', views.admin_admin_reset),
    
    # 评论管理URL（仅管理员可访问）
    path('admin_comments/', views.admin_comments),
    path('admin_comment_delete/', views.admin_comment_delete),
    
    path('rate/movie/', views.rate_movie, name='rate_movie'),
]
