# 关闭urllib3的HTTPS证书警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 核心模块导入
import requests
import os
import json
import time
import random
from urllib.parse import urlparse
from PIL import Image
import pickle
import io
from collections import OrderedDict  # 用于固定请求头顺序，更像真人

# ========== 核心配置 ==========
MOVIE_DATA_FILE = "ur.txt"
POSTER_SAVE_DIR = r"D:\Code\movie\static\assets\movie_posters"
BREAKPOINT_FILE = "download_breakpoint.pkl"
PROXY_FILE = "ipdaili.txt"
# 【必须重新复制】登录豆瓣后，从浏览器复制最新的Cookie！！！
DOUBAN_COOKIE = 'll="118297"; bid=kiQX8C5nW-Q; dbcl2="293177189:BVRysLF5f8c"; push_noty_num=0; push_doumail_num=0; ck=XbE8; frodotk_db="1df59dd39a95955d59e0d97acfc0c017"; ap_v=0,6.0'

# 真人UA池（增加移动端UA，混合使用）
UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
]

# 本地IP 爬取配置（调整为更快速度）
SINGLE_DELAY = (15, 30)  # 每爬1张，休息15-30秒（加快速度）
BATCH_SIZE = 10          # 每爬10张
BATCH_REST = 60          # 休息1分钟（调整为1分钟）
LARGE_BATCH_SIZE = 50    # 每爬50张
LARGE_BATCH_REST = 600   # 休息10分钟（调整为10分钟）
RETRY_TIMES = 1          # 只重试1次，避免触发高频检测
FINAL_RETRY_TIMES = 1
MIN_FILE_SIZE = 5120     # 最小图片大小提升到5KB（过滤豆瓣假图片）
PROXY_VALID_TIMEOUT = 5  # 减少代理验证超时时间

