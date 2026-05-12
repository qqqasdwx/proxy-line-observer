# 使用 sing-box 提供代理线路

本项目不会运行 sing-box。本页只用于说明如何让 sing-box 在外部提供 HTTP/SOCKS 代理入口，然后把这些入口填入 `data/config/lines.csv` 或配置页面。

下面示例暴露两个本地 mixed 代理端口：

- `7890` -> `line-a-out`
- `7891` -> `line-b-out`

示例出站是假的，运行前必须替换为你自己的节点信息。

## 最小 sing-box 配置

在运行 sing-box 的机器上创建 `config.json`：

```json
{
  "log": {
    "level": "info"
  },
  "inbounds": [
    {
      "type": "mixed",
      "tag": "line-a-in",
      "listen": "0.0.0.0",
      "listen_port": 7890
    },
    {
      "type": "mixed",
      "tag": "line-b-in",
      "listen": "0.0.0.0",
      "listen_port": 7891
    }
  ],
  "outbounds": [
    {
      "type": "shadowsocks",
      "tag": "line-a-out",
      "server": "203.0.113.10",
      "server_port": 8388,
      "method": "aes-128-gcm",
      "password": "REPLACE_WITH_LINE_A_PASSWORD"
    },
    {
      "type": "shadowsocks",
      "tag": "line-b-out",
      "server": "203.0.113.20",
      "server_port": 8388,
      "method": "aes-128-gcm",
      "password": "REPLACE_WITH_LINE_B_PASSWORD"
    },
    {
      "type": "direct",
      "tag": "direct"
    }
  ],
  "route": {
    "rules": [
      {
        "inbound": "line-a-in",
        "action": "route",
        "outbound": "line-a-out"
      },
      {
        "inbound": "line-b-in",
        "action": "route",
        "outbound": "line-b-out"
      }
    ],
    "final": "direct"
  }
}
```

## Docker 运行

```bash
mkdir -p ~/proxy-lines/sing-box
cd ~/proxy-lines/sing-box
# 将上面的配置保存为 ./config.json

docker run -d \
  --name sing-box-proxy-lines \
  --restart unless-stopped \
  -p 7890:7890 \
  -p 7891:7891 \
  -v "$PWD/config.json:/etc/sing-box/config.json:ro" \
  ghcr.io/sagernet/sing-box:latest \
  run -c /etc/sing-box/config.json
```

## 接入本项目

如果 sing-box 和本项目运行在同一台 Docker 宿主机：

```csv
line,proxy_url,enabled
line_a,http://host.docker.internal:7890,true
line_b,socks5h://host.docker.internal:7891,true
```

如果 sing-box 运行在另一台机器，把 `host.docker.internal` 换成那台机器的局域网 IP。

## 连通性测试

```bash
curl -x http://127.0.0.1:7890 -I https://www.google.com/generate_204
curl -x socks5h://127.0.0.1:7891 -I https://www.google.com/generate_204
```

参考：

- sing-box Docker 安装：<https://sing-box.sagernet.org/installation/docker/>
- sing-box mixed inbound：<https://sing-box.sagernet.org/configuration/inbound/mixed/>
- sing-box 路由规则：<https://sing-box.sagernet.org/configuration/route/rule/>
