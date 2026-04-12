from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_restx import Api, Resource, fields
from datetime import datetime
import os
import sys

# 添加当前目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config

def create_app():
    """创建Flask应用实例"""
    app = Flask(__name__)
    
    # 配置应用
    app.config.from_object(Config)
    
    # 启用CORS
    CORS(app)
    
    # 基础路由 - API 导航
    @app.route('/')
    def api_root():
        """API 根路径"""
        return jsonify({
            'message': 'ScholarLink AI API Base',
            'version': Config.API_VERSION,
            'status': 'running',
            'timestamp': datetime.now().isoformat(),
            'endpoints': {
                'swagger_docs': '/docs/',
                'health': '/health'
            },
            'description': '访问 /docs/ 查看完整的 Swagger API 文档'
        })
    
    # 创建 API 文档
    api = Api(
        app,
        version=Config.API_VERSION,
        title=Config.API_TITLE if hasattr(Config, 'API_TITLE') else 'ScholarLink AI',
        description='ScholarLink AI 后端接口文档 (Development)',
        doc='/docs/',  # Swagger UI 路径
        prefix='' 
    )
    
    # ====== 第一阶段：基础测试接口 ======
    hello_ns = api.namespace('hello', description='基础连通性测试接口')
    
    hello_model = api.model('HelloResponse', {
        'message': fields.String(required=True, description='响应消息'),
        'status': fields.String(required=True, description='响应状态'),
        'timestamp': fields.String(required=True, description='时间戳')
    })

    @hello_ns.route('/')
    class HelloWorld(Resource):
        @hello_ns.doc('hello_world')
        @hello_ns.marshal_with(hello_model)
        def get(self):
            """获取服务基础状态"""
            return {
                'message': 'Hello! ScholarLink AI Backend is ready.',
                'status': 'success',
                'timestamp': datetime.now().isoformat()
            }

    # TODO: 后续分批引入业务路由
    api.add_namespace(papers_ns, path='/papers')
    api.add_namespace(users_ns, path='/users')
    
    # 健康检查接口 (用于容器或负载均衡检测)
    @app.route('/health')
    def health_check():
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'environment': Config.ENV if hasattr(Config, 'ENV') else 'development'
        })
    
    # 全局错误处理
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': '接口不存在', 'path': request.path}), 404
        
    return app

if __name__ == '__main__':
    app = create_app()
    
    host = getattr(Config, 'HOST', '0.0.0.0')
    port = getattr(Config, 'PORT', 5000)
    debug_mode = getattr(Config, 'DEBUG', True)
    
    print("🚀 ScholarLink AI 后端框架初始化完成...")
    print(f"📍 API 文档地址: http://127.0.0.1:{port}/docs/")
    print("-" * 50)
    
    app.run(host=host, port=port, debug=debug_mode)