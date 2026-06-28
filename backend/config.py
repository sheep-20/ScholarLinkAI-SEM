import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    """应用配置类"""
    
    # 服务器配置
    PORT = int(os.getenv('PORT', 3001))
    HOST = os.getenv('HOST', '0.0.0.0')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    ENV = os.getenv('ENV', 'development')
    
    # 数据库配置 (后续添加)
    DATABASE_HOST = os.getenv('DATABASE_HOST', 'localhost')
    DATABASE_PORT = int(os.getenv('DATABASE_PORT', 5432))
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'scholarlink_ai')
    DATABASE_USER = os.getenv('DATABASE_USER', 'your_username')
    DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD', 'your_password')
    
    # JWT配置 (后续添加)
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your_jwt_secret_key')
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 86400))  # 24小时
    
    # API配置
    API_TITLE = 'ScholarLink AI API'
    API_VERSION = '1.0.0'
    API_DESCRIPTION = 'ScholarLink AI 后端服务 API'
