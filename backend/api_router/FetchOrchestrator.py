"""
FetchOrchestrator API - 论文抓取协调器接口
"""
from flask import request, jsonify
from flask_restx import Namespace, Resource, fields
from datetime import datetime
import sys
import os
import logging

# 添加父目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orchestrator.fetch_orchestrator import FetchOrchestrator

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建命名空间
fetch_ns = Namespace('fetchOrchestrator', description='论文抓取协调器接口')

# 定义响应模型
fetch_response_model = fetch_ns.model('FetchResponse', {
    'message': fields.String(description='响应消息'),
    'status': fields.String(description='响应状态'),
    'timestamp': fields.String(description='时间戳'),
    'data': fields.Raw(description='响应数据')
})

# 定义请求模型
fetch_request_model = fetch_ns.model('FetchRequest', {
    'topk': fields.Integer(
        description='抓取论文数量，None或大数字表示全部抓取',
        required=False,
        default=None,
        example=10
    )
})


@fetch_ns.route('/')
class FetchPapers(Resource):
    @fetch_ns.doc('fetch_papers_orchestrator')
    @fetch_ns.expect(fetch_request_model, validate=False)
    @fetch_ns.marshal_with(fetch_response_model)
    def post(self):
        """
        抓取论文并保存到数据库

        使用FetchOrchestrator协调论文抓取流程，支持指定抓取数量。
        topk参数：抓取论文数量，传入None或大数字表示全部抓取。
        """
        try:
            # 获取请求参数
            data = request.get_json() or {}
            topk = data.get('topk', None)

            # 验证topk参数
            if topk is not None and (not isinstance(topk, int) or topk <= 0):
                return {
                    'message': '参数错误：topk必须是正整数或None',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 400

            logger.info(f"开始调用FetchOrchestrator，topk={topk}")

            # 调用FetchOrchestrator
            orchestrator = FetchOrchestrator()
            result = orchestrator.fetch_and_save_papers(max_results=topk)

            logger.info(f"FetchOrchestrator执行完成: {result}")

            return {
                'message': result.get('message', '抓取完成'),
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': result
            }

        except Exception as e:
            logger.error(f"调用FetchOrchestrator失败: {str(e)}", exc_info=True)
            return {
                'message': f'抓取论文失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500
