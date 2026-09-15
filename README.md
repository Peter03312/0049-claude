# 🍃 树叶辨认卡（Leaf Cards）

给 9–12 岁自然观察小组用的全栈小应用：孩子们把自采的树叶做成 **4–20 张对象卡**，
给每张卡登记观察到的特征（真 / 假 / 未知），系统算出一棵二分辨认树，
保证**每往下走一步，都能把剩下的卡片分成非空的两边**，一直走到只剩一片叶子。

- 「显眼的特征」不一定够用来区分——算法会在所有合法特征里挑最优提问顺序；
- **未知绝不被当成「假」**：某张卡没观察过的特征，不能出现在仍包含它的问题里；
- 分不开时不给残缺树，而是用孩子能懂的话说明：是哪些卡片、卡在哪个特征上
  （还没观察的「？」，还是大家都一样）。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3（`<script setup>`）+ TypeScript + Vite 6，生产用 Nginx 托管 |
| 后端 | FastAPI + SQLAlchemy 2 |
| 数据库 | SQLite（Docker 卷持久化） |
| 编排 | Docker Compose（web、api 两个服务） |

## 一键启动（Docker Compose）

```bash
docker compose up --build
```

- 页面：http://localhost:8080
- API：http://localhost:8000（健康检查 `/api/health`）

宿主端口可用环境变量覆盖：

```bash
WEB_PORT=9090 API_PORT=9000 docker compose up --build
```

数据保存在 Docker 卷 `api-data`（容器内 `/data/leafcards.db`）。

## 一次性自检 verify

不依赖 Docker（需要本机 `python3`、`node`/`npm`）：

```bash
./scripts/verify
```

它会依次：

1. 准备 Python 虚拟环境并安装依赖；
2. 运行后端全部测试（核心算法 + API：**最优、并列、锁定无解、其他无解、未知值**）；
3. 前端类型检查与生产构建；
4. 启动一个临时 API 进程，做真实 HTTP **接口冒烟**（建卡、最优树、编辑过期、
   重载一致、两类无解、快照、4–20 张卡校验）。

全绿时最后一行输出：`✅ verify 全部通过`。

## 本地开发（不用 Docker）

```bash
# 后端
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
cd backend
DB_PATH=$PWD/leafcards.db ../.venv/bin/uvicorn app.main:app --reload --port 8000

# 前端（另开一个终端；/api 自动代理到 8000）
cd web
npm install
VITE_API_TARGET=http://localhost:8000 npm run dev
```

后端测试：`cd backend && ../.venv/bin/pytest -q`
前端构建：`cd web && npm run build`

## 算法说明（`backend/app/core/tree.py`）

### 1. 什么特征可以当节点？

对候选卡片集合 S 和属性 a，只有满足全部条件才允许使用：

1. S 里每张卡在 a 上的值都**已知**（不能有「未知」）；
2. S 中 a 为真、为假的两组**都非空**（必须真的把卡片分成两边）。

### 2. 最优树（动态规划）

对每个可达子集做记忆化 DP，选根属性使以下目标依次最小：

1. **最大叶深**（最坏情况下要问几个问题）；
2. **叶深总和**（所有卡片的问题数之和，平均更省事）；
3. 仍并列时，比较树的**属性编号前序序列**（先访问假子树、再真子树），
   取数值字典序最小者——结果因此完全确定。

叶子深度记 0；子集只有一张卡时即为叶子。

### 3. 两类无解（绝不返回残缺树）

- **锁定无解 `no_lock`**：根集合上有合法特征，但无论怎样锁定，走到某个候选集时
  会卡死。接口返回一条**阻断路径**（从根起的假/真回答序列 + 每步的节点属性），
  按「路径长度最短；长度相同按假先于真的字典序；再按属性编号序列」取最小，
  并对终点卡片集**逐属性**说明阻断原因。
- **其他无解 `inseparable`**：从「至少含两张卡、且没有任何合法二分属性」的子集中，
  取**基数最小、编号升序字典序最小**的一组；同样逐属性给出原因：
  - `unknown`：组里某张卡该特征还是「？」，不能拿来分组；
  - `same`：组内所有卡该特征同为真或同为假，分不出两边。

页面据此提示孩子：再去观察补全「？」，或增加一个能区分它们的新特征。

