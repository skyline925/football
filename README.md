# 足球数据爬虫 - Render 部署指南

## 部署方式

本项目使用 **Render Private Services**（原 Web Service），而非 Cron Job，
因为爬虫需要保持长时间运行（守护进程模式）。

## Render 部署步骤

### 第一步：上传代码到 GitHub

1. 在 GitHub 创建私有仓库，例如 `football-scraper`
2. 将本目录内容上传到仓库（**不要上传 `.env` 文件**）

```bash
cd football-scraper
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/football-scraper.git
git push -u origin main
```

### 第二步：在 Render 创建 Private Service

1. 访问 [dashboard.render.com](https://dashboard.render.com)
2. 点击 **New → Private Service**
3. 连接你的 GitHub 仓库
4. 配置如下：

| 配置项 | 值 |
|--------|-----|
| **Name** | `football-scraper` |
| **Region** | Singapore（离中国最近） |
| **Branch** | `main` |
| **Runtime** | `Docker` |
| **Instance Type** | `Free`（免费额度足够） |
| **Start Command** | `python main.py` |
| **Health Check Path** | `/`（默认） |

### 第三步：设置环境变量（在 Render 控制台）

进入 Service → Environment → Add Environment Variable：

```
DATABASE_URL = postgresql://neondb_owner:xxx@ep-xxx/neondb?sslmode=require
SCRAPER_INTERVAL_MINUTES = 10
HIGH_FREQUENCY_INTERVAL_MINUTES = 5
START_TIME = 10:00
END_TIME = 23:00
MINIMAX_API_KEY = sk-cp-xxx
MINIMAX_MODEL = minimax-2.7
```

> ⚠️ `DATABASE_URL` 请从 Neon 控制台获取最新连接字符串。

### 第四步：部署

1. 点击 **Create Private Service**
2. Render 会自动构建 Docker 镜像并启动
3. 查看 Logs 确认爬虫正常运行：

```
爬虫调度器已启动...
```

## Render 免费版限制

- **免费实例睡眠政策**：如果 15 分钟无流量，Render 会休眠。
- **解决方案**：由于本爬虫是守护进程（`while True` + `schedule`），
  会在后台持续运行，不会触发睡眠。但建议在 `main.py` 中加入心跳日志
  以便 Render 识别为活跃服务。

## 监控

- **Logs**：Render Dashboard → Service → Logs
- **若无输出**：检查环境变量是否正确、Dockerfile 是否能正常构建

## 更新部署

代码更新后，在 Render 控制台点击 **Manual Deploy → Deploy latest commit**。

## 本地测试

```bash
cd football-scraper
cp .env.example .env  # 手动创建并填写环境变量
pip install -r requirements.txt
python main.py
```
