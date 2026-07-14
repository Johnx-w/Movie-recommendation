"""
推荐引擎模块：基于用户的协同过滤 + 类型偏好加权 + 冷启动兜底

============================================================
推荐策略：三层回退
============================================================
1. 协同过滤实时生成（主力）
   - 计算当前用户与所有其他用户的相似度
   - 取 Top-K（K=5）相似用户的评分/收藏，加权生成候选集
   - 相似度公式：0.6 × 皮尔逊相关系数（基于电影评分） + 0.4 × 余弦相似度（基于类型偏好向量）
     - 皮尔逊：衡量两人对共同电影的评分趋势是否一致
     - 余弦：衡量两人喜欢的电影类型分布是否相似
   - 设计理由：即使两人没有共同电影，也能通过类型偏好找到"口味相近"的用户

2. CfRec 缓存兜底
   - 如果实时生成失败（无相似用户 / 无候选电影），从 CfRec 表读取上次保存的推荐结果

3. 冷启动热门推荐（最终兜底）
   - 新用户无评分/收藏 → 分析其有限数据的类型偏好
   - 取 Top-2 偏好类型的高分电影
   - 数量不足时用全站热门补足

============================================================
类型偏好向量 vs 评分向量
============================================================
- 评分向量：用户对每部电影的打分（Rating 表），用于皮尔逊相关系数
- 类型偏好向量：用户喜欢的电影类型分布（如 {"动作": 3.5, "喜剧": 2.0}）
  - 评分权重：score × 0.1（单次评分贡献小，避免噪声）
  - 收藏权重：+1.0（收藏是强信号，权重大于评分）
- 冷启动阶段：无相似用户时，类型偏好向量是唯一的相似度依据

============================================================
为什么收藏 = 10 分
============================================================
收藏是二元的（有/无），评分是 0-10 连续的。为了在同一条公式中混合计算
皮尔逊相关系数，将收藏映射为 10 分（满分），与"用户打了 10 分"的含义一致。
"""
import math

from django.shortcuts import render, redirect
from django.db.models import Q

from ..models import Movie, UserInfo, Collect, Rating, CfRec


def get_user_type_vector(user_id):
    """获取用户的类型偏好向量"""
    type_vector = {}
    all_types = ['动作', '喜剧', '爱情', '科幻', '恐怖', '剧情', '战争', '犯罪', '惊悚', '冒险', '悬疑', '武侠', '奇幻', '动画', '历史']

    for t in all_types:
        type_vector[t] = 0

    # 评分数据：score × 0.1 权重
    user_ratings = Rating.objects.filter(user_id=user_id)
    for rating in user_ratings:
        try:
            movie = Movie.objects.get(id=rating.movie_id)
            if movie.types:
                for t in movie.types.split(' '):
                    if t in type_vector:
                        type_vector[t] += rating.score * 0.1
        except Movie.DoesNotExist:
            pass

    # 收藏数据：+1.0 权重（收藏是强信号）
    user = UserInfo.objects.get(id=user_id)
    user_collects = Collect.objects.filter(collect_user=user.username)
    for collect in user_collects:
        if collect.movie_information and collect.movie_information.types:
            for t in collect.movie_information.types.split(' '):
                if t in type_vector:
                    type_vector[t] += 1.0

    return type_vector


def calculate_similarity(user_id1, user_id2):
    """计算两个用户之间的相似度"""
    user1_ratings = Rating.objects.filter(user_id=user_id1).values('movie_id', 'score')
    user2_ratings = Rating.objects.filter(user_id=user_id2).values('movie_id', 'score')

    user1_collects = Collect.objects.filter(collect_user=UserInfo.objects.get(id=user_id1).username)
    user2_collects = Collect.objects.filter(collect_user=UserInfo.objects.get(id=user_id2).username)

    # 构建评分字典（收藏视为 10 分）
    user1_scores = {}
    for rating in user1_ratings:
        user1_scores[rating['movie_id']] = rating['score']
    for collect in user1_collects:
        if collect.movie_information:
            user1_scores[collect.movie_information.id] = 10.0

    user2_scores = {}
    for rating in user2_ratings:
        user2_scores[rating['movie_id']] = rating['score']
    for collect in user2_collects:
        if collect.movie_information:
            user2_scores[collect.movie_information.id] = 10.0

    common_movies = set(user1_scores.keys()) & set(user2_scores.keys())

    # 皮尔逊相关系数（基于共同电影评分）
    movie_similarity = 0
    if common_movies:
        user1_avg = sum(user1_scores.values()) / len(user1_scores)
        user2_avg = sum(user2_scores.values()) / len(user2_scores)

        numerator = 0
        denominator1 = 0
        denominator2 = 0

        for movie_id in common_movies:
            diff1 = user1_scores[movie_id] - user1_avg
            diff2 = user2_scores[movie_id] - user2_avg
            numerator += diff1 * diff2
            denominator1 += diff1 ** 2
            denominator2 += diff2 ** 2

        if denominator1 != 0 and denominator2 != 0:
            movie_similarity = numerator / (math.sqrt(denominator1) * math.sqrt(denominator2))

    # 余弦相似度（基于类型偏好向量）
    user1_type_vector = get_user_type_vector(user_id1)
    user2_type_vector = get_user_type_vector(user_id2)

    dot_product = sum(user1_type_vector[t] * user2_type_vector[t] for t in user1_type_vector)
    norm1 = math.sqrt(sum(v ** 2 for v in user1_type_vector.values()))
    norm2 = math.sqrt(sum(v ** 2 for v in user2_type_vector.values()))

    type_similarity = dot_product / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0

    # 综合：共同电影时加权，无共同电影时纯类型偏好
    if common_movies:
        return 0.6 * movie_similarity + 0.4 * type_similarity
    return type_similarity


