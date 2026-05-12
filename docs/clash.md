# 使用 Clash/Mihomo 提供代理线路

本项目不会运行 Clash/Mihomo。本页只用于说明如何让 Mihomo 在外部提供 HTTP/SOCKS 代理入口，然后把这些入口填入 `data/config/lines.csv` 或配置页面。

下面示例暴露两个本地 mixed 代理端口：

- `7890` -> `line-a-node`
- `7891` -> `line-b-node`

示例节点是假的，运行前必须替换为你自己的节点信息。

## 最小 Mihomo 配置

在运行 Mihomo 的机器上创建 `config.yaml`：

```yaml
allow-lan: true
bind-address: "*"
mode: rule
log-level: info

proxies:
  - name: line-a-node
    type: ss
    server: 203.0.113.10
    port: 8388
    cipher: aes-128-gcm
    password: REPLACE_WITH_LINE_A_PASSWORD

  - name: line-b-node
    type: ss
    server: 203.0.113.20
    port: 8388
    cipher: aes-128-gcm
    password: REPLACE_WITH_LINE_B_PASSWORD

proxy-groups:
  - name: line-a-fixed
    type: select
    proxies:
      - line-a-node

  - name: line-b-fixed
    type: select
    proxies:
      - line-b-node

listeners:
  - name: line-a
    type: mixed
    listen: 0.0.0.0
    port: 7890
    proxy: line-a-fixed

  - name: line-b
    type: mixed
    listen: 0.0.0.0
    port: 7891
    proxy: line-b-fixed

rules:
  - MATCH,DIRECT
```

Mihomo 的 `listeners` 语法可能随版本变化。如果镜像不接受上面的配置，请按你使用的 Mihomo 版本调整。

## Docker 运行

```bash
mkdir -p ~/proxy-lines/mihomo
cd ~/proxy-lines/mihomo
# 将上面的配置保存为 ./config.yaml

docker run -d \
  --name mihomo-proxy-lines \
  --restart unless-stopped \
  -p 7890:7890 \
  -p 7891:7891 \
  -v "$PWD/config.yaml:/root/.config/mihomo/config.yaml:ro" \
  metacubex/mihomo:latest \
  -f /root/.config/mihomo/config.yaml
```

## 接入本项目

如果 Mihomo 和本项目运行在同一台 Docker 宿主机：

```csv
line,proxy_url,enabled
line_a,http://host.docker.internal:7890,true
line_b,socks5h://host.docker.internal:7891,true
```

如果 Mihomo 运行在另一台机器，把 `host.docker.internal` 换成那台机器的局域网 IP。

## 连通性测试

```bash
curl -x http://127.0.0.1:7890 -I https://www.google.com/generate_204
curl -x socks5h://127.0.0.1:7891 -I https://www.google.com/generate_204
```

参考：

- Mihomo listeners 文档：<https://wiki.metacubex.one/en/config/inbound/listeners/>
