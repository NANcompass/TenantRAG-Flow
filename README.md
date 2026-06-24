# RAG System V2

一个完整的检索增强生成 (Retrieval Augmented Generation) 系统，支持多租户知识库隔离、智能分批处理和精准溯源标注。

## 🆕 V2 版本特性

相比 V1 版本，V2 实现了以下重大升级：

| 特性 | V1 | V2 |
|------|----|----|
| **数据隔离** | 全局混杂 | ✅ 多租户 `kb_id` 隔离 |
| **文档更新** | 手动删除+插入 | ✅ 自动 Upsert（幂等） |
| **大文件处理** | 无限制（易崩溃） | ✅ 分批处理（≤100条/批） |
| **检索融合** | 异构分数难比较 | ✅ Reranker 标准化评分 |
| **答案溯源** | 无来源标注 | ✅ `[来源: kb_id / 文档: doc_name]` |
| **跨库查询** | 不支持 | ✅ 支持多个 `kb_id` 联合查询 |

---

## 项目结构

```
rag_system/
├── app/
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py               # FastAPI 路由定义（V2）
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py               # 配置管理（含 BULK_INSERT_BATCH_SIZE）
│   ├── pipelines/
│   │   ├── __init__.py
│   │   ├── ingestion_pipeline.py   # 入库管线 V2（分批+kb_id）
│   │   └── query_pipeline.py       # 查询管线 V2（溯源+重排）
│   ├── schemas/
│   │   ├── __init__.py
│   │   └── models.py               # Pydantic 数据模型（支持 kb_id）
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── http_client.py          # HTTP客户端（含重试）
│   │   └── logger.py               # 日志配置
│   ├── __init__.py
│   └── main.py                     # FastAPI 应用入口
├── test/
│   ├── test_v2_functionality.py    # V2 功能测试脚本
│   ├── api_test_examples.py        # API 测试示例
│   └── TEST_REPORT_V2.md           # V2 测试报告
├── docs/
│   └── API_DOCUMENTATION_V2.md     # API 接口文档
├── .env                            # 配置文件
├── .env.example                    # 配置示例
├── main.py                         # FastAPI 启动脚本
├── main_mcp.py                     # MCP HTTP 服务启动脚本
├── requirements.txt                # Python 依赖
├── MCP_README.md                   # MCP 服务配置指南
├── plan-v2.md                      # V2 方案设计文档
└── README.md
```

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 到 `.env` 并配置所有服务地址：

```bash
cp .env.example .env
```

### 3. 启动服务

#### FastAPI REST API 服务

```bash
python main.py
```

服务将在 `http://0.0.0.0:8021` 启动（端口可在 `.env` 中配置）。

#### MCP HTTP 服务

```bash
python main_mcp.py
```

MCP 服务将在 `http://0.0.0.0:8022` 启动。

自定义端口：
```bash
export MCP_PORT=9000
python main_mcp.py
```

### 4. 访问 API 文档

**FastAPI 服务:**
- **Swagger UI**: http://localhost:8021/docs
- **ReDoc**: http://localhost:8021/redoc
- **Health Check**: http://localhost:8021/health

**MCP 服务:**
- **MCP 端点**: http://localhost:8022/mcp
- **Health Check**: http://localhost:8022/health
- **详细配置**: [MCP_README.md](MCP_README.md)

---

## 🔌 MCP HTTP 服务

除了 FastAPI REST API，系统还提供 MCP HTTP 服务，用于与 AI 客户端集成。

### MCP 服务端点

- **服务地址**: http://localhost:8022
- **MCP 端点**: http://localhost:8022/mcp
- **传输协议**: Streamable HTTP

### MCP 工具

#### search_knowledge_base

通过 MCP 搜索知识库并生成答案。

**参数**:
- `query` (必需): 用户查询文本
- `kb_id` (必需): 知识库 ID（单个或逗号分隔多个）
- `top_k` (可选): 搜索结果数量
- `rerank_top_n` (可选): 重排后保留的结果数量
- `rerank_threshold` (可选): 相关性阈值
- `temperature` (可选): LLM 温度参数

**配置到 Claude Code**:

在 `.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "rag-system": {
      "url": "http://localhost:8022/mcp",
      "transport": "http"
    }
  }
}
```

---

## API 端点 V2

### 🔥 入库管线（Ingestion Pipeline）

#### POST /ingest/file

入库文件或文件夹到指定知识库。

**请求体:**
```json
{
  "path": "/data/documents/finance",
  "kb_id": "kb_finance",
  "chunk_size": 500,
  "chunk_overlap": 50,
  "mode": "general",
  "semantic_split": false,
  "preserve_hierarchy": false
}
```

