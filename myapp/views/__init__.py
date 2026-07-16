"""
myapp.views 包

按功能域拆分：
- auth:      登录、注册、登出
- movie:     首页、排行榜、电影库、详情、搜索、收藏、评论、评分
- recommend: 协同过滤推荐引擎
- center:    个人中心、留言板
- admin:     后台管理（电影/用户/管理员/评论）
"""

from .auth import (
    LoginForm, RegisterForm,
    login_user, register_user, logout_user,
)

from .movie import (
    index, front_index, rank, depot, details,
    collect, comment_add, result, rate_movie,
)

from .recommend import (
    get_user_type_vector, calculate_similarity,
    get_cold_start_recommendations, generate_recommendations,
    recommend,
)

from .center import center, board_add

from .admin import (
    MovieModelForm, UserModelForm,
    admin_index,
    admin_movie, admin_movie_add, admin_movie_delete,
    admin_movie_detail, admin_movie_edit,
    admin_users, admin_users_delete, admin_users_reset,
    admin_admins, admin_admin_add, admin_admin_delete, admin_admin_reset,
    admin_comments, admin_comment_delete,
)
