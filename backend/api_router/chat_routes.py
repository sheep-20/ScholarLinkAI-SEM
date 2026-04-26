"""
Chat API - AI 对话接口
"""
from flask import Blueprint, request, jsonify
from flask_restx import Namespace, Resource, fields
from datetime import datetime
import sys
import os
import logging

# 添加父目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from service.chat_service import get_chat_service
from service.dbmanager import DbManager

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建命名空间
chat_ns = Namespace('chat', description='AI对话接口')

# 定义响应模型
chat_history_model = chat_ns.model('ChatHistory', {
    'id': fields.Integer(description='对话记录ID'),
    'recommendation_id': fields.Integer(description='推荐记录ID'),
    'user_message': fields.String(description='用户消息'),
    'ai_response': fields.String(description='AI回复'),
    'created_at': fields.String(description='创建时间')
})

send_message_request_model = chat_ns.model('SendMessageRequest', {
    'recommendation_id': fields.Integer(required=True, description='推荐记录ID'),
    'user_message': fields.String(required=True, description='用户消息')
})

send_message_response_model = chat_ns.model('SendMessageResponse', {
    'message': fields.String(description='响应消息'),
    'status': fields.String(description='响应状态'),
    'timestamp': fields.String(description='时间戳'),
    'data': fields.Raw(description='响应数据')
})


@chat_ns.route('/history/<int:recommendation_id>')
class ChatHistory(Resource):
    @chat_ns.doc('get_chat_history')
    @chat_ns.marshal_with(chat_ns.model('ChatHistoryResponse', {
        'message': fields.String(description='响应消息'),
        'status': fields.String(description='响应状态'),
        'timestamp': fields.String(description='时间戳'),
        'data': fields.Nested(chat_ns.model('ChatHistoryData', {
            'chat_history': fields.List(fields.Nested(chat_history_model)),
            'paper_info': fields.Raw(description='论文信息')
        }))
    }))
    def get(self, recommendation_id):
        """
        获取对话历史

        根据 recommendation_id 获取该推荐记录的对话历史
        """
        try:
            db = DbManager()

            # 获取对话历史
            chat_history = db.query_all(
                """
                SELECT ch.id, ch.recommendation_id, ch.user_message, ch.ai_response, ch.created_at
                FROM chat_history ch
                WHERE ch.recommendation_id = %s
                ORDER BY ch.created_at ASC
                """,
                (recommendation_id,)
            )

            # 获取论文信息（通过recommendations表关联）
            paper_info = db.query_one(
                """
                SELECT p.paper_id, p.title, p.abstract, p.author, p.pdf_url
                FROM recommendations r
                JOIN papers p ON r.paper_id = p.paper_id
                WHERE r.id = %s
                """,
                (recommendation_id,)
            )

            if not paper_info:
                return {
                    'message': f'推荐记录不存在 (recommendation_id={recommendation_id})',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 404

            return {
                'message': '获取对话历史成功',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'chat_history': chat_history,
                    'paper_info': paper_info
                }
            }

        except Exception as e:
            logger.error(f"获取对话历史失败: {str(e)}", exc_info=True)
            return {
                'message': f'获取对话历史失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500


@chat_ns.route('/send')
class SendMessage(Resource):
    @chat_ns.doc('send_message')
    @chat_ns.expect(send_message_request_model)
    @chat_ns.marshal_with(send_message_response_model)
    def post(self):
        """
        发送消息给AI

        向AI发送用户消息，并保存对话历史
        """
        try:
            data = request.get_json()

            if not data:
                return {
                    'message': '请求数据格式错误',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 400

            recommendation_id = data.get('recommendation_id')
            user_message = data.get('user_message')

            if not recommendation_id or not user_message:
                return {
                    'message': '请提供 recommendation_id 和 user_message 参数',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 400

            db = DbManager()

            # 获取论文摘要（通过recommendations表关联）
            paper_info = db.query_one(
                """
                SELECT p.abstract
                FROM recommendations r
                JOIN papers p ON r.paper_id = p.paper_id
                WHERE r.id = %s
                """,
                (recommendation_id,)
            )

            if not paper_info:
                return {
                    'message': f'推荐记录不存在 (recommendation_id={recommendation_id})',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 404

            # 获取对话历史（用于上下文）
            conversation_history = db.query_all(
                """
                SELECT user_message, ai_response
                FROM chat_history
                WHERE recommendation_id = %s
                ORDER BY created_at ASC
                """,
                (recommendation_id,)
            )

            # 调用AI服务
            chat_service = get_chat_service()
            ai_response = chat_service.chat_with_ai(
                user_message=user_message,
                paper_abstract=paper_info['abstract'],
                conversation_history=conversation_history
            )

            # 保存对话记录到数据库
            db.execute(
                """
                INSERT INTO chat_history
                (recommendation_id, user_message, ai_response)
                VALUES (%s, %s, %s)
                """,
                (recommendation_id, user_message, ai_response)
            )

            return {
                'message': '消息发送成功',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'user_message': user_message,
                    'ai_response': ai_response
                }
            }

        except Exception as e:
            logger.error(f"发送消息失败: {str(e)}", exc_info=True)
            return {
                'message': f'发送消息失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500