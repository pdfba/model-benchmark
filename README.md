# 模型性能与精度压测

根据 `design.mk` 设计实现的压测软件：指定模型服务接口、测试工具与测试条件后，自动执行性能压测并生成报告。

## 技术栈

- **前端**: Vue 3 + Vite
- **后端**: Python + FastAPI
- **数据库**: SQLite3

## 快速开始

### 1. 后端

```bash
cd backend
python3 -m venv /opt/venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

服务默认运行在 http://127.0.0.1:8900

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认运行在 http://localhost:8173，开发环境下会代理 `/api` 到后端。

**Linux 下若报错 `Cannot find module @rollup/rollup-linux-x64-gnu`**（npm 对可选依赖的 bug），在 `frontend` 目录执行：

```bash
rm -rf node_modules package-lock.json
npm install
```

若仍失败，可先显式安装当前平台的原生包再装依赖：

```bash
npm install @rollup/rollup-linux-x64-gnu --save-optional
npm install
```

### 3. 使用说明

1. 在「测试配置」中填写：模型服务地址、测试工具（当前仅支持 aiakperf）、输入/输出 Token 长度、TTFT(ms)、TPOT(ms)。
2. 点击「开始测试」，后端会执行压测并返回结果。
3. 在「压测报告」中查看关键指标与原始输出。
4. 点击「保存到数据库」可将本次结果写入 SQLite。

**说明**：若本机未安装 `aiakperf`，后端会返回模拟输出，便于本地联调与演示。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/test` | 执行性能测试，请求体见下方 |
| POST | `/api/results` | 将测试结果写入数据库 |
| GET  | `/api/results` | 获取历史测试结果列表 |

**POST /api/test 请求体示例**

```json
{
  "model_url": "https://api.example.com/v1",
  "test_tool": "aiakperf",
  "input_tokens": 16384,
  "output_tokens": 339,
  "ttft_ms": 16.7,
  "tpot_ms": 0.055
}
```

## 项目结构

```
benchmark/
├── design.mk          # 设计说明
├── README.md
├── backend/
│   ├── main.py        # FastAPI 应用与接口
│   ├── database.py    # SQLite 初始化与读写
│   ├── parser.py      # 解析 aiakperf 输出
│   ├── runner.py      # 调用 aiakperf 执行压测
│   ├── requirements.txt
│   └── benchmark.db   # 运行后生成的数据库文件
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.js
        └── App.vue
```
