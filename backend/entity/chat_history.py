"""
Chat History Entity - 聊天历史实体类
匹配数据库结构：id, recommendation_id, user_message, ai_response, created_at
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class ChatHistory(Base):
    __tablename__ = 'chat_history'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='聊天记录ID')
    recommendation_id = Column(Integer, ForeignKey('recommendations.id'), nullable=False, comment='推荐记录ID')
    user_message = Column(Text, nullable=False, comment='用户消息')
    ai_response = Column(Text, nullable=False, comment='AI回复')
    created_at = Column(DateTime, default=datetime.utcnow, comment='创建时间')

    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'recommendation_id': self.recommendation_id,
            'user_message': self.user_message,
            'ai_response': self.ai_response,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
