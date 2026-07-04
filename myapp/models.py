from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.contrib.auth.models import Group, Permission


# 电影模型（核心修正：poster字段、补充objects管理器）
class Movie(models.Model):
    # 显式声明objects管理器，消除编辑器"未解析"提示
    objects = models.Manager()

    title = models.CharField(max_length=255, verbose_name="电影标题")
    score = models.FloatField(null=True, blank=True, verbose_name="评分")
    date = models.DateField(null=True, blank=True, verbose_name="发布日期")
    # 核心修正：poster字段参数顺序（verbose_name在前，路径仅作为默认值/存储值）
    poster = models.CharField(
        verbose_name="海报路径",  # 第一个参数必须是verbose_name
        max_length=255,
        default="assets/movie_posters/default.jpg",  # 默认占位图路径
        blank=True  # 允许为空
    )
    actors = models.CharField(max_length=255, null=True, blank=True, verbose_name="演员表")
    regions = models.CharField(max_length=255, null=True, blank=True, verbose_name="地区")
    types = models.CharField(max_length=255, null=True, blank=True, verbose_name="类型")
    summary = models.TextField(null=True, blank=True, verbose_name="简介")

    class Meta:
        verbose_name = "电影"
        verbose_name_plural = "电影集"

    def __str__(self):
        return self.title


class UserManager(BaseUserManager):
    def _create_user(self, username, password, email, **kwargs):
        if not username:
            raise ValueError("请输入用户名!")
        if not password:
            raise ValueError("请输入密码!")
        if not email:
            raise ValueError("请输入邮箱地址!")
        # 补充：nickname若未传，默认用username
        if 'nickname' not in kwargs or not kwargs['nickname']:
            kwargs['nickname'] = username
        user = self.model(username=username, email=email, **kwargs)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, password, email, **kwargs):
        kwargs['is_superuser'] = False
        kwargs['is_staff'] = False
        return self._create_user(username, password, email, **kwargs)

    def create_superuser(self, username, password, email, **kwargs):
        kwargs['is_superuser'] = True
        kwargs['is_staff'] = True
        return self._create_user(username, password, email, **kwargs)


class UserInfo(AbstractBaseUser, PermissionsMixin):
    user_ID = models.CharField(max_length=32, null=False, verbose_name="用户ID")
    username = models.CharField(max_length=255, null=False, verbose_name="用户名", unique=True)
    # 核心修正：nickname添加默认值，避免创建用户时报错
    nickname = models.CharField(
        max_length=255,
        null=False,
        verbose_name="用户昵称",
        default=""  # 添加默认值
    )
    sex_choice = {
        (1, "男"),
        (2, "女")
    }
    sex = models.IntegerField(choices=sex_choice, null=False, verbose_name="性别", default=1)
    age = models.IntegerField(verbose_name="年龄", null=True)
    # 修正：邮箱设为unique=True，和视图中"检查邮箱重复"逻辑匹配
    email = models.EmailField(null=False, verbose_name="邮箱", unique=True)
    registration = models.DateTimeField(auto_now_add=True, verbose_name="创建时间", null=False)

    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        related_name='userinfo_groups',
        related_query_name='userinfo',
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        related_name='userinfo_permissions',
        related_query_name='userinfo',
    )

    is_staff = models.BooleanField(default=False, verbose_name="是否为管理员")
    is_active = models.BooleanField(default=True, verbose_name="是否激活")

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']
    EMAIL_FIELD = 'email'

    objects = UserManager()

    def __str__(self):
        return self.username


class Collect(models.Model):
    collect_user = models.CharField(max_length=255, null=False, verbose_name="收藏用户名")
    collect_movie = models.CharField(max_length=32, null=False, verbose_name="影片名")
    movie_information = models.ForeignKey(Movie, on_delete=models.CASCADE, null=True)


class Comment(models.Model):
    comment_ID = models.CharField(max_length=32, null=False, verbose_name="评论ID")
    comment_time = models.DateTimeField(auto_now_add=True, verbose_name="发布时间")
    comment_user = models.CharField(max_length=255, null=False, verbose_name="评论用户")
    movie = models.CharField(max_length=32, null=False, verbose_name="影片名")
    discussion = models.CharField(max_length=256, null=False, verbose_name="评论内容")
    comment_score = models.FloatField(null=False, verbose_name="评分")


class Rating(models.Model):
    user = models.ForeignKey(UserInfo, on_delete=models.CASCADE, related_name='user_ratings')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='movie_ratings')
    score = models.FloatField(verbose_name="评分", null=False)
    rating_time = models.DateTimeField(auto_now_add=True, verbose_name="评分时间")
    
    class Meta:
        unique_together = ('user', 'movie')  # 确保一个用户对一部电影只评分一次
        verbose_name = "用户评分"
        verbose_name_plural = "用户评分集"


class CfRec(models.Model):
    user = models.ForeignKey(UserInfo, on_delete=models.CASCADE, related_name='user_cfrecs')
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name='movie_cfrecs')
    rating = models.FloatField(null=False, verbose_name="推荐度")
    
    class Meta:
        unique_together = ('user', 'movie')  # 确保一个用户对一部电影只推荐一次
        verbose_name = "协同过滤推荐"
        verbose_name_plural = "协同过滤推荐集"


# 留言板模型
class Board(models.Model):
    board_ID = models.CharField(max_length=32, null=False, verbose_name="留言ID")
    board_user = models.CharField(max_length=255, null=False, verbose_name="留言用户")
    board_message = models.TextField(null=False, verbose_name="留言内容")
    board_time = models.DateTimeField(auto_now_add=True, verbose_name="留言时间")
    
    class Meta:
        verbose_name = "留言"
        verbose_name_plural = "留言板"
    
    def __str__(self):
        return f"{self.board_user}: {self.board_message[:20]}"
