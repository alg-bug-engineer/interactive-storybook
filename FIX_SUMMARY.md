# ECS 部署错误修复说明

## 问题分析

在 ECS 上部署后，故事生成时出现两个关联错误：

### 错误 1: SOCKS 代理依赖缺失
```
Using SOCKS proxy, but the 'socksio' package is not installed. 
Make sure to install httpx using `pip install httpx[socks]`.
```

**原因**：
- ECS 环境中可能存在 SOCKS 代理配置（通过环境变量如 `HTTP_PROXY`, `HTTPS_PROXY` 等）
- `openai` 库使用 `httpx` 作为 HTTP 客户端
- 当检测到 SOCKS 代理时，`httpx` 需要 `socksio` 包来支持 SOCKS 协议
- 原始 `requirements.txt` 只安装了 `httpx`，没有安装 SOCKS 支持

### 错误 2: AsyncHttpxClientWrapper 属性错误
```
AttributeError: 'AsyncHttpxClientWrapper' object has no attribute '_mounts'
```

**原因**：
- 这是由错误 1 引发的连锁反应
- OpenAI 客户端因为代理问题初始化不完整
- 在关闭客户端时尝试访问不存在的 `_mounts` 属性导致错误
- 缺少正确的客户端生命周期管理（创建和关闭）

## 修复方案

### 1. 更新依赖 (`backend/requirements.txt`)

```diff
- httpx>=0.26.0
+ httpx[socks]>=0.26.0
```

这将安装：
- `httpx` 核心包
- `socksio` SOCKS 代理支持包
- 其他相关依赖

### 2. 优化 OpenAI 客户端管理 (`backend/app/services/llm_service.py`)

**新增功能**：
- ✅ 创建统一的客户端初始化函数 `_create_openai_client()`
- ✅ 配置合理的超时参数（连接 30s，读取 120s）
- ✅ 配置连接池限制，避免资源耗尽
- ✅ 在 `finally` 块中正确关闭客户端，防止资源泄漏
- ✅ 添加详细的日志记录，便于排查问题

**关键改进**：

```python
def _create_openai_client() -> AsyncOpenAI:
    """创建 OpenAI 客户端，带超时和代理配置"""
    timeout = httpx.Timeout(
        connect=30.0,  # 连接超时
        read=120.0,    # 读取超时（LLM 响应可能较慢）
        write=30.0,    # 写入超时
        pool=30.0      # 连接池超时
    )
    
    http_client = httpx.AsyncClient(
        timeout=timeout,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        follow_redirects=True,
    )
    
    return AsyncOpenAI(
        base_url=settings.llm_api_base.rstrip("/"),
        api_key=settings.llm_api_key,
        http_client=http_client,
    )
```

**生命周期管理**：

```python
client = _create_openai_client()
try:
    resp = await client.chat.completions.create(...)
    # 处理响应...
    return result
finally:
    # 确保客户端正确关闭
    try:
        await client.close()
    except Exception as e:
        logger.warning(f"[LLM] 关闭客户端时出错（可忽略）: {e}")
```

## 部署步骤

### 方法 1: 使用自动化脚本（推荐）

在 ECS 服务器上执行：

```bash
cd ~/interactive-storybook
bash deploy-fix.sh
```

脚本会自动：
1. 安装/更新 Python 依赖（包含 `httpx[socks]`）
2. 停止旧服务
3. 重启后端和前端服务
4. 显示进程 PID 和日志路径

### 方法 2: 手动部署

```bash
# 1. 更新代码
cd ~/interactive-storybook
git pull  # 如果使用 git

# 2. 安装依赖
cd backend
pip3 install --upgrade -r requirements.txt

# 3. 重启服务
bash ~/interactive-storybook/restart.sh
```

## 验证修复

### 1. 检查服务状态

```bash
# 查看进程
ps aux | grep -E "uvicorn|next"

# 查看端口
netstat -tulpn | grep -E "1000|1001"
```

### 2. 查看日志

```bash
# 后端日志
tail -f ~/interactive-storybook/logs/backend.log

# 前端日志
tail -f ~/interactive-storybook/logs/frontend.log
```

**期望输出**：
- 看到 `[LLM] ✅ OpenAI 客户端初始化成功`
- 没有 SOCKS 相关错误
- 没有 `_mounts` 属性错误

### 3. 测试故事生成

访问前端页面，尝试生成故事：
- 应该能够成功启动故事生成
- 不再出现 500 错误
- 查看后端日志确认 LLM 调用成功

## 额外说明

### 关于 SOCKS 代理

如果 ECS 环境中确实配置了 SOCKS 代理，这些修复会让应用正常工作。如果不需要代理，可以考虑：

1. **清除代理环境变量**（如果不需要）：
   ```bash
   unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
   ```

2. **在 systemd 服务中禁用代理**（如果使用 systemd）：
   在服务文件中添加：
   ```ini
   [Service]
   Environment="NO_PROXY=*"
   ```

### 性能优化

新的客户端配置包含：
- **连接池限制**：最多 10 个连接，5 个保活连接
- **合理超时**：防止请求无限挂起
- **正确资源释放**：避免内存泄漏

这些改进会提高应用的稳定性和性能。

## 故障排查

如果部署后仍有问题：

1. **检查依赖安装**：
   ```bash
   pip3 list | grep -E "httpx|socksio|openai"
   ```
   应该看到：
   - `httpx` (>= 0.26.0)
   - `socksio` (自动安装)
   - `openai` (>= 1.12.0)

2. **检查代理配置**：
   ```bash
   env | grep -i proxy
   ```

3. **查看详细错误**：
   ```bash
   # 临时启动后端（前台运行，查看详细输出）
   cd ~/interactive-storybook/backend
   python3 -m uvicorn app.main:app --host 0.0.0.0 --port 1001
   ```

4. **Python 版本**：
   确保使用 Python 3.8+
   ```bash
   python3 --version
   ```

## 联系支持

如果问题持续存在，请提供：
- 完整的错误日志
- Python 版本和已安装包列表
- 环境变量配置（`env | grep -i proxy`）
