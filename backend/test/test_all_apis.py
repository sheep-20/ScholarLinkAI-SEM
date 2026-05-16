"""
完整 API 功能测试脚本
测试所有 API 接口的功能
"""
from __future__ import annotations

import sys
import io
import requests
import json
import time
from typing import Dict, Any, Optional

# Windows编码修复
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

BASE_URL = "http://localhost:3001"

# 测试结果统计
test_results = {
    'passed': 0,
    'failed': 0,
    'skipped': 0,
    'total': 0
}

# 存储测试过程中产生的数据（如用户ID）
test_data: Dict[str, Any] = {}


def print_section(title: str):
    """打印章节标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_test(method: str, path: str, description: str):
    """打印测试信息"""
    print(f"\n[测试] {method} {path}")
    print(f"       {description}")


def test_endpoint(
    method: str,
    path: str,
    description: str,
    data: Optional[Dict] = None,
    expected_status: int = 200,
    save_result_key: Optional[str] = None
) -> bool:
    """测试单个端点"""
    test_results['total'] += 1
    
    try:
        url = f"{BASE_URL}{path}"
        print_test(method, path, description)
        
        if method == "GET":
            response = requests.get(url, timeout=10)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=10, headers={'Content-Type': 'application/json'})
        elif method == "PUT":
            response = requests.put(url, json=data, timeout=10, headers={'Content-Type': 'application/json'})
        elif method == "DELETE":
            response = requests.delete(url, timeout=10)
        else:
            print(f"       [SKIP] 不支持的请求方法: {method}")
            test_results['skipped'] += 1
            return False
        
        print(f"       状态码: {response.status_code} (期望: {expected_status})")
        
        if response.status_code == expected_status:
            try:
                result = response.json()
                print(f"       [✓] 测试通过")
                
                # 保存结果数据
                if save_result_key:
                    if isinstance(result, dict) and 'data' in result:
                        test_data[save_result_key] = result['data']
                    else:
                        test_data[save_result_key] = result
                
                # 显示关键信息
                if isinstance(result, dict):
                    if 'message' in result:
                        print(f"       消息: {result['message']}")
                    if 'data' in result and isinstance(result['data'], dict):
                        if 'user_id' in result['data']:
                            print(f"       用户ID: {result['data']['user_id']}")
                        if 'papers' in result['data']:
                            print(f"       论文数量: {len(result['data']['papers'])}")
                
                test_results['passed'] += 1
                return True
            except:
                print(f"       [✓] 测试通过（非JSON响应）")
                test_results['passed'] += 1
                return True
        else:
            print(f"       [✗] 测试失败")
            try:
                error = response.json()
                if 'message' in error:
                    print(f"       错误: {error['message']}")
                else:
                    print(f"       错误: {error}")
            except:
                print(f"       响应: {response.text[:200]}")
            test_results['failed'] += 1
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"       [✗] 无法连接到服务器")
        print(f"       请确保后端服务正在运行: python backend/app.py")
        test_results['failed'] += 1
        return False
    except Exception as e:
        print(f"       [✗] 测试失败: {e}")
        test_results['failed'] += 1
        return False


def main():
    print("=" * 70)
    print("  ScholarLink AI API 完整功能测试")
    print("=" * 70)
    print(f"\n测试目标: {BASE_URL}")
    print(f"开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Hello API 测试
    print_section("1. Hello API 测试")
    
    test_endpoint("GET", "/hello/", "获取 Hello World 消息")
    test_endpoint("GET", "/hello/test_user", "根据姓名获取 Hello 消息")
    test_endpoint("GET", "/hello/status", "获取 Hello API 状态")
    test_endpoint("POST", "/hello/post", "通过 POST 请求发送 Hello 消息", {
        "name": "测试用户",
        "message": "这是一条测试消息"
    })
    
    # 2. Papers API 测试
    print_section("2. Papers API 测试")
    
    # 先获取论文列表（可能为空）
    test_endpoint("GET", "/papers/list", "获取论文列表")
    test_endpoint("GET", "/papers/list?page=1&page_size=10", "获取论文列表（带分页）")
    
    # 抓取论文（可能需要一些时间）
    print("\n[提示] 抓取论文可能需要一些时间，请耐心等待...")
    test_endpoint("POST", "/papers/fetch", "抓取论文并保存到数据库", {
        "max_results": 5  # 只抓取5篇论文用于测试
    }, expected_status=200)
    
    # 等待一下让论文保存完成
    time.sleep(2)
    
    # 再次获取论文列表
    test_endpoint("GET", "/papers/list", "获取论文列表（抓取后）")
    
    # 获取论文详情（如果有论文的话）
    if test_data.get('papers') and len(test_data.get('papers', [])) > 0:
        paper_id = test_data['papers'][0].get('paper_id')
        if paper_id:
            test_endpoint("GET", f"/papers/{paper_id}", f"获取论文详情 (ID: {paper_id})")
    else:
        print("\n[跳过] 没有论文数据，跳过论文详情测试")
        test_results['skipped'] += 1
    
    # 3. Users API 测试
    print_section("3. Users API 测试")
    
    # 获取用户列表
    test_endpoint("GET", "/users/list", "获取用户列表")
    test_endpoint("GET", "/users/list?page=1&page_size=10", "获取用户列表（带分页）")
    
    # 用户注册
    test_username = f"test_user_{int(time.time())}"
    test_password = "test123456"
    test_interest = "Machine Learning, Deep Learning, Natural Language Processing"
    
    test_endpoint("POST", "/users/register", "用户注册", {
        "username": test_username,
        "password": test_password,
        "interest": test_interest
    }, save_result_key="registered_user")
    
    # 获取注册的用户ID
    user_id = None
    if test_data.get('registered_user') and 'user_id' in test_data['registered_user']:
        user_id = test_data['registered_user']['user_id']
        print(f"\n[信息] 注册的用户ID: {user_id}")
    
    # 用户登录
    test_endpoint("POST", "/users/login", "用户登录", {
        "username": test_username,
        "password": test_password
    }, save_result_key="login_token")
    
    # 获取用户兴趣
    if user_id:
        test_endpoint("GET", f"/users/{user_id}/interest", f"获取用户兴趣 (ID: {user_id})")
        
        # 更新用户兴趣
        new_interest = "Computer Vision, Reinforcement Learning"
        test_endpoint("PUT", f"/users/{user_id}/interest", f"更新用户兴趣 (ID: {user_id})", {
            "interest": new_interest
        })
        
        # 再次获取用户兴趣（验证更新）
        test_endpoint("GET", f"/users/{user_id}/interest", f"获取用户兴趣（更新后） (ID: {user_id})")
        
        # 删除用户（清理测试数据）
        print("\n[提示] 清理测试数据：删除测试用户...")
        test_endpoint("DELETE", f"/users/{user_id}", f"删除用户 (ID: {user_id})", expected_status=200)
    else:
        print("\n[跳过] 没有用户ID，跳过用户相关测试")
        test_results['skipped'] += 3
    
    # 4. 健康检查
    print_section("4. 健康检查")
    test_endpoint("GET", "/health", "健康检查")
    
    # 5. 根路径
    print_section("5. 根路径测试")
    test_endpoint("GET", "/", "获取 API 根路径信息")
    
    # 测试总结
    print_section("测试总结")
    print(f"总测试数: {test_results['total']}")
    print(f"✓ 通过: {test_results['passed']}")
    print(f"✗ 失败: {test_results['failed']}")
    print(f"⊘ 跳过: {test_results['skipped']}")
    print(f"\n通过率: {test_results['passed'] / test_results['total'] * 100:.1f}%")
    
    if test_results['failed'] == 0:
        print("\n🎉 所有测试通过！")
        return 0
    else:
        print(f"\n⚠️  有 {test_results['failed']} 个测试失败，请检查后端服务")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n[中断] 测试被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[错误] 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