## HTTP 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/health` | 健康检查 |
| POST | `/api/projects` | 新建辨认卡（对象 4–20 个、属性 1–20 个，编号为唯一正整数） |
| GET | `/api/projects` | 列出全部 |
| GET | `/api/projects/{id}` | 读取一个（结果不新鲜时 `result` 为 `null`） |
| PUT | `/api/projects/{id}` | 编辑：输入版本 +1，**旧树过期** |
| DELETE | `/api/projects/{id}` | 删除（级联删除快照） |
| POST | `/api/projects/{id}/compute` | 计算辨认树，**保存结果并存快照** |
| GET | `/api/projects/{id}/snapshots` | 快照列表 |
| GET | `/api/snapshots/{id}` | 读取某次快照（当时的输入 + 结果） |

单元格放在 `cells`，键为 `"对象编号:属性编号"`，值为 `"true" | "false" | "unknown"`；
未登记的单元格按「未知」处理。**已经声明、但还没有任何观察单元的特征也会出现在无解原因里**
（对那组卡片全部是「还没观察」）。

### 路径锁定（预定制作步骤）

`locks` 是一组「某条回答路线上必须问哪个特征」的预定步骤：

```json
"locks": [
  { "path": [],                 "attributeId": 2 },
  { "path": ["true"],           "attributeId": 5 },
  { "path": ["true", "false"],  "attributeId": 1 }
]
```

* `path` 从根开始、由 `"true"`/`"false"` 组成；空数组表示锁定**根问题**；
* 被锁节点只能使用指定特征：该特征仍必须是合法二分属性
  （候选卡全部已知、真假两组都非空），否则返回 `no_lock`，
  并在 `violatedLock` 指出是哪条预定步骤无法满足，阻断路径终点解释原因；
* 未锁定的节点仍按（最大叶深、叶深总和、属性编号前序）自动选最优。

### 结果示例

成功：

```json
{
  "status": "ok",
  "tree": {
    "type": "question", "attributeId": 1,
    "false": { "type": "question", "attributeId": 2 },
    "true":  { "type": "leaf", "objectId": 1 }
  },
  "score": { "maxDepth": 2, "sumDepth": 8, "preorder": [1, 2, 4] }
}
```

锁定无解：

```json
{
  "status": "no_lock",
  "blockingPath": [{ "attributeId": 1, "branch": "false" }],
  "terminalObjectIds": [3, 4],
  "reasons": [
    { "attributeId": 2, "reason": "unknown", "objectIds": [3] },
    { "attributeId": 3, "reason": "same", "value": "false", "objectIds": [3, 4] }
  ]
}
```

## 快照与一致性

- 每次「算出辨认树」都写一行 `snapshots`：**同时固化当时的矩阵和结果**；
- 任何编辑都会让 `input_version` 加一、清空当前结果；
  读取项目时 `resultFresh=false`、`result=null`，页面明确提示旧树已过期；
- 重新计算后结果与新输入一致（`resultVersion == inputVersion`），旧快照仍保留可回看。

## 页面怎么用

1. 「用示例开始」或「空白新卡」，给辨认卡起名；
2. 维护对象卡和观察特征（编号自动分配、唯一）；
3. 点矩阵格子在 **真 → 假 → ？** 之间循环；
4. 「保存并算出辨认树」：
   - 成功后可以 **🚶 逐问试走**（随时回退、重走，并显示当前还剩哪些卡片），
     或查看 **🌳 整棵树**；
   - 分不开时显示阻断路径/最小冲突组和逐属性原因；
5. 每次计算都在「📸 保存过的计算快照」里留档。

## 目录结构

```
.
├── backend/            FastAPI + SQLAlchemy + SQLite
│   ├── app/
│   │   ├── core/tree.py    # 最优树 DP、两类无解诊断
│   │   ├── main.py         # API 路由
│   │   ├── models.py       # Project / Snapshot 模型
│   │   ├── schemas.py      # 校验（4–20 张卡、唯一正整数编号…）
│   │   └── service.py
│   └── tests/              # pytest：算法 12 例 + API 9 例
├── web/                Vue 3 + TypeScript + Vite
│   └── src/components/     # 矩阵编辑、整树、逐问试走、结果面板
├── scripts/verify      # 一次性：测试 + 构建 + 接口冒烟
└── docker-compose.yml
```
