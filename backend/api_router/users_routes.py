"""
Users API - 用户管理接口
"""
from flask import request
from flask_restx import Namespace, Resource, fields
from datetime import datetime
import sys
import os
import logging
import hashlib

# 添加父目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from service.dbmanager import DbManager
from orchestrator.recommendation_orchestrator import RecommendationOrchestrator

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建命名空间
users_ns = Namespace('users', description='用户管理接口')

# 定义响应模型
user_model = users_ns.model('User', {
    'user_id': fields.Integer(description='用户ID'),
    'username': fields.String(required=True, description='用户名'),
    'interest': fields.String(description='用户兴趣')
})

user_create_model = users_ns.model('UserCreate', {
    'username': fields.String(required=True, description='用户名'),
    'password': fields.String(required=True, description='密码'),
    'interest': fields.String(description='用户兴趣（可选）')
})

user_update_interest_model = users_ns.model('UserUpdateInterest', {
    'interest': fields.String(required=True, description='用户兴趣')
})

user_login_model = users_ns.model('UserLogin', {
    'username': fields.String(required=True, description='用户名'),
    'password': fields.String(required=True, description='密码')
})

response_model = users_ns.model('Response', {
    'message': fields.String(description='响应消息'),
    'status': fields.String(description='响应状态'),
    'timestamp': fields.String(description='时间戳'),
    'data': fields.Raw(description='响应数据')
})