def get_cold_start_recommendations(user_id, top_n=10):
    """冷启动兜底推荐：基于用户类型偏好的热门高分 + 新片优先"""
    rated_movie_ids = set(Rating.objects.filter(user_id=user_id).values_list('movie_id', flat=True))
    collected_movie_ids = set()
    user_collects = Collect.objects.filter(collect_user=UserInfo.objects.get(id=user_id).username)
    for collect in user_collects:
        if collect.movie_information:
            collected_movie_ids.add(collect.movie_information.id)

    exclude_movie_ids = rated_movie_ids | collected_movie_ids

    # 统计类型偏好
    user_preferred_types = {}
    for movie_id in rated_movie_ids:
        try:
            movie = Movie.objects.get(id=movie_id)
            if movie.types:
                for t in movie.types.split(' '):
                    user_preferred_types[t] = user_preferred_types.get(t, 0) + 1
        except Movie.DoesNotExist:
            pass

    for movie_id in collected_movie_ids:
        try:
            movie = Movie.objects.get(id=movie_id)
            if movie.types:
                for t in movie.types.split(' '):
                    user_preferred_types[t] = user_preferred_types.get(t, 0) + 2  # 收藏权重更高
        except Movie.DoesNotExist:
            pass

    sorted_types = sorted(user_preferred_types.items(), key=lambda x: x[1], reverse=True)
    preferred_types = [t[0] for t in sorted_types[:2]]

    if preferred_types:
        preferred_movies = list(
            Movie.objects.filter(types__icontains=preferred_types[0])
            .exclude(id__in=exclude_movie_ids)
            .order_by('-score', '-date')
            .values_list('id', flat=True)
        )

        if len(preferred_movies) < top_n and len(preferred_types) > 1:
            second = list(
                Movie.objects.filter(types__icontains=preferred_types[1])
                .exclude(id__in=exclude_movie_ids | set(preferred_movies))
                .order_by('-score', '-date')
                .values_list('id', flat=True)
            )
            preferred_movies.extend(second)

        if len(preferred_movies) < top_n:
            other = list(
                Movie.objects.exclude(id__in=exclude_movie_ids | set(preferred_movies))
                .order_by('-score', '-date')
                .values_list('id', flat=True)[:top_n - len(preferred_movies)]
            )
            preferred_movies.extend(other)

        return preferred_movies[:top_n]
    else:
        return list(
            Movie.objects.exclude(id__in=exclude_movie_ids)
            .order_by('-score', '-date')
            .values_list('id', flat=True)[:top_n]
        )