**参数说明:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `path` | string | ✅ | 文件或文件夹路径 |
| `kb_id` | string | ✅ | **知识库ID**（V2新增，用于数据隔离） |
| `chunk_size` | int | ❌ | 分块大小（默认 500） |
| `chunk_overlap` | int | ❌ | 分块重叠（默认 50） |
| `mode` | string | ❌ | 分块模式：`general` 或 `parent_child` |
| `semantic_split` | bool | ❌ | 是否启用语义分割 |
| `preserve_hierarchy` | bool | ❌ | 是否保留标题层级 |

**响应示例:**
```json
{
  "total_files": 5,
  "success_files": 5,
  "failed_files": 0,
  "total_chunks": 125,
  "kb_id": "kb_finance",
  "errors": []
}
```

**V2 特性：**
- ✅ 强制指定 `kb_id`，实现多租户隔离
- ✅ 自动 Upsert：相同 `doc_id` + `kb_id` 自动覆盖更新
- ✅ 分批处理：每批最多 100 个切片，防止服务崩溃
- ✅ 幂等性：可重复入库，不会产生重复数据

**示例：**

入库单个文件：
```bash
curl -X POST http://localhost:8021/ingest/file \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/data/docs/财务制度.txt",
    "kb_id": "kb_finance"
  }'
```

入库整个文件夹：
```bash
curl -X POST http://localhost:8021/ingest/file \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/data/documents/hr",
    "kb_id": "kb_hr",
    "chunk_size": 500
  }'
```

---

### 🔍 查询管线（Query Pipeline）

#### POST /query/search

查询知识库并生成带溯源标注的回答。

**请求体:**
```json
{
  "query": "什么是差旅报销标准?",
  "kb_id": "kb_finance,kb_hr",
  "top_k": 15,
  "rerank_top_n": 15,
  "rerank_threshold": 0.1,
  "temperature": 0.7
}
```

**参数说明:**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | ✅ | 用户查询文本 |
| `kb_id` | string | ✅ | **知识库ID**（V2新增，支持单个或逗号分隔多个） |
| `top_k` | int | ❌ | 每种检索返回数量（默认 15） |
| `rerank_top_n` | int | ❌ | Rerank 返回数量（默认 15） |
| `rerank_threshold` | float | ❌ | 相关性阈值（默认 0.1） |
| `temperature` | float | ❌ | LLM 温度（默认 0.7） |

**响应示例:**
```json
{
  "query": "什么是差旅报销标准?",
  "answer": "根据财务制度，员工出差可以报销交通费、住宿费和餐饮费...",
  "context_chunks": 3,
  "kb_ids": "kb_finance,kb_hr",
  "reranked_results": [
    {
      "index": 0,
      "relevance_score": 0.85,
      "kb_id": "kb_finance",
      "doc_name": "财务制度.txt",
      "document": {
        "text": "差旅报销标准：员工出差可报销交通费..."
      }
    },
    {
      "index": 1,
      "relevance_score": 0.72,
      "kb_id": "kb_hr",
      "doc_name": "考勤制度.txt",
      "document": {
        "text": "工作时间：周一至周五..."
      }
    }
  ],
  "usage": {
    "prompt_tokens": 1500,
    "completion_tokens": 200,
    "total_tokens": 1700
  }
}
```

**V2 特性：**
- ✅ 支持单个 `kb_id` 或跨库查询（逗号分隔）
- ✅ 强制通过 Reranker 标准化评分（0-1）
- ✅ Prompt 注入溯源标注：`[来源: kb_finance / 文档: 财务制度.txt]`
- ✅ 结果包含 `kb_id` 和 `doc_name`，精准溯源

**示例：**

单知识库查询：
```bash
curl -X POST http://localhost:8021/query/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是差旅报销标准?",
    "kb_id": "kb_finance"
  }'
```

跨知识库查询：
```bash
curl -X POST http://localhost:8021/query/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "报销流程和工作时间规定",
    "kb_id": "kb_finance,kb_hr",
    "top_k": 20,
    "rerank_threshold": 0.5
  }'
```

---

## 核心流程 V2

### 入库管线流程

```
[文件路径 + kb_id]
    │
    ▼
1. 文档分块服务 (/chunk/file)
   → 提取所有 chunks 的 content，扁平化
    │
    ▼
2. 文本向量化服务 (/v1/embeddings)
   → **分批生成 embeddings（每批≤100）**
    │
    ▼
3. 数据对齐
   → 根据 index 将 vector 回填到对应 chunk
    │
    ▼
4. 批量插入服务 (/api/documents/bulk)
   → **分批写入 MySQL + ES + Milvus（每批≤100）**
   → **带上 kb_id 实现数据隔离**
   → **Upsert 自动覆盖旧数据**
```

