# 应用模板说明

本说明基于当前仓库 apps/* 的实际规范沉淀，指导你新增一个应用目录与对应的 app.json、版本目录与 compose/.env 等文件，确保可被应用商店正确解析与渲染。

## 目录结构
```
.apps/appname                   # 应用目录（英文名，与 app.json 中 appname 一致）
├── app.json                    # 应用的元信息（核心配置）
├── ico-dkapp_${appname}.png    # 应用图标，100x100 像素，png 格式
└── appname                     # 该app的英文名目录（与 app.json 中 appname 一致）
    ├── docker-compose.yml
    └── .env
```

## app.json 字段模板与说明
下面给出一个带注释的模板（示例字段并非要求全部保留，请按需取舍，但关键字段需存在）。
```
{
  "appid": 199,                            # 根据pkg/apps.json 最后的 ID 顺序填写
  "appname": "alist",                      # 英文应用名（目录名同名）
  "apptitle": "Alist",                     # 展示标题
  "apptype": "Storage",                    # 应用类型（见下方可选列表）
  "appTypeCN": "存储/网盘",                 # 类型中文名（与 apptype 对应）
  "appversion": [                          # 版本定义（主/小版本）
    { "m_version": "latest", "s_version": [] },
    { "m_version": "3",      "s_version": ["42.0"] }
  ],
  "appdesc": "一个支持多存储的文件列表程序...",  # 简介
  "appstatus": 1,                           # 1 显示，0 隐藏
  "home": "",                               # 官网或 GitHub
  "help": "https://...",                    # 使用文档
  "updateat": 1752027587,                   # 更新时间戳（秒）
  "reuse": true,                            # 预留配置，一般为 true
  "cpu": 0,                                 # CPU 核心数，0为不限制
  "mem": 0,                                 # 内存，0为不限制
  "disk": 10240,                            # 预留配置
  "depend": null,                           # 依赖数据库应用。也可为数组，见下方示例  可参考应用:nextcloud、wordpress
  # "depend": [
  #   {
  #     "appname": ["mysql"],
  #     "apptype": "Database",
  #     "appTypeCN": "数据库服务",
  #     "appDesc": "需安装 Docker 应用的 MySQL",
  #     "appversion": ["5", "8", "9"]
  #   }
  # ],

  "field": [                                  # 创建面板表单字段（用于生成 .env 的值）
    { "attr": "domain",         "name": "域名",         "type": "textarea", "default": "",     "suffix": "浏览器访问的域名,非必填", "unit": "" },
    { "attr": "allow_access",   "name": "允许外部访问", "type": "checkbox", "default": true,  "suffix": "允许直接通过主机IP+端口访问",      "unit": "" },
    { "attr": "cpus",           "name": "cpu核心数限制", "type": "number",   "default": 0,     "suffix": "0为不限制,最大可用核心数为: ", "unit": "" },
    { "attr": "memory_limit",    "name": "内存限制",     "type": "number",   "default": 0,     "suffix": "0为不限制,最大可用内存为: ",   "unit": "" }
    # 其他自定义字段，如端口、URL、密码、GPU开关等：
    # { "attr": "web_http_port",  "name": "Web端口",     "type": "number",   "default": 8080,  "suffix": "", "unit": "" },
    # { "attr": "gpu",            "name": "开启GPU",     "type": "checkbox", "default": false, "suffix": "9.5.0+ 面板可用", "unit": "" }
  ],

  "env": [                                    # 环境变量映射与类型（会映射为 .env 中的大写KEY）
    { "key": "app_path",       "type": "path",    "default": null, "desc": "应用数据目录" },
    { "key": "host_ip",        "type": "string",  "default": null, "desc": "主机IP" },
    { "key": "cpus",           "type": "number",  "default": null, "desc": "CPU核心数限制" },
    { "key": "memory_limit",   "type": "number",  "default": null, "desc": "内存大小限制" }
    # 常见类型还包括：
    # port, password, username, url, db_host, text,
    # defaultUserName, defaultPassWord 等
    # 例如：
    # { "key": "web_http_port",    "type": "port",     "default": null, "desc": "Web端口" },
    # { "key": "admin_password",   "type": "password", "default": null, "desc": "管理员密码" },
    # { "key": "api_base_url",     "type": "url",      "default": null, "desc": "API地址" }
  ],

  "volumes": {                                # 卷声明：用于提示需挂载的宿主机路径/文件 建议都放在一个/data目录下 的子目录 方便备份迁移
    "data": { "type": "path", "desc": "数据目录" },
    "conf": { "type": "file", "desc": "配置文件" }
  },
}
```

说明要点：
- `field[].attr` 与 `env[].key` 一一对应（env 中会变成大写写入 .env）。
- `env[].type` 决定了面板的校验与渲染：
  - 端口使用 `port`（会做占用检测），路径使用 `path`，字符串使用 `string`，数字使用 `number`；
- `depend` 可声明依赖应用（如数据库），以便引导用户先安装依赖，可参考应用 nextcloud、wordpress。

### apptype 与 appTypeCN 对照
- BuildWebsite | 建站
- Database     | 数据库
- Storage      | 存储/网盘
- Tools        | 实用工具
- Middleware   | 中间件
- AI           | AI/大模型
- Media        | 多媒体
- Email        | 邮件/邮局
- DevOps       | DevOps
- System       | 系统

## .env 规范
以下四项为必填：`HOST_IP`、`CPUS`、`MEMORY_LIMIT`、`APP_PATH`。此外，`app.json` 中 `env[].key` 会被转为大写写入 .env（如 `web_http_port` → `WEB_HTTP_PORT`）。
```
# 自定义变量（示例）
ALIST_WEB_PORT=
S3_SERVER_PORT=

# 必填通用项
HOST_IP=            # 必填
CPUS=               # 必填
MEMORY_LIMIT=       # 必填
APP_PATH=           # 必填
```
- `HOST_IP` 与是否勾选 `allow_access` 联动：
  - 允许外部访问时通常为 `0.0.0.0`；
  - 否则可设为 `127.0.0.1` 仅本机映射。

## docker-compose.yml 规范与示例
不推荐使用 `container_name`（可能影响应用状态识别），可直接使用服务名。服务较多（>5）时，建议自建网络。

```
services:
  alist:
    image: xhofe/alist:v3.42.0
    deploy:
      resources:
        limits:
          cpus: ${CPUS}                      # CPU 限制
          memory: ${MEMORY_LIMIT}            # 内存限制
    environment:
      - PUID=0
      - PGID=0
      - UMASK=022
    ports:
      - ${HOST_IP}:${ALIST_WEB_PORT}:5244    # 端口映射建议形如 ${HOST_IP}:${PORT}
      - ${HOST_IP}:${S3_SERVER_PORT}:5426
    restart: always
    volumes:
      - ${APP_PATH}/data:/opt/alist/data     # 无特殊需求，建议统一挂载到 ${APP_PATH}/ 子目录
      - ${APP_PATH}/mnt:/mnt/data
    labels:
      createdBy: "bt_apps"                  # 必填标签
    # networks:
    #   - baota_net

# networks:
#   baota_net:
#     external: true
```

建议：
- 端口映射统一采用 `${HOST_IP}:${<YOUR_PORT>}:<container_port>` 便于控制访问范围；
- 所有数据/配置尽量挂载到 `${APP_PATH}` 之下，便于备份迁移；
- 必须包含 `labels.createdBy: "bt_apps"`。

## 校验清单（自检）
- 目录下存在 `app.json`、`ico-dkapp_${appname}.png`、与 `appname` 对应的版本目录；
- `.env` 至少包含 `HOST_IP`、`CPUS`、`MEMORY_LIMIT`、`APP_PATH`，以及应用自定义的变量；
- `docker-compose.yml` 使用了 `.env` 中的大写变量，映射端口遵循 `${HOST_IP}:${PORT}` 规范；
- `labels.createdBy: "bt_apps"` 已设置；
- 如声明了依赖，`depend` 结构正确且版本范围合理；
- 图标尺寸与格式正确，应用简介与文档链接可用。
