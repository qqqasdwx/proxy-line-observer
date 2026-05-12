# 架构说明

## 边界

`proxy-line-observer` 只把代理地址作为对比单位。一条线路由 `line` 标识，并通过 `proxy_url` 访问。项目不运行、不解析 Clash、Mihomo、sing-box、节点、订阅、协议、路由规则或供应商细节。

这个边界让观测器可以复用于不同代理软件。外部代理软件负责节点配置和路由，配置页面负责文件配置，Telegraf 负责调度，探测脚本负责执行请求并输出指标。

## Compose 版本

`docker-compose.yml` 面向用户使用，会拉取 GHCR 上预构建的 `config-ui` 和 `telegraf` 镜像，目标是直接执行 `docker compose up -d`。

`docker-compose.dev.yml` 面向开发使用，会从当前仓库构建本地镜像，并挂载探测脚本和配置页面源码，便于快速调试。

## 数据流

```text
data/config/targets.csv + data/config/lines.csv
        |
        v
config-ui 编辑配置文件
        |
        v
data/probes/proxy_probe.sh -- curl -x proxy_url
        |
        v
stdout 输出 Influx line protocol
        |
        v
Telegraf inputs.exec
        |
        v
InfluxDB 2.x bucket
        |
        v
Grafana Flux dashboard
```

## 调度

Telegraf 按 `TELEGRAF_INTERVAL` 执行 `/probes/proxy_probe.sh`。在宿主机上，该脚本位于 `data/probes/proxy_probe.sh`。脚本每轮都会读取 `data/config/probe.env`，并通过 `/tmp` 中的状态文件控制 latency/download 目标的实际运行频率，所以多数探测参数保存后无需重启 Telegraf。

脚本还使用 `flock` 避免慢探测和下一轮探测重叠。

## 指标契约

measurement 固定为 `proxy_probe`。稳定 tag：

- `line`
- `test`
- `kind`

稳定数值字段：

- `success`
- `error`
- `http_code`
- `dns`
- `connect`
- `tls`
- `ttfb`
- `total`
- `speed_download`
- `size_download`

字段类型必须保持稳定。InfluxDB 对同名字段的类型变化很敏感，类型漂移会导致写入失败或查询割裂。

Grafana dashboard 会基于这些字段派生质量视图：5m/1h 成功率、1h 错误数、`total` p50/p95、`ttfb` p50/p95、下载 MB/s。

## 安全模型

指标中不能包含代理 URL、节点域名、订阅 URL、UUID、密码、private key 或 short id。Grafana tag 中只应出现抽象线路名。

运行数据位于 `data/runtime/`，并已被 Git 忽略。
