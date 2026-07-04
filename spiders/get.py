import requests
import json
import random
import time
import bs4


def getip():
    """
    获取代理IP（优化版：无可用IP时返回None，而非直接抛异常）
    """
    iplist = []
    try:
        with open("ipdaili.txt", "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                # 适配 IP|端口|协议 或 IP:端口 格式
                if '|' in line:
                    parts = line.split('|')
                    if len(parts) >= 2:
                        ip = parts[0].strip()
                        port = parts[1].strip()
                        iplist.append(f"{ip}:{port}")
                    else:
                        print(f"跳过格式错误的IP：{line}")
                elif ':' in line:
                    iplist.append(line)
                else:
                    print(f"跳过格式错误的IP：{line}")

        if not iplist:
            print("警告：valid.txt中无可用代理IP，将尝试直接访问（无代理）")
            return None  # 无IP时返回None，而非抛异常

        # 随机选一个IP
        proxy = random.choice(iplist)
        proxies = {
            'http': f'http://{proxy}',
            'https': f'https://{proxy}'
        }
        return proxies

    except FileNotFoundError:
        print("警告：未找到valid.txt文件，将尝试直接访问（无代理）")
        return None


# 请求头列表
headers = [
    {
        'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"},
    {
        'User-Agent': "Mozilla/5.0 (X11; U; Linux x86_64; zh-CN; rv:1.9.2.10) Gecko/20100922 Ubuntu/10.10 (maverick) Firefox/3.6.10"},
    {
        'User-Agent': "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36 OPR/26.0.1656.60"},
    {
        'User-Agent': "Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; WOW64; Trident/5.0; SLCC2; .NET CLR 2.0.50727; .NET CLR 3.5.30729; .NET CLR 3.0.30729; Media Center PC 6.0; .NET4.0C; .NET4.0E; QQBrowser/7.0.3698.400)"},
    {
        'User-Agent': "Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; Trident/4.0; SV1; QQDownload 732; .NET4.0C; .NET4.0E; SE 2.X MetaSr 1.0)"},
    {'User-Agent': "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko"},
    {
        'User-Agent': "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Maxthon/4.4.3.4000 Chrome/30.0.1599.101 Safari/537.36"}
]

# 先清空旧的ur.txt
with open("ur.txt", 'w', encoding='utf-8') as f:
    f.write("")

# 爬取+写入逻辑（核心优化：拆分异常捕获，给变量加初始值）
for i in range(10, 100, 1):
    time.sleep(random.uniform(2, 5))
    # 给r赋初始值，避免未定义
    r = None
    try:
        # 1. 获取代理IP（无IP时返回None）
        proxies = getip()

        # 2. 构造URL
        url = f'https://movie.douban.com/j/chart/top_list?type=11&interval_id=50:40&action=&start={i * 20}&limit=20'

        # 3. 发送请求（无代理时不传proxies参数）
        request_kwargs = {
            'headers': random.choice(headers),
            'timeout': 10
        }
        if proxies:  # 有代理才传proxies
            request_kwargs['proxies'] = proxies

        r = requests.get(url, **request_kwargs)
        r.raise_for_status()  # 触发HTTP错误（如403/500）
        result = r.json()

        # 4. 写入ur.txt
        with open("ur.txt", 'a', encoding='utf-8') as f:
            for movie in result:
                json.dump(movie, f, ensure_ascii=False)
                f.write('\n')

        print(f"✅ 第{i}页成功：写入{len(result)}条电影数据")

    except requests.exceptions.RequestException as e:
        # 捕获请求相关错误（超时、连接失败、HTTP错误等）
        print(f"❌ 第{i}页请求失败：{str(e)}")
    except json.JSONDecodeError as e:
        # 捕获JSON解析错误
        print(f"❌ 第{i}页JSON解析失败：{str(e)}")
    except Exception as e:
        # 捕获其他未知错误
        print(f"❌ 第{i}页未知错误：{str(e)}")
    finally:
        # 无论成功失败，都释放响应对象（避免内存泄漏）
        if r:
            r.close()
    continue