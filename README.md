# 宝塔面板-Docker应用商店官方仓库 | BT Panel - Docker App Store Official Repository

[中文](#中文) | [English](#english)

---

## 中文

本仓库用于宝塔面板 Docker 应用商店的官方应用收录与维护。

- 反馈与交流：提交 Issues 或加入 QQ 群 662047798
- 欢迎 PR：提交你的 Docker 应用至应用商店，共建生态

### 快速开始：如何提交一个应用
1. 在 `apps/<your-app-name>/` 下创建目录，并放置：
    - `app.json`（应用元信息）
    - `ico-dkapp_{appname}.png`（100x100 png）
    - 与 `app.json.appname` 对应的版本目录,每个目录包含：
        - `docker-compose.yml`
        - `.env`
2. 编写 `app.json`（字段规则见下文）
3. 编写 `docker-compose.yml` 与 `.env`，确保变量一致并可启动
4. 本地自测通过后提交 PR

### 自动更新版本工具 (update_versions.py)

自动从 Docker Hub 获取并更新应用版本信息的 Python 脚本。

#### 功能特性
- ✅ 自动从 Docker Hub API 获取最新镜像版本
- ✅ 支持所有标签类型（数字版本、latest、alpine、bookworm 等）
- ✅ 按最新更新时间排序版本
- ✅ 多线程并行处理，大幅提升速度（2-97x faster）
- ✅ 实时进度显示，自动原地更新状态
- ✅ 支持版本数量限制

#### 基本用法

```bash
# 更新所有应用（测试模式）
python3 update_versions.py --dry-run

# 更新所有应用（实际更新）
python3 update_versions.py

# 更新特定应用
python3 update_versions.py redis mysql nginx

# 使用并行处理加速（推荐）
python3 update_versions.py --workers 10

# 查看详细调试信息
python3 update_versions.py --debug redis
```

#### 命令行选项

```
用法: update_versions.py [-h] [--dry-run] [--debug] [--apps-dir APPS_DIR]
                         [--max-tags MAX_TAGS]
                         [--max-versions-per-major N]
                         [--max-major-versions N]
                         [--workers N]
                         [apps ...]

参数:
  apps                   要更新的应用名称（留空则更新所有应用）
  
  --dry-run             显示将要更新的内容但不实际修改文件
  --debug               启用详细调试输出
  --apps-dir DIR        应用目录路径（默认: apps）
  --max-tags N          从 Docker Hub 获取的最大标签数（默认: 100）
  --max-versions-per-major N
                        每个主版本保留的最大子版本数（默认: 无限制）
  --max-major-versions N
                        保留的最大主版本数（默认: 无限制）
  --workers N           并行处理的线程数（默认: 1）
```

#### 性能优化建议

使用多线程可显著提升更新速度：

| 应用数量 | 推荐 Workers | 预计时间 (308 apps) |
|---------|-------------|-------------------|
| 小批量   | 5           | 测试 5 apps: ~7s   |
| 中等批量 | 10          | 全部: ~150s (2.5min) |
| 大批量   | 15-20       | 全部: ~130s (2min)  |

> **提示**: Docker Hub 有 API 限速，建议不超过 20 workers

**示例**：
```bash
# 小批量更新（5 个应用）
python3 update_versions.py --workers 5 redis mysql nginx adminer alist

# 中等批量更新（20 个应用）
python3 update_versions.py --workers 10

# 大批量更新（所有应用）
python3 update_versions.py --workers 20

# 限制版本数量（推荐用于生产环境）
python3 update_versions.py --workers 10 \
  --max-versions-per-major 20 \
  --max-major-versions 5
```

#### 技术特性

- **真正并行**: 使用 Semaphore 实现多个 API 请求同时执行
- **智能并发控制**: 根据 workers 数量动态调整并发限制（最多 10 个同时请求）
- **速率限制**: 150ms 最小请求间隔 + 随机 jitter，避免触发 Docker Hub 429 错误
- **自动重试**: 遇到 429 错误自动指数退避重试（3s, 6s, 12s）
- **线程安全**: 所有操作都是线程安全的
- **实时进度**: TTY 环境下自动原地更新进度，非 TTY 环境自动降级到逐行输出

### 目录结构示例
```
apps/
└── wordpress/
    ├── app.json
    ├── ico-dkapp_wordpress.png
    └── wordpress/
        ├── docker-compose.yml
        └── .env
```

### 图标与命名
- `ico-dkapp_${appname}.png`：100x100 像素、png 格式
- `appname` 使用小写中划线或下划线风格，避免空格与大写
- 目录名与 `appname` 建议保持一致

### 质量检查（提交前自检）
- 目录包含 `app.json`、`ico-dkapp_${appname}.png`、对应版本目录与必要文件
- `.env` 至少包含：`HOST_IP`、`CPUS`、`MEMORY_LIMIT`、`APP_PATH` 与自定义变量
- `docker-compose.yml` 使用 `.env` 的大写变量，端口按 `${HOST_IP}:${PORT}` 规范
- `labels.createdBy: "bt_apps"` 存在
- 依赖声明（如有）合理且与说明一致
- 说明链接（`home`、`help`）可访问

### 提交流程（PR 要求）
- 确保能在标准 Docker 环境下拉起并运行
- 遵循本文规范
- PR 描述中附：应用简介、镜像版本、主要环境变量说明、是否有依赖
- 变更图标、文档与 compose 时，同步更新 `app.json` 与版本目录

---

## English

This repository is used for the official application collection and maintenance of the BT Panel Docker App Store.

- Feedback & Communication: Submit Issues or join QQ group 662047798
- Welcome PRs: Submit your Docker applications to the app store and build the ecosystem together

### Quick Start: How to Submit an Application
1. Create a directory under `apps/<your-app-name>/` and place:
    - `app.json` (application metadata)
    - `ico-dkapp_{appname}.png` (100x100 png)
    - Version directories corresponding to `app.json.appname`, each containing:
        - `docker-compose.yml`
        - `.env`
2. Write `app.json` (field rules below)
3. Write `docker-compose.yml` and `.env`, ensure variables are consistent and can start
4. Submit PR after local testing passes

### Automatic Version Update Tool (update_versions.py)

Python script that automatically fetches and updates application version information from Docker Hub.

#### Features
- ✅ Automatically fetch latest image versions from Docker Hub API
- ✅ Support all tag types (numeric versions, latest, alpine, bookworm, etc.)
- ✅ Sort versions by last update time
- ✅ Multi-threaded parallel processing for massive speed improvements (2-97x faster)
- ✅ Real-time progress display with in-place updates
- ✅ Support version count limits

#### Basic Usage

```bash
# Update all apps (dry run mode)
python3 update_versions.py --dry-run

# Update all apps (live update)
python3 update_versions.py

# Update specific apps
python3 update_versions.py redis mysql nginx

# Use parallel processing for speed (recommended)
python3 update_versions.py --workers 10

# View detailed debug information
python3 update_versions.py --debug redis
```

#### Command Line Options

```
Usage: update_versions.py [-h] [--dry-run] [--debug] [--apps-dir APPS_DIR]
                         [--max-tags MAX_TAGS]
                         [--max-versions-per-major N]
                         [--max-major-versions N]
                         [--workers N]
                         [apps ...]

Arguments:
  apps                   App names to update (empty for all apps)
  
  --dry-run             Show what would be updated without making changes
  --debug               Enable verbose debug output
  --apps-dir DIR        Apps directory path (default: apps)
  --max-tags N          Maximum tags to fetch from Docker Hub (default: 100)
  --max-versions-per-major N
                        Maximum sub-versions to keep per major version (default: unlimited)
  --max-major-versions N
                        Maximum major versions to keep (default: unlimited)
  --workers N           Number of parallel worker threads (default: 1)
```

#### Performance Optimization Tips

Using multi-threading significantly improves update speed:

| Batch Size | Recommended Workers | Expected Time (308 apps) |
|------------|---------------------|--------------------------|
| Small      | 5                   | Test 5 apps: ~7s         |
| Medium     | 10                  | All: ~150s (2.5min)      |
| Large      | 15-20               | All: ~130s (2min)        |

> **Note**: Docker Hub has API rate limits, recommend not exceeding 20 workers

**Examples**:
```bash
# Small batch update (5 apps)
python3 update_versions.py --workers 5 redis mysql nginx adminer alist

# Medium batch update (20 apps)
python3 update_versions.py --workers 10

# Large batch update (all apps)
python3 update_versions.py --workers 20

# Limit version count (recommended for production)
python3 update_versions.py --workers 10 \
  --max-versions-per-major 20 \
  --max-major-versions 5
```

#### Technical Features

- **True Parallelism**: Uses Semaphore to execute multiple API requests simultaneously
- **Smart Concurrency Control**: Dynamically adjusts concurrency limit based on worker count (max 10 concurrent requests)
- **Rate Limiting**: 150ms minimum request interval + random jitter to prevent Docker Hub 429 errors
- **Automatic Retry**: Exponential backoff retry on 429 errors (3s, 6s, 12s)
- **Thread-Safe**: All operations are thread-safe
- **Real-time Progress**: Automatic in-place progress updates in TTY environments, automatically degrades to line-by-line output in non-TTY

### Directory Structure Example
```
apps/
└── wordpress/
    ├── app.json
    ├── ico-dkapp_wordpress.png
    └── wordpress/
        ├── docker-compose.yml
        └── .env
```

### Icons and Naming
- `ico-dkapp_${appname}.png`: 100x100 pixels, png format
- `appname` use lowercase with hyphens or underscores, avoid spaces and uppercase
- Directory name should match `appname`

### Quality Checklist (Before Submission)
- Directory contains `app.json`, `ico-dkapp_${appname}.png`, version directories and necessary files
- `.env` must include at least: `HOST_IP`, `CPUS`, `MEMORY_LIMIT`, `APP_PATH` and custom variables
- `docker-compose.yml` uses uppercase variables from `.env`, ports follow `${HOST_IP}:${PORT}` format
- `labels.createdBy: "bt_apps"` exists
- Dependency declarations (if any) are reasonable and consistent with documentation
- Help links (`home`, `help`) are accessible

### Submission Process (PR Requirements)
- Ensure it can be pulled up and run in a standard Docker environment
- Follow specifications in this document
- Include in PR description: app introduction, image version, main environment variables, dependencies
- When changing icons, documentation and compose files, update `app.json` and version directories accordingly