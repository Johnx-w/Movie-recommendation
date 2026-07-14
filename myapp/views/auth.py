"""
认证模块：登录、注册、登出

包含：
- LoginForm / RegisterForm（Django Forms）
- 登录失败计数 + 锁定机制（基于 Django Cache）
- login_user / register_user / logout_user
"""
import random
import math
import time
from datetime import datetime

from django.shortcuts import render, redirect
from django import forms
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.core.exceptions import ValidationError
from django.core.cache import cache

from ..models import UserInfo


# ============================================================
# 登录表单
# ============================================================
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
                # 使用 Django authenticate 验证哈希密码
                user = authenticate(request, username=username, password=password)

                if user is not None:
                    login(request, user)
                    request.session.set_expiry(None)
                    _clear_login_failed(username)
                    return redirect('/front_index/')
                else:
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


# ============================================================
# 注册表单
# ============================================================
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
            nickname = form.cleaned_data.get("nickname", username)

            if UserInfo.objects.filter(username=username).exists():
                messages.error(request, '你输入的用户名已存在!')
                return HttpResponseRedirect('/register/')
            if UserInfo.objects.filter(email=email).exists():
                messages.error(request, '你输入的邮箱已经被注册过!')
                return HttpResponseRedirect('/register/')

            user_ID = datetime.now().strftime("%Y%m%d%H%M%S") + str(random.randint(1000, 9999))
            UserInfo.objects.create_user(
                username=username,
                password=password,
                email=email,
                user_ID=user_ID,
                nickname=nickname,
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
