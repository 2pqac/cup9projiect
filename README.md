# 多模态数据驱动的可解释精准问数 / 问答智能体

> “中国电子杯”第三届高校 ICT 产教融合创新大赛 · 赛题八（网信产业应用赛道）
>
> 输入自然语言问题，由 Agent 自动判断并查询 **结构化数据库（NL2SQL）** 或
> **非结构化文档（RAG）**，返回答案、数据 / 文档来源与可解释推理链（trace）。

---

## 一、系统功能

- **NL2SQL（结构化数据）**：中文问题 → 外键图 BFS 定位相关表 → LLM 生成 SQL
  → 安全校验 + 表字段校验 → 执行；失败把报错回喂模型自我修正（最多 3 次），
  LLM 不可用时规则字典兜底。
- **RAG（非结构化数据）**：PDF / TXT 加载 → 结构化切片 → TF-IDF 检索
  → LLM 严格基于片段生成答案，并给出文档名、章节、页码来源。
- **Agent（编排）**：意图路由（SQL / RAG），统一展示答案、来源与推理链。

---

## 二、目录结构

```
cup8project/
├─ agent/
│  ├─ main.py            # 系统总入口（路由 + 结果展示）
│  └─ router.py          # 意图路由：SQL / RAG
├─ nl2sql/
│  ├─ llm_nl2sql.py      # NL2SQL 主流程（LLM 生成 + 自我修正 + 规则兜底）
│  ├─ join_graph.py      # 外键关系图 + BFS 自动补全 JOIN 路径
│  ├─ schema_linking.py  # 规则 Schema Linking（实体锚点 / 字段 / 值）
│  ├─ validator.py       # SQL 安全校验（拦截 DROP/DELETE/UPDATE 等写操作）
│  ├─ schema_validator.py# 表 / 字段真实存在校验
│  ├─ query_service.py   # 安全校验 + 表校验 + 执行 串联
│  └─ nl2sql_generator.py# 规则 SQL 生成（兜底）
├─ database/
│  ├─ chinook.db         # Chinook SQLite 数据库（11 张表，已自带）
│  ├─ schema.py          # 表结构提取
│  ├─ schema.json        # 表 / 字段 / 主键 / 外键（程序读取）
│  ├─ schema.sql         # 建表语句
│  ├─ executor.py        # 只读 SELECT 执行器
│  └─ export_schema.py   # 导出 schema.json / schema.sql
├─ rag/
│  ├─ rag_qa.py          # RAG 主服务（answer() / run()）
│  ├─ document_loader.py # PDF / TXT 加载
│  ├─ chunker.py         # 章节识别 + 文本切片
│  └─ retriever.py       # TF-IDF + 余弦相似度检索
├─ knowledge_base/       # RAG 知识库文档
│  ├─ chinook_guide.pdf
│  └─ chinook_guide.txt
├─ tests/                # pytest 测试
├─ evaluation/           # NL2SQL 评估脚本与结果
│  ├─ nl2sql_eval.py     # 基线 vs 优化，输出 5 项指标
│  ├─ analyze_oos.py     # 离线分析“超纲 / 脑补表”
│  └─ results/           # 评估结果 JSON
├─ .env.example          # 环境变量模板
├─ requirements.txt
└─ README.md
```

---

## 三、快速开始

> 环境：Windows + PowerShell（macOS / Linux 命令等价）；Python 3.10+（本项目使用 3.13）。

```powershell
# 1. 进入项目目录
cd D:\cup8project

# 2. 创建并激活虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
copy .env.example .env
# 用记事本 / VSCode 打开 .env，填入 LLM_API_KEY（本项目使用 DeepSeek，OpenAI 兼容接口）
```

`.env` 示例：

```ini
LLM_API_KEY=sk-你的key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

> 数据库 `database/chinook.db` 已自带，无需额外下载。
> 如需重新生成结构文件：`python database/export_schema.py`。

---

## 四、运行

```powershell
# 完整系统（Agent 路由 SQL / RAG，控制台交互）
python agent/main.py

