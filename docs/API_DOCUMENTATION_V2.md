# RAG System V2 - API 接口文档

> 版本: V2.0.0  
> 更新日期: 2026-06-23  
> 基础URL: `http://localhost:8021`

---

## 目录

- [概述](#概述)
- [通用说明](#通用说明)
- [入库管线接口](#入库管线接口)
  - [POST /ingest/file](#post-ingestfile)
- [查询管线接口](#查询管线接口)
  - [POST /query/search](#post-querysearch)
- [系统接口](#系统接口)
  - [GET /health](#get-health)
  - [GET /](#get-)
- [错误处理](#错误处理)
- [最佳实践](#最佳实践)
- [示例代码](#示例代码)

---

## 概述

RAG System V2 是一个支持多租户知识库隔离的检索增强生成系统。相比 V1 版本，V2 实现了以下重大升级：

### V2 核心特性

1. **多租户数据隔离** - 通过 `kb_id` 实现知识库级别的数据隔离
2. **Upsert 自动更新** - 相同 `doc_id` + `kb_id` 自动覆盖，无需手动删除
3. **分批流控处理** - 向量化和入库均分批（≤100条/批）
4. **标准化语义重排** - 强制通过 Reranker 抹平 ES/Milvus 分数差异
5. **精准溯源标注** - Prompt 注入 `[来源: kb_id / 文档: doc_name]`

---

## 通用说明

### 认证

当前版本无需认证（可选配置 API Key）。

### Content-Type

所有 POST 请求必须使用 `application/json`：

```http
Content-Type: application/json
```

### 字符编码

请求和响应均使用 UTF-8 编码。

### 时间格式

时间戳使用 Unix 时间戳（秒）。

### 分页

当前版本不支持分页，所有结果一次性返回。

---

## 入库管线接口

### POST /ingest/file

入库文件或文件夹到指定知识库。

#### 请求

**URL**: `/ingest/file`

**Method**: `POST`

**Headers**:
```http
Content-Type: application/json
```

**请求体**:

```json
{
  "path": "string",           // 必填：文件或文件夹路径
  "kb_id": "string",          // 必填：知识库ID（V2新增）
  "chunk_size": integer,      // 可选：分块大小
  "chunk_overlap": integer,   // 可选：分块重叠
  "mode": "string",           // 可选：分块模式
  "semantic_split": boolean,  // 可选：语义分割
  "preserve_hierarchy": boolean  // 可选：保留层级
}
```

#### 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `path` | string | ✅ | - | 文件或文件夹的绝对路径 |
| `kb_id` | string | ✅ | - | **知识库ID**，用于数据隔离<br>建议格式：`kb_<业务领域>`<br>示例：`kb_finance`, `kb_hr`, `kb_tech` |
| `chunk_size` | integer | ❌ | 500 | 分块大小（字符数） |
| `chunk_overlap` | integer | ❌ | 50 | 分块重叠大小（字符数） |
| `mode` | string | ❌ | `general` | 分块模式：<br>- `general`: 通用模式<br>- `parent_child`: 父子模式 |
| `semantic_split` | boolean | ❌ | false | 是否启用语义分割 |
| `preserve_hierarchy` | boolean | ❌ | false | 是否保留标题层级结构 |

#### 响应

**成功响应 (200)**:

```json
{
  "total_files": integer,     // 处理的文件总数
  "success_files": integer,   // 成功入库的文件数
  "failed_files": integer,    // 失败的文件数
  "total_chunks": integer,    // 成功入库的切片总数
  "kb_id": "string",          // 知识库ID（V2新增）
  "errors": [                 // 错误信息列表
    "string",
    "string"
  ]
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `total_files` | integer | 本次处理的文件总数 |
| `success_files` | integer | 成功入库的文件数 |
| `failed_files` | integer | 失败的文件数 |
| `total_chunks` | integer | 成功入库的切片总数 |
| `kb_id` | string | 入库的目标知识库ID |
| `errors` | array | 错误信息列表（如有） |

**失败响应 (500)**:

```json
{
  "error": "string",
  "status_code": integer,
  "details": "string"
}
```

#### V2 特性说明

##### 1. 多租户数据隔离

- 所有数据必须归属于某个 `kb_id`
- 不同 `kb_id` 的数据完全隔离
- 查询时只能检索指定 `kb_id` 的数据

##### 2. Upsert 自动更新

- **doc_id 生成规则**: `MD5(文件名)`
- **幂等性**: 相同 `doc_id` + `kb_id` 自动覆盖旧数据
- **无需手动删除**: 直接再次入库即可更新文档
- **原子性**: 删除旧数据 + 插入新数据一次性完成

##### 3. 分批流控处理

- **向量化分批**: 每批最多 100 个文本
- **入库分批**: 每批最多 100 个切片
- **防止服务崩溃**: 大文件自动分批处理
- **分批公式**: `(总切片数 + 100 - 1) // 100`

#### 示例

##### 示例 1: 入库单个文件

```bash
curl -X POST http://localhost:8021/ingest/file \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/data/documents/finance/财务制度.txt",
    "kb_id": "kb_finance"
  }'
```

**响应**:
```json
{
  "total_files": 1,
  "success_files": 1,
  "failed_files": 0,
  "total_chunks": 25,
  "kb_id": "kb_finance",
  "errors": []
}
```

##### 示例 2: 入库整个文件夹

```bash
curl -X POST http://localhost:8021/ingest/file \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/data/documents/hr",
    "kb_id": "kb_hr",
    "chunk_size": 500,
    "chunk_overlap": 50
  }'
```

**响应**:
```json
{
  "total_files": 10,
  "success_files": 10,
  "failed_files": 0,
  "total_chunks": 250,
  "kb_id": "kb_hr",
  "errors": []
}
```

##### 示例 3: 更新已有文档

```bash
# 文档内容已更新，再次入库即可覆盖旧版本
curl -X POST http://localhost:8021/ingest/file \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/data/documents/finance/财务制度_v2.txt",
    "kb_id": "kb_finance"
  }'
```

**说明**:
- 如果文件名相同（或计算出的 `doc_id` 相同），会自动删除旧数据
- 无需手动调用删除接口

##### 示例 4: 大文件处理

```bash
# 大文件（如 350 个切片）自动分批处理
curl -X POST http://localhost:8021/ingest/file \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/data/documents/large_file.txt",
    "kb_id": "kb_tech"
  }'
```

**内部处理流程**:
```
350 个切片 → 分成 4 批
- Batch 1: 100 个切片
- Batch 2: 100 个切片
- Batch 3: 100 个切片
- Batch 4: 50 个切片
```

---

## 查询管线接口

### POST /query/search

查询知识库并生成带溯源标注的回答。

#### 请求

**URL**: `/query/search`

**Method**: `POST`

**Headers**:
```http
Content-Type: application/json
```

**请求体**:

```json
{
  "query": "string",          // 必填：查询文本
  "kb_id": "string",          // 必填：知识库ID（单个或多个，V2新增）
  "top_k": integer,           // 可选：每种检索返回数量
  "rerank_top_n": integer,    // 可选：Rerank返回数量
  "rerank_threshold": float,  // 可选：相关性阈值
  "temperature": float        // 可选：LLM温度
}
```

#### 参数说明

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | ✅ | - | 用户查询文本 |
| `kb_id` | string | ✅ | - | **知识库ID**（V2新增）<br>- 单个: `kb_finance`<br>- 多个: `kb_finance,kb_hr,kb_tech`<br>（逗号分隔，支持跨库查询） |
| `top_k` | integer | ❌ | 15 | 每种检索（ES + Milvus）返回的数量 |
| `rerank_top_n` | integer | ❌ | 15 | Rerank 返回的 top-n 结果数量 |
| `rerank_threshold` | float | ❌ | 0.1 | 相关性阈值（0-1），低于此值的结果被过滤 |
| `temperature` | float | ❌ | 0.7 | LLM 生成温度（控制创造性） |

#### 响应

**成功响应 (200)**:

```json
{
  "query": "string",               // 用户查询
  "answer": "string",              // LLM 生成的答案
  "context_chunks": integer,       // 用于生成答案的切片数量
  "kb_ids": "string",              // 查询的知识库ID列表（V2新增）
  "reranked_results": [            // Rerank后的结果列表（V2增强）
    {
      "index": integer,            // 原始索引
      "relevance_score": float,    // 标准化相关性分数（0-1）
      "kb_id": "string",           // 知识库ID（V2新增）
      "doc_name": "string",        // 文档名称（V2新增）
      "document": {
        "text": "string"           // 切片内容
      }
    }
  ],
  "usage": {                       // Token使用统计
    "prompt_tokens": integer,
    "completion_tokens": integer,
    "total_tokens": integer
  }
}
```

**响应字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `query` | string | 用户的原始查询文本 |
| `answer` | string | LLM 生成的最终答案 |
| `context_chunks` | integer | 实际用于生成答案的切片数量 |
| `kb_ids` | string | 查询涉及的知识库ID列表 |
| `reranked_results` | array | Rerank 后的结果列表（带溯源信息） |
| `reranked_results[].index` | integer | 在原始搜索结果中的索引 |
| `reranked_results[].relevance_score` | float | 标准化相关性分数（0-1） |
| `reranked_results[].kb_id` | string | 该切片所属的知识库ID |
| `reranked_results[].doc_name` | string | 该切片所属的文档名称 |
| `reranked_results[].document.text` | string | 切片的文本内容 |
| `usage` | object | LLM Token 使用统计 |

**失败响应 (500)**:

```json
{
  "error": "string",
  "status_code": integer,
  "details": "string"
}
```

#### V2 特性说明

##### 1. kb_id 动态路由

- **单个 kb_id**: `"kb_finance"` - 只在财务知识库中检索
- **多个 kb_id**: `"kb_finance,kb_hr"` - 跨财务和HR知识库联合检索
- **隔离保证**: 只返回指定 `kb_id` 的数据，不会泄露其他知识库

##### 2. 标准化语义重排

**问题**: ES 的 BM25 分数（0-10+，越大越好）和 Milvus 的向量距离（0-2，越小越好）无法直接比较

**解决方案**: 强制通过 Reranker 模型标准化评分

**流程**:
```
混合检索结果 → 提取所有 content → 喂给 Reranker
→ 输出 relevance_score (0-1) → 按 relevance_score 排序
```

**优势**:
- ✅ 抹平异构分数差异
- ✅ 统一评分标准（0-1）
- ✅ 更精准的语义相关性判断

##### 3. 溯源标注系统

**Prompt 拼接格式**:
```
[来源: kb_finance / 文档: 财务制度.txt]
差旅报销标准：员工出差可报销交通费、住宿费和餐饮费。

[来源: kb_hr / 文档: 考勤制度.txt]
工作时间：周一至周五，早9点到晚6点。
```

**优势**:
- ✅ 大模型知道数据来源
- ✅ 回答可追溯到具体文档
- ✅ 跨库查询时区分不同知识库
- ✅ 提升答案可信度

#### 示例

##### 示例 1: 单知识库查询

```bash
curl -X POST http://localhost:8021/query/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是差旅报销标准?",
    "kb_id": "kb_finance"
  }'
```

**响应**:
```json
{
  "query": "什么是差旅报销标准?",
  "answer": "根据财务制度，员工出差可以报销交通费、住宿费和餐饮费。具体标准为...",
  "context_chunks": 3,
  "kb_ids": "kb_finance",
  "reranked_results": [
    {
      "index": 0,
      "relevance_score": 0.85,
      "kb_id": "kb_finance",
      "doc_name": "财务制度.txt",
      "document": {
        "text": "差旅报销标准：员工出差可报销交通费、住宿费和餐饮费..."
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

##### 示例 2: 跨知识库查询

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

**响应**:
```json
{
  "query": "报销流程和工作时间规定",
  "answer": "根据财务制度和HR考勤制度的相关规定：\n\n1. 报销流程：...\n2. 工作时间：...",
  "context_chunks": 5,
  "kb_ids": "kb_finance,kb_hr",
  "reranked_results": [
    {
      "index": 0,
      "relevance_score": 0.88,
      "kb_id": "kb_finance",
      "doc_name": "财务制度.txt",
      "document": {
        "text": "报销流程：提交申请 → 部门审批 → 财务审核..."
      }
    },
    {
      "index": 1,
      "relevance_score": 0.76,
      "kb_id": "kb_hr",
      "doc_name": "考勤制度.txt",
      "document": {
        "text": "工作时间：周一至周五，早9点到晚6点..."
      }
    }
  ],
  "usage": {
    "prompt_tokens": 2500,
    "completion_tokens": 350,
    "total_tokens": 2850
  }
}
```

##### 示例 3: 无相关结果

```bash
curl -X POST http://localhost:8021/query/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是股票投资策略?",
    "kb_id": "kb_hr"
  }'
```

**响应**:
```json
{
  "query": "什么是股票投资策略?",
  "answer": "知识库中未查到相关信息。",
  "context_chunks": 0,
  "kb_ids": "kb_hr",
  "reranked_results": [],
  "usage": null
}
```

---

## 系统接口

### GET /health

健康检查接口。

#### 请求

**URL**: `/health`

**Method**: `GET`

#### 响应

```json
{
  "status": "healthy",
  "app_name": "RAG System",
  "version": "1.0.0"
}
```

---

### GET /

根端点，返回 API 信息。

#### 请求

**URL**: `/`

**Method**: `GET`

#### 响应

```json
{
  "name": "RAG System",
  "version": "1.0.0",
  "docs": "/docs",
  "health": "/health",
  "endpoints": {
    "ingestion": {
      "sync": "POST /ingest/file"
    },
    "query": {
      "params": "POST /query/search?query=..."
    }
  }
}
```

---

## 错误处理

### 错误响应格式

所有错误响应遵循统一格式：

```json
{
  "error": "错误描述",
  "status_code": HTTP状态码,
  "details": "详细信息"
}
```

### 常见错误码

| 状态码 | 说明 | 可能原因 |
|--------|------|----------|
| 400 | Bad Request | 请求参数缺失或格式错误 |
| 500 | Internal Server Error | 服务内部错误（底层服务失败、网络异常等） |
| 503 | Service Unavailable | 底层服务不可用（超时、连接失败等） |

### 错误示例

#### 缺少必填字段

**请求**:
```json
{
  "path": "/data/docs",
  // 缺少 kb_id
}
```

**响应** (400):
```json
{
  "error": "Validation error",
  "details": "kb_id is required"
}
```

#### 底层服务失败

**请求**:
```json
{
  "path": "/data/nonexistent",
  "kb_id": "kb_finance"
}
```

**响应** (500):
```json
{
  "error": "Internal server error",
  "details": "File not found: /data/nonexistent"
}
```

#### 网络超时

**响应** (503):
```json
{
  "error": "Service unavailable",
  "details": "Embedding service timeout after 120s"
}
```

---

## 最佳实践

### 1. 知识库命名规范

建议使用统一的知识库ID命名格式：

```
kb_<业务领域>
```

示例：
- `kb_finance` - 财务知识库
- `kb_hr` - HR知识库
- `kb_tech` - 技术知识库
- `kb_legal` - 法务知识库

### 2. 入库最佳实践

#### 分批入库

对于大量文件，建议分批入库：

```python
# 不要一次性入库整个大目录
# ❌ 不推荐
ingest(path="/data/all_documents", kb_id="kb_all")

# ✅ 推荐：按业务域分批入库
ingest(path="/data/finance", kb_id="kb_finance")
ingest(path="/data/hr", kb_id="kb_hr")
ingest(path="/data/tech", kb_id="kb_tech")
```

#### 文档更新

文档更新时直接再次入库即可：

```python
# 文档内容更新后，直接再次入库
# 系统会自动删除旧版本
ingest(path="/data/finance/财务制度_v2.txt", kb_id="kb_finance")
```

### 3. 查询最佳实践

#### 合理设置 top_k

- **精确查询**: `top_k=10-15`
- **广泛查询**: `top_k=20-30`
- **不要过大**: 避免 `top_k > 50`，影响性能

#### 调整 rerank_threshold

- **严格模式**: `rerank_threshold=0.6-0.8`（只返回高度相关结果）
- **宽松模式**: `rerank_threshold=0.1-0.3`（返回更多候选）
- **平衡模式**: `rerank_threshold=0.4-0.5`

#### 跨库查询

只在必要时使用跨库查询：

```python
# ✅ 推荐：单库查询（更快、更精准）
query("报销流程", kb_id="kb_finance")

# ✅ 适度使用：跨库查询（多域问题）
query("报销和工作时间", kb_id="kb_finance,kb_hr")

# ❌ 不推荐：过多知识库（影响性能）
query("...", kb_id="kb_finance,kb_hr,kb_tech,kb_legal")
```

### 4. 性能优化

#### 并发请求

入库操作建议串行（避免冲突），查询操作可并发：

```python
# ❌ 入库不建议并发（可能导致数据冲突）
asyncio.gather(
    ingest(path="file1", kb_id="kb1"),
    ingest(path="file2", kb_id="kb1")  # 相同 kb_id
)

# ✅ 查询可以并发
asyncio.gather(
    query("问题1", kb_id="kb_finance"),
    query("问题2", kb_id="kb_hr")
)
```

#### 缓存策略

对于高频查询，可在应用层添加缓存：

```python
# 示例：简单的查询缓存
cache = {}

def cached_query(query_text, kb_id):
    cache_key = f"{query_text}|{kb_id}"
    if cache_key in cache:
        return cache[cache_key]
    
    result = query(query_text, kb_id)
    cache[cache_key] = result
    return result
```

---

## 示例代码

### Python 完整示例

```python
import requests
import json

BASE_URL = "http://localhost:8021"

def ingest_file(path, kb_id):
    """入库文件到指定知识库"""
    payload = {
        "path": path,
        "kb_id": kb_id
    }
    
    response = requests.post(
        f"{BASE_URL}/ingest/file",
        json=payload
    )
    
    print(f"入库结果: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))
    return response.json()


def query_kb(query_text, kb_ids):
    """查询知识库"""
    payload = {
        "query": query_text,
        "kb_id": kb_ids,
        "top_k": 15,
        "rerank_threshold": 0.4
    }
    
    response = requests.post(
        f"{BASE_URL}/query/search",
        json=payload
    )
    
    print(f"查询结果: {response.status_code}")
    result = response.json()
    
    print(f"\n答案: {result['answer']}")
    print(f"\n使用了 {result['context_chunks']} 个切片")
    print(f"\n知识库: {result['kb_ids']}")
    
    # 打印溯源信息
    if result['reranked_results']:
        print("\n溯源信息:")
        for r in result['reranked_results']:
            print(f"  - [{r['kb_id']} / {r['doc_name']}]: score={r['relevance_score']}")
    
    return result


if __name__ == "__main__":
    # 示例 1: 入库
    print("=" * 60)
    print("示例 1: 入库财务文档")
    print("=" * 60)
    ingest_file("/data/documents/finance", "kb_finance")
    
    # 示例 2: 单库查询
    print("\n" + "=" * 60)
    print("示例 2: 查询财务知识库")
    print("=" * 60)
    query_kb("什么是差旅报销标准?", "kb_finance")
    
    # 示例 3: 跨库查询
    print("\n" + "=" * 60)
    print("示例 3: 跨库查询")
    print("=" * 60)
    query_kb("报销流程和工作时间规定", "kb_finance,kb_hr")
```

### Bash cURL 示例

```bash
# 入库
curl -X POST http://localhost:8021/ingest/file \
  -H "Content-Type: application/json" \
  -d '{"path":"/data/docs/finance","kb_id":"kb_finance"}'

# 查询
curl -X POST http://localhost:8021/query/search \
  -H "Content-Type: application/json" \
  -d '{"query":"报销标准","kb_id":"kb_finance"}'

# 健康检查
curl http://localhost:8021/health
```

---

## 附录

### A. 分批处理详细说明

V2 的分批处理机制：

```
总切片数: 350
批次数: ceil(350 / 100) = 4

处理流程:
├─ Batch 1 (切片 0-99)
│  ├─ 向量化: 100个文本 → 100个向量
│  └─ 入库: 100个切片 → MySQL + ES + Milvus
├─ Batch 2 (切片 100-199)
│  ├─ 向量化: 100个文本 → 100个向量
│  └─ 入库: 100个切片 → MySQL + ES + Milvus
├─ Batch 3 (切片 200-299)
│  ├─ 向量化: 100个文本 → 100个向量
│  └─ 入库: 100个切片 → MySQL + ES + Milvus
└─ Batch 4 (切片 300-349)
   ├─ 向量化: 50个文本 → 50个向量
   └─ 入库: 50个切片 → MySQL + ES + Milvus
```

### B. Upsert 机制详细说明

V2 的 Upsert 流程：

```
入库请求: kb_id="kb_finance", doc_id="abc123" (文件MD5)

底层处理:
1. 检查是否存在: kb_id="kb_finance" AND doc_id="abc123"
   ├─ 如果存在 → 删除旧文档及其所有切片（MySQL + ES + Milvus）
   └─ 如果不存在 → 直接插入
   
2. 插入新数据:
   ├─ MySQL: 创建文档记录 (status=SUCCESS)
   ├─ MySQL: 批量插入切片
   ├─ ES: 批量插入切片
   └─ Milvus: 批量插入向量
   
3. 如果任一步骤失败:
   └─ MySQL: 更新文档状态为 FAILED
```

### C. 溯源标注详细说明

V2 的溯源标注格式：

```
用户查询: "报销流程和工作时间"

混合检索返回:
- Result 1: kb_id="kb_finance", doc_name="财务制度.txt", content="报销流程..."
- Result 2: kb_id="kb_hr", doc_name="考勤制度.txt", content="工作时间..."

Rerank后按 relevance_score 排序:
- Result 1: score=0.85 (财务制度)
- Result 2: score=0.76 (考勤制度)

组装给LLM的Prompt:
"""
你是一个专业的知识库助手。请严格基于以下参考资料回答用户的问题。

【参考资料】：

[来源: kb_finance / 文档: 财务制度.txt]
报销流程：提交申请 → 部门审批 → 财务审核...

[来源: kb_hr / 文档: 考勤制度.txt]
工作时间：周一至周五，早9点到晚6点...

【用户问题】：
报销流程和工作时间规定
"""
```

---
