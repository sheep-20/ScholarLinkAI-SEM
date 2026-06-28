"""
Chat Service - AI 对话服务
处理与AI的对话逻辑，使用论文摘要作为系统提示词
"""

import os
import yaml
from typing import Dict, List, Optional
from openai import OpenAI
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def load_config():
    """从 config.yaml 加载配置"""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


class ChatService:
    """AI 对话服务类"""

    def __init__(self):
        config = load_config()
        openai_config = config.get("openai", {})

        self.client = OpenAI(
            base_url=openai_config.get("base_url", "https://api.deepseek.com"),
            api_key=openai_config.get("api_key"),
        )
        self.chat_model = openai_config.get("chat_model", "deepseek-chat")
        self.timeout = openai_config.get("timeout", 60)

    def create_system_prompt(self, paper_abstract: str) -> str:
        """根据论文摘要创建系统提示词"""
        return f"""你是一个专业的学术助手，专门帮助用户理解这篇论文。

论文摘要：
{paper_abstract}

请基于这篇论文的内容回答用户的问题。你应该：
1. 提供准确、清晰的解释
2. 使用通俗易懂的语言
3. 结合论文的具体内容进行解答
4. 如果问题超出论文范围，诚实地说明
5. 保持专业和友好的态度

如果用户问的问题与这篇论文无关，请礼貌地提醒他们这个问题超出了当前论文的讨论范围。"""

    def chat_with_ai(self, user_message: str, paper_abstract: str, conversation_history: Optional[List[Dict]] = None) -> str:
        """
        与AI进行对话

        Args:
            user_message: 用户消息
            paper_abstract: 论文摘要
            conversation_history: 对话历史（可选）

        Returns:
            AI回复内容
        """
        try:
            # 构建消息列表
            messages = [
                {"role": "system", "content": self.create_system_prompt(paper_abstract)}
            ]

            # 添加历史对话
            if conversation_history:
                for chat in conversation_history[-10:]:  # 只保留最近10轮对话
                    messages.append({"role": "user", "content": chat["user_message"]})
                    messages.append({"role": "assistant", "content": chat["ai_response"]})

            # 添加当前用户消息
            messages.append({"role": "user", "content": user_message})

            # 调用AI API
            response = self.client.chat.completions.create(
                model=self.chat_model,
                messages=messages,
                max_tokens=2000,
                temperature=0.7,
                timeout=self.timeout
            )

            ai_response = response.choices[0].message.content
            return ai_response

        except Exception as e:
            logger.error(f"AI对话失败: {str(e)}")
            return f"抱歉，我遇到了一些问题：{str(e)}。请稍后重试。"


# 全局单例实例
_chat_service_instance = None


def get_chat_service() -> ChatService:
    """获取ChatService单例实例"""
    global _chat_service_instance
    if _chat_service_instance is None:
        _chat_service_instance = ChatService()
    return _chat_service_instance