**V2 关键改进：**
- 🔄 **分批处理**：向量化分批（≤100）、入库分批（≤100）
- 🏷️ **kb_id 隔离**：每条切片带上 `kb_id` 字段
- ⚡ **Upsert 机制**：相同 `doc_id` + `kb_id` 自动覆盖，无需手动删除
- 📊 **流控保护**：防止大批量数据压垮底层服务

### 查询管线流程

```
[用户查询 + kb_id]
    │
    ├─→ 1. 向量化服务 (/v1/embeddings)
        → 获得查询向量
    │
    ▼
2. 混合检索服务 (/api/search/hybrid)
   → ES文本检索 + Milvus向量检索
   → **kb_id 过滤（支持多个）**
   → 自动去重，补全 content
    │
    ▼
3. Rerank服务 (/v1/rerank)
   → **标准化评分（0-1），抹平 ES/Milvus 分数差异**
   → 按 relevance_score 重排序
    │
    ▼
4. 阈值过滤
   → 过滤 relevance_score < threshold 的结果
    │
    ▼
5. 溯源 Prompt组装
   → **注入来源标注：[来源: kb_id / 文档: doc_name]**
   → Context + Query
    │
    ▼
6. LLM生成 (/v1/chat/completions)
   → 最终答案（可追溯到具体文档）
```

**V2 关键改进：**
- 🔍 **kb_id 路由**：支持单库或跨库查询
- 🎯 **标准化重排**：强制通过 Reranker，统一评分标准
- 📝 **溯源标注**：Prompt 中明确数据来源
- 🔗 **精准溯源**：答案可追溯到 `kb_id` + `doc_name`

---

## 配置说明

所有配置都在 `.env` 文件中：

### 服务配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `CHUNK_SERVICE_URL` | 分块服务地址 | - |
| `EMBEDDING_SERVICE_URL` | 向量化服务地址 | - |
| `RERANK_SERVICE_URL` | Rerank服务地址 | - |
| `LLM_SERVICE_URL` | LLM服务地址 | - |
| `DOCUMENT_SERVICE_URL` | 文档存储服务地址 | - |

### V2 新增配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `BULK_INSERT_BATCH_SIZE` | **批量处理上限** | 100 |

### 管线配置

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `DEFAULT_CHUNK_SIZE` | 默认分块大小 | 500 |
| `DEFAULT_CHUNK_OVERLAP` | 分块重叠 | 50 |
| `DEFAULT_TOP_K` | 混合检索数量 | 15 |
| `RERANK_TOP_N` | Rerank返回数量 | 15 |
| `RERANK_THRESHOLD` | 相关性阈值 | 0.1 |
| `LLM_TEMPERATURE` | LLM温度 | 0.7 |
| `LLM_MAX_TOKENS` | LLM最大tokens | 30000 |
| `MAX_RETRIES` | HTTP重试次数 | 3 |

---

## 异常处理

- ✅ HTTP 请求失败自动重试（指数退避）
- ✅ 详细的日志记录（INFO/WARNING/ERROR级别）
- ✅ 优雅的错误响应（包含错误详情和状态码）
- ✅ 底层服务失败感知（如 bulk insert status=FAILED）

---

## 开发

### 启动服务

```bash
# FastAPI 服务（端口 8021）
python main.py

# MCP HTTP 服务（端口 8022）
python main_mcp.py

# 同时运行两个服务
python main.py & python main_mcp.py &
```

### 开发模式

```bash
# FastAPI 开发模式（热重载）
DEBUG=true python main.py

# 生产模式
DEBUG=false python main.py
```

### 自定义 MCP 服务端口

```bash
export MCP_PORT=9000
export MCP_HOST=127.0.0.1
python main_mcp.py
```

---

## API 文档

详细的 API 接口文档请查看：[docs/API_DOCUMENTATION_V2.md](docs/API_DOCUMENTATION_V2.md)

---

## 版本历史

### V2.0.0 (2026-06-23)
- ✅ 多租户数据隔离（kb_id）
- ✅ Upsert 自动更新机制
- ✅ 分批流控处理（≤100）
- ✅ Reranker 标准化评分
- ✅ 溯源标注系统
- ✅ MCP HTTP 服务支持（Streamable HTTP 传输）

### V1.0.0
- 基础入库和查询管线
- 混合检索（ES + Milvus）
- Rerank 重排
- LLM 生成

---

## 许可证

内部项目，仅供授权用户使用。

---

## 联系方式

如有问题或建议，请联系项目负责人。