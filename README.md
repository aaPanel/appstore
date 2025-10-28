# 宝塔面板-Docker应用商店官方仓库

本仓库用于宝塔面板 Docker 应用商店的官方应用收录与维护。

- 反馈与交流：提交 Issues 或加入 QQ 群 662047798
- 欢迎 PR：提交你的 Docker 应用至应用商店，共建生态

## 快速开始：如何提交一个应用
1. 在 `apps/<your-app-name>/` 下创建目录，并放置：
   - `app.json`（应用元信息）
   - `ico-dkapp_{appname}.png`（100x100 png）
   - 与 `app.json.appname` 对应的版本目录,每个目录包含：
     - `docker-compose.yml`
     - `.env`
2. 编写 `app.json`（字段规则见下文，完整模板见 `template.md`）
3. 编写 `docker-compose.yml` 与 `.env`，确保变量一致并可启动
4. 本地自测通过后提交 PR

建议先阅读：[template.md](template.md),仓库规范模板，含完整示例与最佳实践）

## 目录结构示例
```
apps/
└── wordpress/
    ├── app.json
    ├── ico-dkapp_wordpress.png
    └── wordpress/
        ├── docker-compose.yml
        └── .env
```

## 图标与命名
- `ico-dkapp_${appname}.png`：100x100 像素、png 格式
- `appname` 使用小写中划线或下划线风格，避免空格与大写
- 目录名与 `appname` 建议保持一致

## 质量检查（提交前自检）
- 目录包含 `app.json`、`ico-dkapp_${appname}.png`、对应版本目录与必要文件
- `.env` 至少包含：`HOST_IP`、`CPUS`、`MEMORY_LIMIT`、`APP_PATH` 与自定义变量
- `docker-compose.yml` 使用 `.env` 的大写变量，端口按 `${HOST_IP}:${PORT}` 规范
- `labels.createdBy: "bt_apps"` 存在
- 依赖声明（如有）合理且与说明一致
- 说明链接（`home`、`help`）可访问

## 提交流程（PR 要求）
- 确保能在标准 Docker 环境下拉起并运行
- 遵循本文与 `template.md` 规范
- PR 描述中附：应用简介、镜像版本、主要环境变量说明、是否有依赖
- 变更图标、文档与 compose 时，同步更新 `app.json` 与版本目录

更多细节、示例与最佳实践请参考：`template.md`。祝开发顺利！
