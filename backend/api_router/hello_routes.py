from flask import Blueprint, request, jsonify
from datetime import datetime
import sys
import os

# 添加父目录到Python路径以导入config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

# 创建蓝图
hello_bp = Blueprint('hello', __name__)

@hello_bp.route('/hello', methods=['GET'])
def hello_world():
    """Hello World API - GET请求"""
    return jsonify({
        'message': 'Hello World! 欢迎使用 ScholarLink AI API',
        'status': 'success',
        'timestamp': datetime.now().isoformat(),
        'data': {
            'service': 'ScholarLink AI Backend',
            'version': Config.API_VERSION,
            'description': '这是一个基于 Flask 的 Python 后端服务'
        }
    })

@hello_bp.route('/hello/<name>', methods=['GET'])
def hello_name(name):
    """带参数的 Hello API - GET请求"""
    return jsonify({
        'message': f'Hello {name}! 欢迎使用 ScholarLink AI API',
        'status': 'success',
        'timestamp': datetime.now().isoformat(),
        'data': {
            'name': name,
            'service': 'ScholarLink AI Backend',
            'version': Config.API_VERSION
        }
    })

@hello_bp.route('/hello', methods=['POST'])
def hello_post():
    """Hello API - POST请求"""
    data = request.get_json()
    
    if not data:
        return jsonify({
            'error': '请求数据格式错误',
            'message': '请提供 JSON 格式的数据',
            'status': 'error'
        }), 400
    
    name = data.get('name')
    message = data.get('message', '')
    
    if not name:
        return jsonify({
            'error': '缺少必要参数',
            'message': '请提供 name 参数',
            'status': 'error'
        }), 400
    
    return jsonify({
        'message': f'Hello {name}! {message if message else "欢迎使用 ScholarLink AI API"}',
        'status': 'success',
        'timestamp': datetime.now().isoformat(),
        'data': {
            'name': name,
            'custom_message': message,
            'service': 'ScholarLink AI Backend',
            'version': Config.API_VERSION
        }
    })

@hello_bp.route('/hello/status', methods=['GET'])
def hello_status():
    """Hello API 状态检查"""
    return jsonify({
        'status': 'running',
        'message': 'Hello API 运行正常',
        'timestamp': datetime.now().isoformat(),
        'endpoints': {
            'GET /api/hello': '基础 Hello World',
            'GET /api/hello/<name>': '带参数的 Hello',
            'POST /api/hello': 'POST 请求的 Hello',
            'GET /api/hello/status': 'API 状态检查'
        }
    })