def hash_password(password: str) -> str:
    """简单的密码哈希（生产环境应使用 bcrypt）"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    return hash_password(password) == hashed


@users_ns.route('/login')
class UserLogin(Resource):
    @users_ns.doc('user_login')
    @users_ns.expect(user_login_model)
    @users_ns.marshal_with(response_model)
    def post(self):
        """
        用户登录
        
        验证用户名和密码，返回用户信息
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
            
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                return {
                    'message': '用户名和密码不能为空',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 400
            
            db = DbManager()
            
            # 查询用户
            user = db.query_one(
                "SELECT user_id, username, password, interest FROM users WHERE username = %s",
                (username,)
            )
            
            if not user:
                return {
                    'message': '用户名或密码错误',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 401
            
            # 验证密码
            if not verify_password(password, user['password']):
                return {
                    'message': '用户名或密码错误',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 401
            
            logger.info(f"用户登录成功: {username} (ID={user['user_id']})")
            
            return {
                'message': '登录成功',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'user_id': user['user_id'],
                    'username': user['username'],
                    'interest': user['interest']
                }
            }
            
        except Exception as e:
            logger.error(f"用户登录失败: {str(e)}", exc_info=True)
            return {
                'message': f'登录失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500


@users_ns.route('/register')
class UserRegister(Resource):
    @users_ns.doc('register_user')
    @users_ns.expect(user_create_model)
    @users_ns.marshal_with(response_model)
    def post(self):
        """
        用户注册
        
        创建新用户账号
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
            
            username = data.get('username')
            password = data.get('password')
            interest = data.get('interest', '')
            
            if not username or not password:
                return {
                    'message': '用户名和密码不能为空',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 400
            
            db = DbManager()
            
            # 检查用户名是否已存在
            existing = db.query_one(
                "SELECT user_id FROM users WHERE username = %s",
                (username,)
            )
            
            if existing:
                return {
                    'message': f'用户名 {username} 已存在',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 409
            
            # 密码加密
            hashed_password = hash_password(password)
            
            # 插入用户
            result = db.execute(
                """
                INSERT INTO users (username, password, interest)
                VALUES (%s, %s, %s)
                """,
                (username, hashed_password, interest)
            )
            
            user_id = result['lastrowid']
            logger.info(f"用户注册成功: {username} (ID={user_id})")
            
            # 如果提供了兴趣，触发生成embedding
            if interest:
                try:
                    orchestrator = RecommendationOrchestrator()
                    orchestrator.update_user_interest_embedding(user_id, interest)
                    logger.info(f"用户 {user_id} 兴趣embedding初始化成功")
                except Exception as e:
                    logger.warning(f"初始化用户兴趣embedding时出错: {str(e)}")
                    # 不影响注册流程
            
            return {
                'message': '用户注册成功',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'user_id': user_id,
                    'username': username,
                    'interest': interest
                }
            }
            
        except Exception as e:
            logger.error(f"用户注册失败: {str(e)}", exc_info=True)
            return {
                'message': f'用户注册失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500


@users_ns.route('/<int:user_id>')
class UserDetail(Resource):
    @users_ns.doc('get_user')
    @users_ns.marshal_with(response_model)
    def get(self, user_id):
        """
        获取用户信息
        
        根据 user_id 获取用户详情（不包含密码）
        """
        try:
            db = DbManager()
            user = db.query_one(
                """
                SELECT user_id, username, interest 
                FROM users 
                WHERE user_id = %s
                """,
                (user_id,)
            )
            
            if not user:
                return {
                    'message': f'用户不存在 (user_id={user_id})',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 404
            
            return {
                'message': '获取用户信息成功',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'user': user
                }
            }
            
        except Exception as e:
            logger.error(f"获取用户信息失败: {str(e)}", exc_info=True)
            return {
                'message': f'获取用户信息失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500


@users_ns.route('/<int:user_id>/interest')
class UserInterest(Resource):
    @users_ns.doc('update_interest')
    @users_ns.expect(user_update_interest_model)
    @users_ns.marshal_with(response_model)
    def put(self, user_id):
        """
        更新用户兴趣
        
        修改用户的研究兴趣领域
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
            
            interest = data.get('interest')
            
            if not interest:
                return {
                    'message': '兴趣字段不能为空',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 400
            
            db = DbManager()
            
            # 检查用户是否存在
            user = db.query_one(
                "SELECT user_id FROM users WHERE user_id = %s",
                (user_id,)
            )
            
            if not user:
                return {
                    'message': f'用户不存在 (user_id={user_id})',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 404
            
            # 更新兴趣
            result = db.execute(
                "UPDATE users SET interest = %s WHERE user_id = %s",
                (interest, user_id)
            )
            
            logger.info(f"用户 {user_id} 兴趣更新成功: {interest}")
            
            # 触发更新兴趣的embedding（异步处理，不阻塞主流程）
            try:
                orchestrator = RecommendationOrchestrator()
                embedding_updated = orchestrator.update_user_interest_embedding(user_id, interest)
                if embedding_updated:
                    logger.info(f"用户 {user_id} 兴趣embedding更新成功")
                else:
                    logger.warning(f"用户 {user_id} 兴趣embedding更新失败（可能是配额限制，稍后会自动重试）")
                    # 注意：即使embedding更新失败，兴趣文本已保存，可以在后台任务中重试
            except RuntimeError as e:
                error_msg = str(e)
                # 配额错误不影响主流程，但记录警告
                if "quota" in error_msg.lower() or "429" in error_msg or "rate limit" in error_msg.lower():
                    logger.warning(f"用户 {user_id} 兴趣embedding更新失败（API配额限制）: {error_msg}")
                else:
                    logger.error(f"更新用户兴趣embedding时出错: {error_msg}", exc_info=True)
            except Exception as e:
                logger.error(f"更新用户兴趣embedding时出错: {str(e)}", exc_info=True)
                # 不影响主流程，继续返回成功
            
            return {
                'message': '用户兴趣更新成功',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'user_id': user_id,
                    'interest': interest,
                    'updated_rows': result['rowcount']
                }
            }
            
        except Exception as e:
            logger.error(f"更新用户兴趣失败: {str(e)}", exc_info=True)
            return {
                'message': f'更新用户兴趣失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500
    
    @users_ns.doc('get_interest')
    @users_ns.marshal_with(response_model)
    def get(self, user_id):
        """
        获取用户兴趣
        
        查询用户的研究兴趣领域
        """
        try:
            db = DbManager()
            user = db.query_one(
                "SELECT user_id, username, interest FROM users WHERE user_id = %s",
                (user_id,)
            )
            
            if not user:
                return {
                    'message': f'用户不存在 (user_id={user_id})',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 404
            
            return {
                'message': '获取用户兴趣成功',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'user_id': user['user_id'],
                    'username': user['username'],
                    'interest': user['interest']
                }
            }
            
        except Exception as e:
            logger.error(f"获取用户兴趣失败: {str(e)}", exc_info=True)
            return {
                'message': f'获取用户兴趣失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500


@users_ns.route('/list')
class UserList(Resource):
    @users_ns.doc('list_users')
    @users_ns.marshal_with(response_model)
    def get(self):
        """
        获取用户列表
        
        支持分页查询（不返回密码）
        """
        try:
            # 获取查询参数
            page = int(request.args.get('page', 1))
            page_size = int(request.args.get('page_size', 20))
            
            # 计算偏移量
            offset = (page - 1) * page_size
            
            db = DbManager()
            
            # 查询用户列表（不包含密码）
            users = db.query_all(
                """
                SELECT user_id, username, interest
                FROM users
                ORDER BY user_id DESC
                LIMIT %s OFFSET %s
                """,
                (page_size, offset)
            )
            
            # 获取总数
            total = db.query_one("SELECT COUNT(*) as count FROM users")
            total_count = total['count'] if total else 0
            total_pages = (total_count + page_size - 1) // page_size
            
            return {
                'message': '获取用户列表成功',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'users': users,
                    'pagination': {
                        'page': page,
                        'page_size': page_size,
                        'total': total_count,
                        'total_pages': total_pages
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"获取用户列表失败: {str(e)}", exc_info=True)
            return {
                'message': f'获取用户列表失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500


@users_ns.route('/<int:user_id>')
class UserDelete(Resource):
    @users_ns.doc('delete_user')
    @users_ns.marshal_with(response_model)
    def delete(self, user_id):
        """
        删除用户
        
        删除指定用户（及其相关推荐）
        """
        try:
            db = DbManager()
            
            # 检查用户是否存在
            user = db.query_one(
                "SELECT user_id FROM users WHERE user_id = %s",
                (user_id,)
            )
            
            if not user:
                return {
                    'message': f'用户不存在 (user_id={user_id})',
                    'status': 'error',
                    'timestamp': datetime.now().isoformat(),
                    'data': None
                }, 404
            
            # 删除用户（由于外键约束，相关推荐会级联删除）
            result = db.execute(
                "DELETE FROM users WHERE user_id = %s",
                (user_id,)
            )
            
            logger.info(f"用户 {user_id} 已删除")
            
            return {
                'message': '用户删除成功',
                'status': 'success',
                'timestamp': datetime.now().isoformat(),
                'data': {
                    'deleted_user_id': user_id,
                    'deleted_rows': result['rowcount']
                }
            }
            
        except Exception as e:
            logger.error(f"删除用户失败: {str(e)}", exc_info=True)
            return {
                'message': f'删除用户失败: {str(e)}',
                'status': 'error',
                'timestamp': datetime.now().isoformat(),
                'data': None
            }, 500
