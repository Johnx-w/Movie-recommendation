from django.utils.safestring import mark_safe

class Pagination(object):

    def __init__(self, request, queryset, page_size=10, page_param="page", plus=5):

        from django.http.request import QueryDict
        import copy
        query_dict = copy.deepcopy(request.GET)
        query_dict._mutable = True
        self.query_dict = query_dict

        self.page_param = page_param
        page = request.GET.get(page_param, "1")

        if page.isdecimal():
            page = int(page)
        else:
            page: 1

        self.page = page
        self.page_size = page_size

        self.start = (page - 1) * page_size
        self.end = page * page_size

        self.page_queryset = queryset[self.start:self.end]

        # 处理 QuerySet 和普通列表
        try:
            # 尝试直接调用 count() 方法（QuerySet 支持）
            total_count = queryset.count()
        except TypeError:
            # 如果出错（普通列表需要参数），使用 len() 函数
            total_count = len(queryset)
        total_page_count, div = divmod(total_count, page_size)
        if div:
            total_page_count += 1
        self.total_page_count = total_page_count
        self.plus = plus

    def html(self):
        if self.total_page_count <= 2 * self.plus + 1:
            start_page = 1
            end_page = self.total_page_count
        else:
            if self.page <= self.plus:
                start_page = 1
                end_page = 2 * self.plus + 1
            else:
                if (self.page + self.plus) > self.total_page_count:
                    start_page = self.total_page_count - 2 * self.plus
                    end_page = self.total_page_count
                else:
                    start_page = self.page - self.plus
                    end_page = self.page + self.plus

        page_str_list = []

        self.query_dict.setlist(self.page_param, [1])
        page_str_list.append(
            '<li class="page-item"><a class="page-link" href="?{}">首页</a></li>'.format(self.query_dict.urlencode()))

        # 上一页
        if self.page > 1:
            self.query_dict.setlist(self.page_param, [self.page - 1])
            prev = '<li class="page-item"><a class="page-link" href="?{}">上一页</a></li>'.format(
                self.query_dict.urlencode())
        else:
            self.query_dict.setlist(self.page_param, [1])
            prev = '<li class="page-item"><a class="page-link" href="?{}">上一页</a></li>'.format(
                self.query_dict.urlencode())
        page_str_list.append(prev)
        # 页面
        for i in range(start_page, end_page + 1):
            self.query_dict.setlist(self.page_param, [i])
            if i == self.page:
                ele = '<li class="page-item active"><a class="page-link" href="?{}">{}</a></li>'.format(
                    self.query_dict.urlencode(), i)
            else:
                ele = '<li class="page-item"><a class="page-link" href="?{}">{}</a></li>'.format(
                    self.query_dict.urlencode(), i)
            page_str_list.append(ele)
        # 下一页
        if self.page < self.total_page_count:
            self.query_dict.setlist(self.page_param, [self.page + 1])
            prev = '<li class="page-item"><a class="page-link" href="?{}">下一页</a></li>'.format(
                self.query_dict.urlencode())
        else:
            self.query_dict.setlist(self.page_param, [self.total_page_count])
            prev = '<li class="page-item"><a class="page-link" href="?{}">下一页</a></li>'.format(
                self.query_dict.urlencode())
        page_str_list.append(prev)

        # 尾页
        self.query_dict.setlist(self.page_param, [self.total_page_count])
        page_str_list.append(
            '<li class="page-item"><a class="page-link" href="?{}">尾页</a></li>'.format(self.query_dict.urlencode()))

        # 构建搜索跳转表单，包含所有当前URL参数
        search_form = '<li><form style="float:left;margin-left:-1px" method="get">'
        # 添加所有当前URL参数，除了page参数
        for key, values in self.query_dict.lists():
            if key != self.page_param:
                for value in values:
                    search_form += f'<input type="hidden" name="{key}" value="{value}">'
        # 添加页码输入框和提交按钮
        search_form += '<input name="page" style="position: relative;float:left;display: inline-block;width: 60px;border-radius: 0;" type="text" class="form-control" placeholder="页码"><button style="border-radius:0" class="btn btn-primary" type="submit">跳转</button></form></li>'
        page_str_list.append(search_form)

        page_string = mark_safe("".join(page_str_list))
        return page_string