def generate_recommendations(user_id, top_n=10):
    """基于用户的协同过滤生成推荐（包含类型偏好加权）"""
    try:
        current_user = UserInfo.objects.get(id=user_id)
        other_users = UserInfo.objects.exclude(id=user_id)

        current_user_type_vector = get_user_type_vector(user_id)

        # 计算与所有用户的相似度
        similarities = []
        for other_user in other_users:
            sim = calculate_similarity(user_id, other_user.id)
            if sim > 0:
                similarities.append((other_user.id, sim))

        if not similarities:
            return []

        similarities.sort(key=lambda x: x[1], reverse=True)
        K = 5
        top_similar_users = similarities[:K]

        # 排除已评分/已收藏的电影
        current_user_rated_movies = set(Rating.objects.filter(user_id=user_id).values_list('movie_id', flat=True))
        current_user_collected_movies = set()
        user_collects = Collect.objects.filter(collect_user=current_user.username)
        for collect in user_collects:
            if collect.movie_information:
                current_user_collected_movies.add(collect.movie_information.id)

        exclude_movies = current_user_rated_movies | current_user_collected_movies

        candidate_movies = {}

        for user_id_sim, sim_score in top_similar_users:
            # 相似用户的评分
            user_ratings = Rating.objects.filter(user_id=user_id_sim)
            for rating in user_ratings:
                if rating.movie_id not in exclude_movies:
                    base_score = sim_score * rating.score
                    # 类型偏好加成
                    try:
                        movie = Movie.objects.get(id=rating.movie_id)
                        if movie.types:
                            type_bonus = sum(
                                current_user_type_vector.get(t, 0) * 0.5
                                for t in movie.types.split(' ')
                            )
                            base_score += type_bonus
                    except Movie.DoesNotExist:
                        pass
                    candidate_movies[rating.movie_id] = candidate_movies.get(rating.movie_id, 0) + base_score

            # 相似用户的收藏（视为 10 分）
            sim_user_collects = Collect.objects.filter(collect_user=UserInfo.objects.get(id=user_id_sim).username)
            for collect in sim_user_collects:
                if collect.movie_information and collect.movie_information.id not in exclude_movies:
                    base_score = sim_score * 10.0
                    if collect.movie_information.types:
                        type_bonus = sum(
                            current_user_type_vector.get(t, 0) * 0.5
                            for t in collect.movie_information.types.split(' ')
                        )
                        base_score += type_bonus
                    candidate_movies[collect.movie_information.id] = candidate_movies.get(collect.movie_information.id, 0) + base_score

        if not candidate_movies:
            return []

        sorted_candidates = sorted(candidate_movies.items(), key=lambda x: x[1], reverse=True)
        top_recommendations = sorted_candidates[:top_n]

        # 持久化到 CfRec 表
        CfRec.objects.filter(user_id=user_id).delete()
        for movie_id, score in top_recommendations:
            CfRec.objects.create(user_id=user_id, movie_id=movie_id, rating=score)

        return [movie_id for movie_id, _ in top_recommendations]

    except Exception as e:
        print(f"协同过滤推荐生成错误: {str(e)}")
        return []


def recommend(request):
    """推荐页视图"""
    try:
        if not request.user.is_authenticated:
            return redirect('/login/')

        user_id = request.user.id
        top_n = 10

        current_user = UserInfo.objects.get(id=user_id)
        current_user_collected_movies = set()
        user_collects = Collect.objects.filter(collect_user=current_user.username)
        for collect in user_collects:
            if collect.movie_information:
                current_user_collected_movies.add(collect.movie_information.id)

        # 三层回退策略
        realtime_rec_ids = generate_recommendations(user_id, top_n=top_n)

        if realtime_rec_ids:
            recommended_movie_ids = realtime_rec_ids
        else:
            # 回退到 CfRec 缓存
            cf_rec_ids = list(
                CfRec.objects.filter(user_id=user_id)
                .order_by('-rating')
                .values_list('movie_id', flat=True)[:top_n]
            )
            if cf_rec_ids:
                recommended_movie_ids = [mid for mid in cf_rec_ids if mid not in current_user_collected_movies]
            else:
                # 最终回退：冷启动热门
                recommended_movie_ids = get_cold_start_recommendations(user_id, top_n=top_n)
                CfRec.objects.filter(user_id=user_id).delete()
                for idx, movie_id in enumerate(recommended_movie_ids):
                    CfRec.objects.create(user_id=user_id, movie_id=movie_id, rating=float(top_n - idx))

        # 过滤已收藏
        recommended_movie_ids = [mid for mid in recommended_movie_ids if mid not in current_user_collected_movies]

        # 数量不足时补充
        if len(recommended_movie_ids) < top_n:
            cold_start_ids = get_cold_start_recommendations(user_id, top_n=top_n)
            additional = [mid for mid in cold_start_ids
                         if mid not in current_user_collected_movies and mid not in recommended_movie_ids]
            recommended_movie_ids.extend(additional)
            recommended_movie_ids = recommended_movie_ids[:top_n]

        # 保持顺序查出 Movie 对象
        movie_map = {movie.id: movie for movie in Movie.objects.filter(id__in=recommended_movie_ids)}
        data_list = [movie_map[mid] for mid in recommended_movie_ids if mid in movie_map]

        return render(request, 'front_recommendation.html', {'data_list': data_list})

    except Exception as e:
        print(f'推荐功能错误：{str(e)}')
        return render(request, 'front_recommendation.html', {'data_list': []})
