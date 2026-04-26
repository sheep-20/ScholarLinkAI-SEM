"""
推荐Orchestrator - 协调embedding服务和数据库，实现论文推荐功能
"""
from __future__ import annotations

import logging
import os
from typing import List, Dict, Any, Optional
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed

from service.dbmanager import DbManager
from service.openrouter_embedding import OpenRouterEmbedding
from service.retry_utils import retry_on_quota_error
from service.Generate_blogs import BlogGenerator

logger = logging.getLogger(__name__)


def _get_default_embedding_provider() -> str:
    """从config.yaml或环境变量读取默认的embedding provider"""
    # 1. 环境变量优先
    provider = os.getenv("EMBEDDING_PROVIDER", "").strip()
    if provider:
        return provider.lower()
    
    # 2. 从config.yaml读取
    try:
        import yaml
        base = os.path.dirname(__file__)
        for root in [
            os.path.abspath(os.path.join(base, "..", "..")),
            os.path.abspath(os.path.join(base, "..")),
            os.path.abspath(os.path.join(base, ".")),
        ]:
            cfg = os.path.join(root, "config.yaml")
            if os.path.isfile(cfg):
                with open(cfg, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    embedding_config = data.get("embedding") or {}
                    if isinstance(embedding_config, dict):
                        provider = embedding_config.get("provider", "").strip()
                        if provider:
                            return provider.lower()
                break
    except Exception as e:
        logger.debug(f"读取config.yaml失败: {e}")
    
    # 3. 默认值
    return "openrouter"


class RecommendationOrchestrator:
    """推荐业务流程编排器"""
    
    def __init__(self, embedding_provider: Optional[str] = None):
        """
        初始化推荐orchestrator
        
        Args:
            embedding_provider: embedding服务提供商，如果为None则从config.yaml读取，默认"openrouter"
        """
        self.db = DbManager()
        if embedding_provider is None:
            embedding_provider = _get_default_embedding_provider()
        self.embedding_service = OpenRouterEmbedding()
        logger.info(f"RecommendationOrchestrator初始化完成，使用{embedding_provider} embedding服务")
    
    @retry_on_quota_error(max_retries=2, initial_delay=5.0)
    def update_user_interest_embedding(self, user_id: int, interest: str) -> bool:
        """
        更新用户兴趣的embedding向量

        Args:
            user_id: 用户ID
            interest: 用户兴趣文本

        Returns:
            是否成功更新
        """
        try:
            # 检查用户是否存在
            user = self.db.query_one(
                "SELECT user_id FROM users WHERE user_id = %s",
                (user_id,)
            )
            if not user:
                logger.error(f"用户不存在: user_id={user_id}")
                return False

            # 生成兴趣的embedding向量
            if not interest or not interest.strip():
                logger.warning(f"用户{user_id}的兴趣为空，跳过embedding更新")
                return False

            try:
                embedding = self.embedding_service.embed_text(interest.strip(), normalize=True)
            except RuntimeError as e:
                error_msg = str(e)
                # 如果是配额错误，记录警告但继续（允许稍后重试）
                if "quota" in error_msg.lower() or "429" in error_msg or "rate limit" in error_msg.lower():
                    logger.warning(f"用户{user_id}的兴趣embedding生成失败（配额限制），稍后可以重试: {error_msg}")
                    return False
                # 其他错误直接抛出
                raise

            # 将向量转换为字符串存储（JSON格式）
            import json
            embedding_str = json.dumps(embedding)

            # 更新interest_embeddings表
            self.db.execute(
                "INSERT INTO interest_embeddings (user_id, embedding) VALUES (%s, %s) ON DUPLICATE KEY UPDATE embedding = VALUES(embedding)",
                (user_id, embedding_str)
            )

            logger.info(f"用户{user_id}的兴趣embedding更新成功")
            return True

        except Exception as e:
            logger.error(f"更新用户兴趣embedding失败: {str(e)}", exc_info=True)
            return False
    
    def get_user_interest_embedding(self, user_id: int) -> Optional[List[float]]:
        """
        获取用户兴趣的embedding向量

        Args:
            user_id: 用户ID

        Returns:
            embedding向量，如果不存在则返回None
        """
        try:
            result = self.db.query_one(
                "SELECT embedding FROM interest_embeddings WHERE user_id = %s",
                (user_id,)
            )
            if not result or not result.get('embedding'):
                return None

            import json
            embedding_str = result['embedding']
            if isinstance(embedding_str, str):
                return json.loads(embedding_str)
            return None

        except Exception as e:
            logger.error(f"获取用户兴趣embedding失败: {str(e)}", exc_info=True)
            return None
    
    def compute_paper_embedding(self, paper_id: int) -> Optional[List[float]]:
        """
        计算论文的embedding向量（基于标题和摘要）
        
        Args:
            paper_id: 论文ID
            
        Returns:
            embedding向量
        """
        try:
            paper = self.db.query_one(
                "SELECT title, abstract FROM papers WHERE paper_id = %s",
                (paper_id,)
            )
            if not paper:
                return None
            
            # 组合标题和摘要
            text = f"{paper.get('title', '')} {paper.get('abstract', '')}"
            text = text.strip()
            if not text:
                return None
            
            # 生成embedding
            embedding = self.embedding_service.embed_text(text, normalize=True)
            return embedding
            
        except Exception as e:
            logger.error(f"计算论文embedding失败: {str(e)}", exc_info=True)
            return None
    
    def get_paper_embedding(self, paper_id: int) -> Optional[List[float]]:
        """
        从paper_embeddings表获取论文的embedding向量

        Args:
            paper_id: 论文ID

        Returns:
            embedding向量，如果不存在则返回None
        """
        try:
            result = self.db.query_one(
                "SELECT embedding FROM paper_embeddings WHERE paper_id = %s",
                (paper_id,)
            )
            if not result or not result.get('embedding'):
                return None

            import json
            embedding_str = result['embedding']
            if isinstance(embedding_str, str):
                return json.loads(embedding_str)
            return None

        except Exception as e:
            logger.error(f"获取论文embedding失败: {str(e)}", exc_info=True)
            return None

    def recommend_papers(self, user_id: int, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        为用户推荐论文（基于预计算的embeddings）

        Args:
            user_id: 用户ID
            top_k: 返回前k个推荐结果

        Returns:
            推荐的论文列表，包含相似度分数
        """
        try:
            # 获取用户兴趣embedding
            user_embedding = self.get_user_interest_embedding(user_id)
            if not user_embedding:
                # 如果没有embedding，尝试从兴趣文本生成
                user = self.db.query_one(
                    "SELECT interest FROM users WHERE user_id = %s",
                    (user_id,)
                )
                if user and user.get('interest'):
                    self.update_user_interest_embedding(user_id, user['interest'])
                    user_embedding = self.get_user_interest_embedding(user_id)

            if not user_embedding:
                logger.warning(f"用户{user_id}没有兴趣embedding，无法推荐")
                return []

            # 获取所有有embedding的论文
            paper_embeddings = self.db.query_all(
                """
                SELECT pe.paper_id, pe.embedding, p.title, p.abstract, p.author, p.pdf_url
                FROM paper_embeddings pe
                JOIN papers p ON pe.paper_id = p.paper_id
                """
            )

            if not paper_embeddings:
                logger.info("没有预计算的论文embeddings，尝试实时计算")
                # 如果没有预计算的embeddings，回退到实时计算
                return self._recommend_with_live_computation(user_id, top_k)

            # 计算每篇论文的相似度
            recommendations = []
            user_vec = np.array(user_embedding)

            for paper_data in paper_embeddings:
                paper_id = paper_data['paper_id']

                # 解析论文embedding
                try:
                    import json
                    embedding_str = paper_data['embedding']
                    if isinstance(embedding_str, str):
                        paper_embedding = json.loads(embedding_str)
                    else:
                        continue
                except Exception as e:
                    logger.warning(f"解析论文{paper_id}的embedding失败: {e}")
                    continue

                # 计算余弦相似度
                paper_vec = np.array(paper_embedding)
                # 确保向量长度一致
                if len(user_vec) != len(paper_vec):
                    logger.warning(f"向量维度不匹配: user={len(user_vec)}, paper={len(paper_vec)}")
                    continue
                similarity = float(np.dot(user_vec, paper_vec))

                recommendations.append({
                    'paper_id': paper_id,
                    'title': paper_data['title'],
                    'abstract': paper_data['abstract'],
                    'author': paper_data['author'],
                    'pdf_url': paper_data['pdf_url'],
                    'similarity': similarity
                })

            # 按相似度排序，返回top_k
            recommendations.sort(key=lambda x: x['similarity'], reverse=True)
            return recommendations[:top_k]

        except Exception as e:
            logger.error(f"推荐论文失败: {str(e)}", exc_info=True)
            return []

    def _recommend_with_live_computation(self, user_id: int, top_k: int = 10) -> List[Dict[str, Any]]:
        """
        备用推荐方法：实时计算论文embeddings（性能较慢）

        Args:
            user_id: 用户ID
            top_k: 返回前k个推荐结果

        Returns:
            推荐的论文列表，包含相似度分数
        """
        try:
            # 获取用户兴趣embedding
            user_embedding = self.get_user_interest_embedding(user_id)
            if not user_embedding:
                logger.warning(f"用户{user_id}没有兴趣embedding，无法推荐")
                return []

            # 获取所有论文
            papers = self.db.query_all(
                "SELECT paper_id, title, abstract, author, pdf_url FROM papers"
            )

            if not papers:
                return []

            # 计算每篇论文的相似度
            recommendations = []
            user_vec = np.array(user_embedding)

            for paper in papers:
                paper_id = paper['paper_id']

                # 计算论文embedding
                paper_embedding = self.compute_paper_embedding(paper_id)
                if not paper_embedding:
                    continue

                # 计算余弦相似度
                paper_vec = np.array(paper_embedding)
                # 确保向量长度一致
                if len(user_vec) != len(paper_vec):
                    logger.warning(f"向量维度不匹配: user={len(user_vec)}, paper={len(paper_vec)}")
                    continue
                similarity = float(np.dot(user_vec, paper_vec))

                recommendations.append({
                    'paper_id': paper_id,
                    'title': paper['title'],
                    'abstract': paper['abstract'],
                    'author': paper['author'],
                    'pdf_url': paper['pdf_url'],
                    'similarity': similarity
                })

            # 按相似度排序，返回top_k
            recommendations.sort(key=lambda x: x['similarity'], reverse=True)
            return recommendations[:top_k]

        except Exception as e:
            logger.error(f"实时计算推荐失败: {str(e)}", exc_info=True)
            return []

    @retry_on_quota_error(max_retries=2, initial_delay=5.0)
    def update_paper_embedding(self, paper_id: int) -> bool:
        """
        更新论文的embedding向量

        Args:
            paper_id: 论文ID

        Returns:
            是否成功更新
        """
        try:
            # 检查论文是否存在
            paper = self.db.query_one(
                "SELECT title, abstract FROM papers WHERE paper_id = %s",
                (paper_id,)
            )
            if not paper:
                logger.error(f"论文不存在: paper_id={paper_id}")
                return False

            # 计算embedding
            text = f"{paper.get('title', '')} {paper.get('abstract', '')}".strip()
            if not text:
                logger.warning(f"论文{paper_id}没有有效文本内容")
                return False

            try:
                embedding = self.embedding_service.embed_text(text, normalize=True)
            except RuntimeError as e:
                error_msg = str(e)
                if "quota" in error_msg.lower() or "429" in error_msg or "rate limit" in error_msg.lower():
                    logger.warning(f"论文{paper_id}的embedding生成失败（配额限制），稍后可以重试: {error_msg}")
                    return False
                raise

            # 将向量转换为字符串存储
            import json
            embedding_str = json.dumps(embedding)

            # 更新paper_embeddings表
            self.db.execute(
                "INSERT INTO paper_embeddings (paper_id, embedding) VALUES (%s, %s) ON DUPLICATE KEY UPDATE embedding = VALUES(embedding)",
                (paper_id, embedding_str)
            )

            logger.info(f"论文{paper_id}的embedding更新成功")
            return True

        except Exception as e:
            logger.error(f"更新论文embedding失败: {str(e)}", exc_info=True)
            return False

    def update_all_paper_embeddings(self, batch_size: int = 10) -> int:
        """
        批量更新所有论文的embeddings

        Args:
            batch_size: 每批处理的论文数量

        Returns:
            成功更新的论文数量
        """
        try:
            # 获取所有论文
            papers = self.db.query_all("SELECT paper_id FROM papers")
            if not papers:
                logger.info("没有论文需要更新embedding")
                return 0

            success_count = 0
            total_count = len(papers)

            logger.info(f"开始批量更新{total_count}篇论文的embeddings")

            for i in range(0, total_count, batch_size):
                batch = papers[i:i + batch_size]
                batch_success = 0

                for paper in batch:
                    if self.update_paper_embedding(paper['paper_id']):
                        batch_success += 1

                success_count += batch_success
                logger.info(f"已处理 {min(i + batch_size, total_count)}/{total_count} 篇论文，当前批次成功: {batch_success}/{len(batch)}")

            logger.info(f"批量更新完成，成功: {success_count}/{total_count}")
            return success_count

        except Exception as e:
            logger.error(f"批量更新论文embeddings失败: {str(e)}", exc_info=True)
            return 0

    def generate_blogs(
        self,
        topk: int = 5,
        user_id: Optional[int] = None,
        max_workers: int = 4,
    ) -> Dict[str, Any]:
        """
        生成指定数量的论文博客，并按需保存到 recommendations 表。

        Args:
            topk: 生成博客的数量，默认5，最大10。
            user_id: 若提供，则将生成结果保存到 recommendations.user_id 关联的记录。
            max_workers: 并发工作线程数（默认4），控制同时生成的博客数量。

        Returns:
            {
                "blogs": [...],              # 已生成的博客列表
                "requested": topk,           # 请求的数量
                "generated": len(blogs),     # 实际生成的数量
                "saved": saved_count,        # 成功写入 recommendations 的数量
                "save_failed": failed_save_count  # 保存失败的数量
            }
        """
        try:
            # 验证topk参数
            if not isinstance(topk, int) or topk <= 0:
                logger.error(f"无效的topk参数: {topk}")
                return {"blogs": [], "requested": topk, "generated": 0, "saved": 0, "save_failed": 0}
            if topk > 10:
                logger.warning(f"topk参数超过最大值10，已调整为10")
                topk = 10

            logger.info(f"开始生成 {topk} 篇博客")

            # 获取最新的论文（按paper_id降序排序）
            papers = self.db.query_all(
                """
                SELECT paper_id, title, pdf_url
                FROM papers
                WHERE pdf_url IS NOT NULL AND pdf_url != ''
                ORDER BY paper_id DESC
                LIMIT %s
                """,
                (topk,)
            )

            if not papers:
                logger.warning("没有找到有效的论文数据")
                return {"blogs": [], "requested": topk, "generated": 0, "saved": 0, "save_failed": 0}

            logger.info(f"找到 {len(papers)} 篇论文，开始生成博客")

            # 初始化博客生成器（线程安全：无共享状态，仅使用 client）
            blog_generator = BlogGenerator()

            blogs = []
            success_count = 0
            failed_count = 0
            saved_count = 0
            failed_save_count = 0

            def _process_one(paper: Dict[str, Any]) -> Dict[str, Any]:
                paper_id = paper['paper_id']
                title = paper['title']
                pdf_url = paper['pdf_url']

                try:
                    logger.info(f"正在为论文生成博客: {title[:50]}...")
                    blog_content = blog_generator.generate_from_pdf_url(pdf_url)
                    result = {
                        'paper_id': paper_id,
                        'title': title,
                        'pdf_url': pdf_url,
                        'blog_content': blog_content,
                        'status': 'ok'
                    }

                    if user_id is not None:
                        try:
                            self.db.execute(
                                """
                                INSERT INTO recommendations (user_id, paper_id, blog)
                                VALUES (%s, %s, %s)
                                ON DUPLICATE KEY UPDATE blog = VALUES(blog), created_at = CURRENT_TIMESTAMP
                                """,
                                (user_id, paper_id, blog_content)
                            )
                            result['saved'] = True
                        except Exception as db_err:
                            logger.error(
                                f"保存博客到 recommendations 失败: user_id={user_id}, paper_id={paper_id}, err={db_err}"
                            )
                            result['saved'] = False
                            result['save_err'] = str(db_err)
                    return result
                except Exception as e:
                    logger.error(f"为论文 {title[:50]} 生成博客失败: {str(e)}")
                    return {
                        'paper_id': paper_id,
                        'title': title,
                        'pdf_url': pdf_url,
                        'status': 'fail',
                        'err': str(e),
                    }

            # 并发生成
            with ThreadPoolExecutor(max_workers=max_workers or 1) as executor:
                future_map = {executor.submit(_process_one, p): p for p in papers}
                for fut in as_completed(future_map):
                    res = fut.result()
                    if res.get('status') == 'ok':
                        blogs.append({
                            'paper_id': res['paper_id'],
                            'title': res['title'],
                            'pdf_url': res['pdf_url'],
                            'blog_content': res['blog_content']
                        })
                        success_count += 1
                        if res.get('saved'):
                            saved_count += 1
                        elif res.get('saved') is False:
                            failed_save_count += 1
                    else:
                        failed_count += 1

            logger.info(f"博客生成完成: 成功 {success_count} 篇，失败 {failed_count} 篇")

            blogs = blogs[:topk]  # 确保返回的数量不超过topk

            return {
                "blogs": blogs,
                "requested": topk,
                "generated": len(blogs),
                "saved": saved_count,
                "save_failed": failed_save_count
            }

        except Exception as e:
            logger.error(f"生成博客失败: {str(e)}", exc_info=True)
            return {"blogs": [], "requested": topk, "generated": 0, "saved": 0, "save_failed": 0}


    def generate_blogs_for_all_users(
        self,
        topk_per_user: int = 3,
        max_workers: int = 4,
    ) -> Dict[str, Any]:
        """
        为所有有兴趣embedding的用户生成推荐博客并写入 recommendations 表。

        流程：
        1) 找出有兴趣 embedding 的用户
        2) 为每个用户计算前 topk_per_user 篇推荐论文
        3) 合并所有用户的论文需求为去重集合，每篇博客只生成一次
        4) 将生成结果写入 recommendations（ON DUPLICATE KEY UPDATE）
        """
        try:
            users = self.db.query_all(
                """
                SELECT u.user_id
                FROM users u
                JOIN interest_embeddings ie ON u.user_id = ie.user_id
                """
            )
            if not users:
                logger.warning("没有找到带兴趣embedding的用户")
                return {
                    "message": "no users with embeddings",
                    "users": 0,
                    "papers": 0,
                    "generated": 0,
                    "saved_pairs": 0,
                    "failed_generate": 0,
                    "failed_save": 0,
                }

            user_reco: Dict[int, List[int]] = {}
            paper_map: Dict[int, Dict[str, Any]] = {}

            for u in users:
                uid = u["user_id"]
                recs = self.recommend_papers(uid, top_k=topk_per_user)
                paper_ids: List[int] = []
                for r in recs:
                    pid = r.get("paper_id")
                    pdf_url = r.get("pdf_url")
                    title = r.get("title")
                    if not pid or not pdf_url:
                        continue
                    if pid not in paper_map:
                        paper_map[pid] = {
                            "paper_id": pid,
                            "title": title,
                            "pdf_url": pdf_url,
                        }
                    paper_ids.append(pid)
                user_reco[uid] = paper_ids

            if not paper_map:
                logger.warning("没有可生成博客的论文（可能缺少pdf_url）")
                return {
                    "message": "no papers to generate",
                    "users": len(users),
                    "papers": 0,
                    "generated": 0,
                    "saved_pairs": 0,
                    "failed_generate": 0,
                    "failed_save": 0,
                }

            logger.info(
                f"为 {len(users)} 位用户准备生成博客，独立论文数 {len(paper_map)}，每用户topk={topk_per_user}"
            )

            blog_generator = BlogGenerator()
            blog_map: Dict[int, str] = {}
            failed_generate = 0

            def _gen_one(paper: Dict[str, Any]) -> Dict[str, Any]:
                pid = paper["paper_id"]
                title = paper.get("title", "")
                pdf_url = paper.get("pdf_url", "")
                try:
                    content = blog_generator.generate_from_pdf_url(pdf_url)
                    return {"paper_id": pid, "content": content, "status": "ok"}
                except Exception as e:
                    logger.error(f"生成论文{pid}:{title[:40]}的博客失败: {e}")
                    return {"paper_id": pid, "status": "fail", "err": str(e)}

            with ThreadPoolExecutor(max_workers=max_workers or 1) as executor:
                futures = {executor.submit(_gen_one, p): p for p in paper_map.values()}
                for fut in as_completed(futures):
                    res = fut.result()
                    if res.get("status") == "ok":
                        blog_map[res["paper_id"]] = res["content"]
                    else:
                        failed_generate += 1

            saved_pairs = 0
            failed_save = 0
            for uid, pids in user_reco.items():
                for pid in pids:
                    content = blog_map.get(pid)
                    if not content:
                        continue
                    try:
                        self.db.execute(
                            """
                            INSERT INTO recommendations (user_id, paper_id, blog)
                            VALUES (%s, %s, %s)
                            ON DUPLICATE KEY UPDATE blog = VALUES(blog), created_at = CURRENT_TIMESTAMP
                            """,
                            (uid, pid, content),
                        )
                        saved_pairs += 1
                    except Exception as e:
                        failed_save += 1
                        logger.error(f"保存 user_id={uid}, paper_id={pid} 到 recommendations 失败: {e}")

            return {
                "message": "ok",
                "users": len(users),
                "papers": len(paper_map),
                "generated": len(blog_map),
                "saved_pairs": saved_pairs,
                "failed_generate": failed_generate,
                "failed_save": failed_save,
            }

        except Exception as e:
            logger.error(f"为所有用户生成博客失败: {e}", exc_info=True)
            return {
                "message": f"error: {e}",
                "users": 0,
                "papers": 0,
                "generated": 0,
                "saved_pairs": 0,
                "failed_generate": 0,
                "failed_save": 0,
            }

    def list_recommendations(
        self,
        user_id: Optional[int] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        获取推荐博客列表，可按用户过滤。
        """
        try:
            params: List[Any] = []
            where = ""
            if user_id is not None:
                where = "WHERE r.user_id = %s"
                params.append(user_id)

            sql = f"""
                SELECT
                    r.id,
                    r.user_id,
                    r.paper_id,
                    r.blog,
                    r.created_at,
                    p.title,
                    p.abstract,
                    p.author,
                    p.pdf_url,
                    pl.user_id AS liked_user
                FROM recommendations r
                JOIN papers p ON r.paper_id = p.paper_id
                LEFT JOIN paper_liked pl
                  ON pl.paper_id = r.paper_id
                 AND (%s IS NOT NULL AND pl.user_id = %s)
                {where}
                ORDER BY r.created_at DESC
                LIMIT %s
            """
            # need user_id twice for join placeholder even if None
            params_with_like = []
            params_with_like.extend(params if user_id is None else params)  # params already contains user_id if set
            params_with_like.extend([user_id, user_id])
            params_with_like.append(limit)
            rows = self.db.query_all(sql, tuple(params_with_like))
            # 转换 datetime 为字符串，避免 JSON 序列化报错
            for r in rows:
                ts = r.get("created_at")
                if ts is not None:
                    r["created_at"] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
                r["liked"] = bool(r.get("liked_user"))
                r.pop("liked_user", None)
            return rows
        except Exception as e:
            logger.error(f"获取recommendations失败: {e}", exc_info=True)
            return []

    # --- 点赞/收藏 ---
    def like_paper(self, user_id: int, paper_id: int) -> bool:
        try:
            # 校验用户、论文是否存在，避免外键错误
            user_exists = self.db.query_one("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            paper_exists = self.db.query_one("SELECT paper_id FROM papers WHERE paper_id = %s", (paper_id,))
            if not user_exists or not paper_exists:
                logger.error(f"收藏失败: user或paper不存在 user_id={user_id}, paper_id={paper_id}")
                return False

            self.db.execute(
                """
                INSERT INTO paper_liked (user_id, paper_id)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE created_at = CURRENT_TIMESTAMP
                """,
                (user_id, paper_id),
            )
            return True
        except Exception as e:
            logger.error(f"收藏失败 user_id={user_id}, paper_id={paper_id}: {e}")
            return False

    def unlike_paper(self, user_id: int, paper_id: int) -> bool:
        try:
            # 同样先校验存在性，保持一致
            user_exists = self.db.query_one("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
            paper_exists = self.db.query_one("SELECT paper_id FROM papers WHERE paper_id = %s", (paper_id,))
            if not user_exists or not paper_exists:
                logger.error(f"取消收藏失败: user或paper不存在 user_id={user_id}, paper_id={paper_id}")
                return False

            self.db.execute(
                "DELETE FROM paper_liked WHERE user_id = %s AND paper_id = %s",
                (user_id, paper_id),
            )
            return True
        except Exception as e:
            logger.error(f"取消收藏失败 user_id={user_id}, paper_id={paper_id}: {e}")
            return False

    def list_liked(
        self,
        user_id: int,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        获取指定用户的收藏列表，附带论文信息与可用的博客内容（若存在）。
        """
        try:
            sql = """
                SELECT
                    pl.user_id,
                    pl.paper_id,
                    pl.created_at AS liked_at,
                    p.title,
                    p.abstract,
                    p.author,
                    p.pdf_url,
                    r.blog,
                    r.created_at AS blog_created_at
                FROM paper_liked pl
                JOIN papers p ON pl.paper_id = p.paper_id
                LEFT JOIN recommendations r
                  ON r.paper_id = pl.paper_id
                 AND r.user_id = pl.user_id
                WHERE pl.user_id = %s
                ORDER BY pl.created_at DESC
                LIMIT %s
            """
            rows = self.db.query_all(sql, (user_id, limit))
            for r in rows:
                for k in ("liked_at", "blog_created_at"):
                    ts = r.get(k)
                    if ts is not None:
                        r[k] = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
                r["liked"] = True
            return rows
        except Exception as e:
            logger.error(f"获取收藏列表失败: {e}", exc_info=True)
            return []


__all__ = ["RecommendationOrchestrator"]
