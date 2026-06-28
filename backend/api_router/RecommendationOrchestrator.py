"""
RecommendationOrchestrator API - 论文推荐和博客生成协调器接口
"""
from flask import request, jsonify
from flask_restx import Namespace, Resource, fields
from datetime import datetime
import sys
import os
import logging

# 添加父目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.recommendation_orchestrator import RecommendationOrchestrator
from service.search_service import SearchService

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建命名空间
recommendation_ns = Namespace('recommendationOrchestrator', description='论文推荐和博客生成协调器接口')

# 定义响应模型
recommend_response_model = recommendation_ns.model('RecommendResponse', {
    'message': fields.String(description='响应消息'),
    'status': fields.String(description='响应状态'),
    'timestamp': fields.String(description='时间戳'),
    'data': fields.Raw(description='响应数据')
})

# 定义博客模型
blog_model = recommendation_ns.model('Blog', {
    'paper_id': fields.Integer(description='论文ID'),
    'title': fields.String(description='论文标题'),
    'pdf_url': fields.String(description='PDF链接'),
    'blog_content': fields.String(description='生成的博客内容')
})

# 定义请求模型（可选，每用户的推荐数量，默认3）
recommend_request_model = recommendation_ns.model('RecommendRequest', {
    'topk_per_user': fields.Integer(
        description='每个用户取前多少篇推荐论文（默认3，最大10）',
        required=False,
        default=3,
        example=3,
        min=1,
        max=10
    )
})

# 推荐列表模型（用于文档描述）
recommend_item_model = recommendation_ns.model('RecommendItem', {
    'user_id': fields.Integer(description='用户ID'),
    'paper_id': fields.Integer(description='论文ID'),
    'title': fields.String(description='论文标题'),
    'author': fields.String(description='作者'),
    'abstract': fields.String(description='摘要'),
    'pdf_url': fields.String(description='PDF链接'),
    'blog': fields.String(description='生成的博客内容'),
    'created_at': fields.String(description='创建时间'),
    'liked': fields.Boolean(description='当前用户是否已喜欢')
})

# 收藏项模型
favorite_item_model = recommendation_ns.model('FavoriteItem', {
    'user_id': fields.Integer(description='用户ID'),
    'paper_id': fields.Integer(description='论文ID'),
    'title': fields.String(description='论文标题'),
    'author': fields.String(description='作者'),
    'abstract': fields.String(description='摘要'),
    'pdf_url': fields.String(description='PDF链接'),
    'blog': fields.String(description='可用的博客内容'),
    'liked_at': fields.String(description='收藏时间'),
    'blog_created_at': fields.String(description='博客生成时间'),
    'liked': fields.Boolean(description='恒为True，标记已收藏')
})