# ========== 工具函数 ==========
def read_proxy_list():
    proxy_list = []
    if not os.path.exists(PROXY_FILE):
        print(f"⚠️ 代理文件不存在，使用本地IP")
        return proxy_list
    with open(PROXY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and ":" in line:
                proxy_list.append(line)
    if not proxy_list:
        print(f"⚠️ 代理列表为空，使用本地IP")
    return proxy_list

def get_random_proxy(proxy_list):
    if not proxy_list:
        return None
    random.shuffle(proxy_list)
    for proxy in proxy_list:
        try:
            proxies = {"http":f"http://{proxy}", "https":f"http://{proxy}"}
            test_res = requests.get(
                "https://movie.douban.com",
                proxies=proxies,
                headers={"User-Agent":random.choice(UA_POOL)},
                timeout=PROXY_VALID_TIMEOUT,
                verify=False
            )
            if test_res.status_code == 200:
                print(f"✅ 有效代理：{proxy}")
                return proxies
        except Exception as e:
            print(f"⚠️ 代理{proxy}无效：{str(e)[:80]}")
    print(f"⚠️ 无有效代理，使用本地IP")
    return None

def init_dirs():
    if not os.path.exists(POSTER_SAVE_DIR):
        os.makedirs(POSTER_SAVE_DIR)

def load_breakpoint():
    if os.path.exists(BREAKPOINT_FILE):
        with open(BREAKPOINT_FILE, "rb") as f:
            data = pickle.load(f)
            print(f"断点：成功{len(data['success_ids'])}，失败{len(data['fail_queue'])}")
            return data
    print(f"无断点，从头开始")
    return {"success_ids":set(), "fail_queue":[]}

def save_breakpoint(data):
    with open(BREAKPOINT_FILE, "wb") as f:
        pickle.dump(data, f)

def get_valid_suffix(cover_url):
    try:
        path = urlparse(cover_url).path
        for suf in ["jpg","png","webp","jpeg"]:
            if path.lower().endswith(f".{suf}"):
                return suf
        return "jpg"
    except:
        return "jpg"

def check_image_in_memory(img_data):
    """核心修复：在内存中校验图片数据，不写入无效文件"""
    print(f"图片数据大小：{len(img_data)}字节")
    if len(img_data) < MIN_FILE_SIZE:
        print(f"内存校验失败：数据大小{len(img_data)}字节 < {MIN_FILE_SIZE}字节")
        return False
    
    try:
        # 步骤1：打开图片
        img = Image.open(io.BytesIO(img_data))
        print(f"步骤1：成功打开图片，格式：{img.format}")
        
        # 步骤2：校验文件头
        img.verify()
        print(f"步骤2：文件头校验成功")
        
        # 步骤3：重新打开并加载完整数据
        img = Image.open(io.BytesIO(img_data))
        img.load()
        print(f"步骤3：完整数据加载成功，尺寸：{img.size}")
        
        print(f"内存校验成功：图片尺寸{img.size}")
        return True
    except Exception as e:
        print(f"内存校验失败：{type(e).__name__}: {str(e)[:100]}")
        # 调试：查看前100字节的内容，判断是否是真实图片数据
        print(f"数据前100字节：{img_data[:100]}")
        return False

# ========== 核心下载函数（终极修复） ==========
def download_single_poster(movie_id, cover_url, proxy_list):
    suffix = get_valid_suffix(cover_url)
    save_path = os.path.join(POSTER_SAVE_DIR, f"{movie_id}.{suffix}")

    # 检查已存在的图片
    if os.path.exists(save_path):
        with open(save_path, "rb") as f:
            if check_image_in_memory(f.read()):
                print(f"已存在有效图片，跳过")
                return True, save_path
            else:
                os.remove(save_path)
                print(f"已存在图片损坏，删除并重下")

    # 本地IP 预热（加快速度）
    time.sleep(random.uniform(*SINGLE_DELAY))

    for retry in range(RETRY_TIMES):
        # 简化代理选择逻辑，因为已在主逻辑中验证过代理有效性
        proxies = None
        is_local = True
        if proxy_list:
            proxies = {"http":f"http://{random.choice(proxy_list)}", "https":f"http://{random.choice(proxy_list)}"}
            is_local = False
        print(f"第{retry+1}次重试：{'本地IP' if is_local else '代理IP'}")

        try:
            # 关键：用OrderedDict固定请求头顺序，模拟浏览器发送顺序
            headers = OrderedDict([
                ("User-Agent", random.choice(UA_POOL)),
                ("Referer", f"https://movie.douban.com/subject/{movie_id}/"),
                ("Accept", "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"),
                ("Accept-Encoding", "gzip, deflate, br, zstd"),
                ("Accept-Language", "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6"),
                ("Cache-Control", "no-cache"),
                ("Pragma", "no-cache"),
                ("DNT", "1"),
                ("Cookie", DOUBAN_COOKIE),
                ("Sec-Ch-Ua", '"Not/A)Brand";v="8", "Chromium";v="126", "Microsoft Edge";v="126"'),
                ("Sec-Ch-Ua-Mobile", "?0" if random.random()>0.3 else "?1"),  # 随机移动端标识
                ("Sec-Ch-Ua-Platform", '"Windows"'),
                ("Sec-Fetch-Dest", "image"),
                ("Sec-Fetch-Mode", "no-cors"),
                ("Sec-Fetch-Site", "same-site"),
                ("Upgrade-Insecure-Requests", "1"),
                ("Connection", "close")  # 关闭长连接，避免IP追踪
            ])

            # 发送请求，直接获取全部数据（不使用stream，避免截断）
            session = requests.Session()
            session.keep_alive = False
            session.verify = False
            if proxies:
                session.proxies = proxies

            response = session.get(
                cover_url,
                headers=headers,
                timeout=120,  # 延长超时到120秒
                allow_redirects=True,
                params={"_t": random.random() * 1000000}  # 随机参数防缓存
            )

            # 状态码和类型校验
            if response.status_code != 200:
                print(f"状态码{response.status_code}，跳过")
                time.sleep(random.uniform(15, 30) if is_local else 10)  # 减少等待时间
                continue
            if not response.headers.get("Content-Type", "").startswith("image/"):
                print(f"非图片类型：{response.headers.get('Content-Type')}")
                time.sleep(random.uniform(15, 30) if is_local else 10)  # 减少等待时间
                continue

            # 核心步骤：内存中校验图片数据，无效则直接跳过
            img_data = response.content
            if not check_image_in_memory(img_data):
                time.sleep(random.uniform(15, 30) if is_local else 10)  # 减少等待时间
                continue

            # 内存校验通过，再写入文件 - 添加异常处理
            try:
                with open(save_path, "wb") as f:
                    f.write(img_data)
                print(f"下载成功：{os.path.basename(save_path)}")
                return True, save_path
            except Exception as e:
                print(f"保存图片失败：{str(e)[:80]}")
                # 尝试重命名保存
                try:
                    backup_path = f"{save_path}.bak"
                    with open(backup_path, "wb") as f:
                        f.write(img_data)
                    print(f"备份保存成功：{os.path.basename(backup_path)}")
                    return True, backup_path
                except Exception as e2:
                    print(f"备份保存也失败：{str(e2)[:50]}")
                    time.sleep(random.uniform(5, 10))
                    continue

        except Exception as e:
            print(f"下载异常：{str(e)[:80]}")
            time.sleep(random.uniform(15, 30) if is_local else 10)  # 减少等待时间

    print(f"最终下载失败：{movie_id}.{suffix}")
    return False, (movie_id, cover_url)

def final_retry_fail_queue(fail_queue, proxy_list):
    print(f"\n重试失败队列（共{len(fail_queue)}个）")
    success = 0
    new_fail = []
    for mid, url in fail_queue:
        time.sleep(random.uniform(120, 180))  # 重试间隔2-3分钟
        res, _ = download_single_poster(mid, url, proxy_list)
        if res:
            success +=1
        else:
            new_fail.append((mid, url))
    print(f"重试结果：成功{success}，失败{len(new_fail)}")
    return new_fail

# ========== 主逻辑 ==========
if __name__ == "__main__":
    init_dirs()
    breakpoint_data = load_breakpoint()
    success_ids, fail_queue = breakpoint_data["success_ids"], breakpoint_data["fail_queue"]
    proxy_list = read_proxy_list()
    
    # 检查是否有有效代理，若无则后续所有爬取都使用本地IP
    has_valid_proxy = False
    if proxy_list:
        print("检查代理有效性...")
        valid_proxies = []
        for proxy in proxy_list:
            try:
                proxies = {"http":f"http://{proxy}", "https":f"http://{proxy}"}
                test_res = requests.get(
                    "https://movie.douban.com",
                    proxies=proxies,
                    headers={"User-Agent":random.choice(UA_POOL)},
                    timeout=PROXY_VALID_TIMEOUT,
                    verify=False
                )
                if test_res.status_code == 200:
                    valid_proxies.append(proxy)
                    has_valid_proxy = True
                    print(f"有效代理：{proxy}")
            except Exception as e:
                print(f"代理{proxy}无效：{str(e)[:50]}")
        
        if not has_valid_proxy:
            print(f"无有效代理，后续所有爬取都将使用本地IP")
            proxy_list = []
        else:
            proxy_list = valid_proxies
            print(f"有效代理数量：{len(proxy_list)}")
    else:
        print("无代理列表，使用本地IP")

    if not os.path.exists(MOVIE_DATA_FILE):
        print(f"找不到{MOVIE_DATA_FILE}")
        exit(1)

    with open(MOVIE_DATA_FILE, "r", encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip()]
    total = len(lines)
    print(f"\n读取{total}条数据，开始爬取\n")

    # 新增：遍历现有图片文件，检查是否损坏，损坏的加入待爬取列表
    existing_files = {}
    if os.path.exists(POSTER_SAVE_DIR):
        print("检查现有图片是否损坏...")
        for file_name in os.listdir(POSTER_SAVE_DIR):
            if file_name.endswith((".jpg", ".png", ".webp", ".jpeg")):
                movie_id = os.path.splitext(file_name)[0]
                file_path = os.path.join(POSTER_SAVE_DIR, file_name)
                try:
                    with open(file_path, "rb") as f:
                        img_data = f.read()
                    if not check_image_in_memory(img_data):
                        print(f"发现损坏图片：{file_name}")
                        existing_files[movie_id] = "corrupted"
                    else:
                        existing_files[movie_id] = "valid"
                except Exception as e:
                    print(f"检查图片{file_name}失败：{str(e)[:50]}")
                    existing_files[movie_id] = "corrupted"
        print(f"检查完成：有效图片{list(existing_files.values()).count('valid')}，损坏图片{list(existing_files.values()).count('corrupted')}")

    current_count = 0
    for line_num, line in enumerate(lines, 1):
        try:
            movie = json.loads(line)
            mid, url = movie.get("id"), movie.get("cover_url")
            if not mid or not url:
                print(f"第{line_num}行：无ID/URL")
                continue
            
            # 修改：即使在success_ids中，如果图片损坏也要重新爬取
            if mid in success_ids:
                if mid in existing_files and existing_files[mid] == "corrupted":
                    print(f"第{line_num}行：已成功但图片损坏，重新爬取")
                else:
                    print(f"第{line_num}行：已成功且图片有效，跳过")
                    continue

            res, _ = download_single_poster(mid, url, proxy_list)
            if res:
                success_ids.add(mid)
                current_count +=1
                print(f"进度：{line_num}/{total}，累计成功{len(success_ids)}")
            else:
                fail_queue.append((mid, url))
                print(f"进度：{line_num}/{total}，加入失败队列")

            # 保存断点 - 添加异常处理
            if line_num % 5 == 0:
                try:
                    breakpoint_data["success_ids"] = success_ids
                    breakpoint_data["fail_queue"] = fail_queue
                    save_breakpoint(breakpoint_data)
                    print(f"保存断点")
                except Exception as e:
                    print(f"保存断点失败：{str(e)[:50]}")

            # 爬取节奏控制 - 只在使用本地IP时生效
            if not proxy_list:  # 无代理列表则使用本地IP
                if current_count % BATCH_SIZE ==0 and current_count>0:
                    print(f"\n爬取{current_count}张，休息{BATCH_REST//60}分钟...")
                    time.sleep(BATCH_REST)
                if current_count % LARGE_BATCH_SIZE ==0 and current_count>0:
                    print(f"\n爬取{current_count}张，休息{LARGE_BATCH_REST//60}分钟...")
                    time.sleep(LARGE_BATCH_REST)

        except json.JSONDecodeError:
            print(f"第{line_num}行：JSON格式错误")
        except Exception as e:
            print(f"第{line_num}行：异常{str(e)[:80]}")

    # 保存最终断点+重试失败队列
    save_breakpoint({"success_ids":success_ids, "fail_queue":fail_queue})
    final_fail = final_retry_fail_queue(fail_queue, proxy_list)

    # 最终统计
    print("\n" + "="*60)
    print(f"最终统计：")
    print(f"   总数据：{total}")
    print(f"   成功：{len(success_ids)} ({len(success_ids)/total*100:.1f}%)")
    print(f"   失败：{len(final_fail)}")
    if final_fail:
        print(f"失败ID：{[x[0] for x in final_fail]}")
    print(f"图片路径：{POSTER_SAVE_DIR}")
    print("="*60)