# 仅 NL2SQL 对话
python nl2sql/llm_nl2sql.py
```

---

## 五、测试

```powershell
# 运行全部测试
pytest tests/ -q
```

- **已配置 `LLM_API_KEY`**：离线测试 + LLM 端到端测试全部运行；
- **未配置 key**：离线测试通过，LLM 端到端用例自动 `skip`（属正常现象，
  对外结论需注明“LLM 集成测试在无 key 交付版处于跳过状态”）。

---

## 六、NL2SQL 评估（中级任务：精准 Schema Linking + 高质量多表 JOIN）

```powershell
# 在线评估：基线 vs 优化（需 key，结果保存到 evaluation/results/）
python evaluation/nl2sql_eval.py

# 离线分析：模型是否引用了“系统未提供的表”（无需再次调用大模型）
python evaluation/analyze_oos.py
```

对比结果（11 个问题，2026-10-01 实测）：

| 指标 | 基线（仅规则锚点） | 优化（外键图 + BFS） |
| --- | --- | --- |
| Schema Linking 命中率 | 81.8% | **100%** |
| 超纲表引用（脑补未提供表）问题数 | 2 / 11 | **0 / 11** |
| 执行准确率 | 100% | 100% |
| 首次成功率 | 100% | 100% |
| 自我修正成功率 | 0% | 0% |
| 平均时延 | 0.61 s | 0.68 s |

**口径说明（重要）**：Chinook 是公开教学库，基座模型在训练数据中见过，
基线在两个跨表问题（“消费前 5 客户”“单首歌曲最高销量”）上**凭记忆脑补**
了缺失的 Invoice / InvoiceLine 表（超纲引用 2 次），因此执行准确率都为 100%。
优化方案的确定性价值体现在：Schema 命中率达 100%、零超纲引用——
即把“依赖模型记忆、不可控、不可复现”的召回，变为“基于外键图、确定、
可复现、可扩展到任意库”的召回；迁移到模型未见过的真实业务库时，
基线将因无法记忆而失败，优化方案仍可正常工作。

---

## 七、模块接口约定（供 Agent / 前后端对接）

**NL2SQL**

```python
from nl2sql.llm_nl2sql import NL2SQL

result = NL2SQL().run("美国有多少客户？", use_join_graph=True)
# use_join_graph=False 时为基线（不做外键路径补全），仅用于评估对比
```

返回字段：

```json
{
  "success": true,
  "sql": "SELECT ...",
  "columns": ["列名"],
  "rows": [["值"]],
  "data":  [["值"]],
  "tables": ["Customer"],
  "attempts": 1,
  "trace": [{"step": "步骤名", "detail": "详情"}],
  "message": "",
  "error": ""
}
```

- `rows` 与 `data` 内容相同（`data` 为兼容别名）；
- `attempts`：LLM 尝试次数（1–3），`0` 表示规则兜底；
- 失败时 `success=false`，错误信息同时放在 `message` 与 `error`。

**RAG**

```python
from rag.rag_qa import RAGService

result = RAGService().answer("Album 表和 Artist 表是什么关系？")
# 返回：success / answer / sources / trace（run() 为等价入口）
```

---

## 八、团队分工

| 成员 | 主责 |
| --- | --- |
| A | 数据库 + NL2SQL（schema、Schema Linking、外键图 BFS、SQL 生成与校验、评估） |
| B | RAG + 文档处理（加载、切片、检索、来源、中级任务“不标准目录识别”） |
| C | Agent 编排 + 前后端 Demo + 模块整合与测试 |

> 原则：每人有主责，但都需理解另外两人的模块，避免答辩时单点风险。

---

## 九、技术栈

Python · SQLite（Chinook）· DeepSeek（OpenAI 兼容接口）· sqlglot（SQL 解析 / 校验）
· scikit-learn（TF-IDF）· pypdf（PDF 读取）· pytest（测试）
· Gradio / FastAPI（依赖已安装，交互界面由 C 负责）