@recommendation_ns.route('/')
class GenerateBlogs(Resource):
    @recommendation_ns.doc('generate_blogs_orchestrator')
    @recommendation_ns.expect(recommend_request_model, validate=False)
    @recommendation_ns.marshal_with(recommend_response_model)
    def post(self):
        """
        为所有用户生成推荐博客并入库

        调用后自动：
        1) 读取所有有兴趣 embedding 的用户
        2) 每用户计算前 topk_per_user 篇推荐论文
        3) 去重论文集合，博客只生成一次
        4) 写入 recommendations 表（ON DUPLICATE KEY UPDATE）
        """
        try:
            # 获取请求参数
            data = request.get_json() or {}
            topk_per_user = data.get('topk_per_user', 3)

            if not isinstance(topk_per_user, int) or topk_per_user <= 0:
                return {
                    'message': '参数错误：topk_per_user必须是正整数',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 400

            if topk_per_user > 10:
                logger.warning(f"topk_per_user超过最大值10，已调整为10")
                topk_per_user = 10

            logger.info(f"开始批量为所有用户生成博客，每用户topk={topk_per_user}")

            # 调用RecommendationOrchestrator
            orchestrator = RecommendationOrchestrator()
            result = orchestrator.generate_blogs_for_all_users(topk_per_user=topk_per_user)

            return {
                'message': '批量生成完成',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'users': result.get('users', 0),
                    'papers': result.get('papers', 0),
                    'generated': result.get('generated', 0),
                    'saved_pairs': result.get('saved_pairs', 0),
                    'failed_generate': result.get('failed_generate', 0),
                    'failed_save': result.get('failed_save', 0),
                    'topk_per_user': topk_per_user
                }
            }

        except Exception as e:
            logger.error(f"调用RecommendationOrchestrator失败: {str(e)}", exc_info=True)
            return {
                'message': f'生成博客失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500


@recommendation_ns.route('/list')
class ListRecommendations(Resource):
    @recommendation_ns.doc('list_recommendations')
    @recommendation_ns.marshal_with(recommend_response_model)
    def get(self):
        """
        获取推荐博客列表：
        - 可选 query 参数 user_id：指定用户的推荐；缺省则返回默认top（前5）。
        - 可选 query 参数 limit：数量上限，默认5，最大50。
        """
        try:
            user_id = request.args.get('user_id')
            limit = request.args.get('limit', 5)

            if user_id is not None:
                try:
                    user_id = int(user_id)
                    if user_id <= 0:
                        raise ValueError()
                except Exception:
                    return {
                        'message': '参数错误：user_id必须是正整数',
                        'status': 'error',
                        'timestamp': datetime.now().isoformat(),
                        'data': None
                    }, 400

            try:
                limit = int(limit)
                if limit <= 0:
                    limit = 5
                if limit > 50:
                    limit = 50
            except Exception:
                limit = 5

            orchestrator = RecommendationOrchestrator()
            recs = orchestrator.list_recommendations(user_id=user_id, limit=limit)
            if user_id is not None and not recs:
                recs = orchestrator.list_recommendations(user_id=None, limit=5)

            return {
                'message': 'ok',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'recommendations': recs,
                    'user_id': user_id,
                    'limit': limit
                }
            }

        except Exception as e:
            logger.error(f"获取推荐列表失败: {str(e)}", exc_info=True)
            return {
                'message': f'获取推荐列表失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500


@recommendation_ns.route('/like')
class LikeRecommendation(Resource):
    @recommendation_ns.doc('like_recommendation')
    @recommendation_ns.expect(recommendation_ns.model('LikePayload', {
        'user_id': fields.Integer(required=True, description='用户ID'),
        'paper_id': fields.Integer(required=True, description='论文ID'),
        'action': fields.String(required=False, description='like 或 unlike，默认 like')
    }), validate=False)
    @recommendation_ns.marshal_with(recommend_response_model)
    def post(self):
        """
        收藏/取消收藏 推荐的论文
        body: {user_id, paper_id, action=like|unlike}
        """
        try:
            data = request.get_json() or {}
            user_id = data.get('user_id')
            paper_id = data.get('paper_id')
            action = (data.get('action') or 'like').lower()

            # 校验
            try:
                user_id = int(user_id)
                paper_id = int(paper_id)
                if user_id <= 0 or paper_id <= 0:
                    raise ValueError()
            except Exception:
                return {
                    'message': '参数错误：user_id 与 paper_id 必须是正整数',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 400

            orchestrator = RecommendationOrchestrator()
            ok = orchestrator.like_paper(user_id, paper_id) if action != 'unlike' else orchestrator.unlike_paper(user_id, paper_id)

            if not ok:
                return {
                    'message': f'{action} 失败',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 500

            return {
                'message': f'{action} 成功',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'user_id': user_id,
                    'paper_id': paper_id,
                    'action': action
                }
            }

        except Exception as e:
            logger.error(f"收藏操作失败: {str(e)}", exc_info=True)
            return {
                'message': f'收藏操作失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500


@recommendation_ns.route('/favorites')
class ListFavorites(Resource):
    @recommendation_ns.doc('list_favorites')
    @recommendation_ns.marshal_with(recommend_response_model)
    def get(self):
        """
        获取用户收藏列表
        - 必选 query 参数 user_id
        - 可选 limit，默认20，最大50
        """
        try:
            user_id = request.args.get('user_id')
            limit = request.args.get('limit', 20)

            try:
                user_id = int(user_id)
                if user_id <= 0:
                    raise ValueError()
            except Exception:
                return {
                    'message': '参数错误：user_id必须是正整数',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 400

            try:
                limit = int(limit)
                if limit <= 0:
                    limit = 20
                if limit > 50:
                    limit = 50
            except Exception:
                limit = 20

            orchestrator = RecommendationOrchestrator()
            favs = orchestrator.list_liked(user_id=user_id, limit=limit)

            return {
                'message': 'ok',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'favorites': favs,
                    'user_id': user_id,
                    'limit': limit
                }
            }

        except Exception as e:
            logger.error(f"获取收藏列表失败: {str(e)}", exc_info=True)
            return {
                'message': f'获取收藏列表失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500


@recommendation_ns.route('/search')
class SearchPapers(Resource):
    @recommendation_ns.doc('search_papers')
    @recommendation_ns.marshal_with(recommend_response_model)
    def get(self):
        """
        语义搜索论文：
        - query: 必填，查询文本
        - topk: 可选，默认5，最大10
        返回最匹配的论文，若有博客则附带blog字段
        """
        try:
            query = request.args.get('query', '').strip()
            topk = request.args.get('topk', 5)

            if not query:
                return {
                    'message': '参数错误：query不能为空',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 400

            try:
                topk = int(topk)
                if topk <= 0:
                    topk = 5
                if topk > 10:
                    topk = 10
            except Exception:
                topk = 5

            svc = SearchService()
            items = svc.search(query=query, topk=topk)

            return {
                'message': 'ok',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'results': items,
                    'query': query,
                    'topk': topk
                }
            }

        except Exception as e:
            logger.error(f"搜索失败: {str(e)}", exc_info=True)
            return {
                'message': f'搜索失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500
