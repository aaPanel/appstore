CONFIG_FILE="/mnt/tcdn/config.properties"

# 检查配置文件是否挂载
if [ ! -f "$CONFIG_FILE" ]; then
  echo "配置文件不存在或未挂载: $CONFIG_FILE"
  exit 1
fi

# 创建新的配置内容
echo "开始更新配置文件: $CONFIG_FILE"

cat > "$CONFIG_FILE" <<EOF
translate.tcdn.api.html.url=https://translate.apistore.huaweicloud.com/html
translate.tcdn.api.html.key=${TCDN_HTML_KEY:-default_html_key}
translate.tcdn.api.jsParser.url=https://jse.apistore.huaweicloud.com/jsParser
translate.tcdn.api.jsParser.key=${TCDN_JSPARSER_KEY:-default_jsParser_key}
token=${TCDN_TOKEN:-default_token}
server.port=80
EOF

# 打印更新完成日志
echo "配置文件更新完成:"
cat "$CONFIG_FILE"

