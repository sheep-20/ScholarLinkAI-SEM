from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_restx import Api, Resource, fields
from datetime import datetime
import os
import sys

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from api_router.hello_routes import hello_bp
from api_router.papers_routes import papers_ns
from api_router.users_routes import users_ns
from api_router.RecommendationOrchestrator import recommendation_ns
from api_router.FetchOrchestrator import fetch_ns
from api_router.chat_routes import chat_ns

def create_app():
    """创建Flask应用实例"""
    app = Flask(__name__)
    
    # 配置应用
    app.config.from_object(Config)
    
    # 启用CORS
    CORS(app)
    
    # 先定义根路径（在 Api 对象创建之前，确保优先级）
    @app.route('/')
    def api_root():
        """API 根路径 - 显示所有可用的 API 端点"""
        return jsonify({
            'message': 'ScholarLink AI API',
            'version': Config.API_VERSION,
            'status': 'running',
            'timestamp': datetime.now().isoformat(),
            'endpoints': {
                'swagger_docs': '/docs/',
                'hello': '/hello/',
                'papers': {
                    'fetch': '/papers/fetch',
                    'list': '/papers/list',
                    'detail': '/papers/<paper_id>'
                },
                'users': {
                    'register': '/users/register',
                    'login': '/users/login',
                    'list': '/users/list',
                    'detail': '/users/<user_id>'
                },
                'recommendationOrchestrator': '/recommendationOrchestrator/',
                'fetchOrchestrator': '/fetchOrchestrator/',
                'chat': {
                    'history': '/chat/history/<recommendation_id>',
                    'send': '/chat/send'
                },
                'health': '/health'
            },
            'description': '访问 /docs/ 查看完整的 Swagger API 文档'
        })
    
    # 创建 API 文档
    api = Api(
        app,
        version=Config.API_VERSION,
        title=Config.API_TITLE,
        description=Config.API_DESCRIPTION,
        doc='/docs/',  # Swagger UI 路径
        prefix=''  # 不使用 /api 前缀，所有接口直接在根路径下
    )
    
    # 创建命名空间
    hello_ns = api.namespace('hello', description='Hello World API 接口')
    
    # 注册 papers 命名空间
    api.add_namespace(papers_ns, path='/papers')

    # 注册 users 命名空间
    api.add_namespace(users_ns, path='/users')

    # 注册 recommendationOrchestrator 命名空间
    api.add_namespace(recommendation_ns, path='/recommendationOrchestrator')

    # 注册 fetchOrchestrator 命名空间
    api.add_namespace(fetch_ns, path='/fetchOrchestrator')

    # 注册 chat 命名空间
    api.add_namespace(chat_ns, path='/chat')
    
    # 定义数据模型
    hello_model = api.model('HelloResponse', {
        'message': fields.String(required=True, description='响应消息'),
        'status': fields.String(required=True, description='响应状态'),
        'timestamp': fields.String(required=True, description='时间戳'),
        'data': fields.Raw(description='响应数据')
    })
    
    hello_request_model = api.model('HelloRequest', {
        'name': fields.String(required=True, description='姓名'),
        'message': fields.String(description='自定义消息')
    })
    
    # Hello World API 路由
    @hello_ns.route('/')
    class HelloWorld(Resource):
        @hello_ns.doc('hello_world')
        @hello_ns.marshal_with(hello_model)
        def get(self):
            """获取 Hello World 消息"""
            return {
                'message': 'Hello World! 欢迎使用 ScholarLink AI API',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'service': 'ScholarLink AI Backend',
                    'version': Config.API_VERSION,
                    'description': '这是一个基于 Flask 的 Python 后端服务'
                }
            }
    
    @hello_ns.route('/<name>')
    class HelloName(Resource):
        @hello_ns.doc('hello_name')
        @hello_ns.marshal_with(hello_model)
        def get(self, name):
            """根据姓名获取 Hello 消息"""
            return {
                'message': f'Hello {name}! 欢迎使用 ScholarLink AI API',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'name': name,
                    'service': 'ScholarLink AI Backend',
                    'version': Config.API_VERSION
                }
            }
    
    @hello_ns.route('/post')
    class HelloPost(Resource):
        @hello_ns.doc('hello_post')
        @hello_ns.expect(hello_request_model)
        @hello_ns.marshal_with(hello_model)
        def post(self):
            """通过 POST 请求发送 Hello 消息"""
            data = request.get_json()
            
            if not data:
                api.abort(400, '请求数据格式错误')
            
            name = data.get('name')
            message = data.get('message', '')
            
            if not name:
                api.abort(400, '请提供 name 参数')
            
            return {
                'message': f'Hello {name}! {message if message else "欢迎使用 ScholarLink AI API"}',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'name': name,
                    'custom_message': message,
                    'service': 'ScholarLink AI Backend',
                    'version': Config.API_VERSION
                }
            }
    
    @hello_ns.route('/status')
    class HelloStatus(Resource):
        @hello_ns.doc('hello_status')
        @hello_ns.marshal_with(hello_model)
        def get(self):
            """获取 Hello API 状态"""
            return {
                'message': 'Hello API 运行正常',
                'status': 'running',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'endpoints': {
                        'GET /hello/': '基础 Hello World',
                        'GET /hello/<name>': '带参数的 Hello',
                        'POST /hello/post': 'POST 请求的 Hello',
                        'GET /hello/status': 'API 状态检查'
                    }
                }
            }
    
    # 注册原有的蓝图（保持兼容性）
    app.register_blueprint(hello_bp, url_prefix='/v1')
    
    # 健康检查接口
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'message': '服务运行正常',
            'timestamp': datetime.now().isoformat(),
            'version': Config.API_VERSION,
            'environment': Config.ENV
        })
    
    # 404错误处理
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            'error': '接口不存在',
            'message': f'无法找到 {request.path} 接口',
            'timestamp': datetime.now().isoformat()
        }), 404
    
    # 500错误处理
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            'error': '服务器内部错误',
            'message': '服务器出现错误，请稍后重试',
            'timestamp': datetime.now().isoformat()
        }), 500
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    print("🚀 ScholarLink AI 后端服务正在启动...")
    print(f"📍 服务地址: http://{Config.HOST}:{Config.PORT}")
    print(f"🌍 环境: {Config.ENV}")
    print(f"🔧 调试模式: {Config.DEBUG}")
    print(f"⏰ 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
