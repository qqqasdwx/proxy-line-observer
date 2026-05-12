# proxy-line-observer

`proxy-line-observer` 是一个基于 Docker Compose 的代理线路质量观测栈，用于长期对比多条 HTTP/SOCKS 代理入口的可用性、延迟、首包时间、错误率和下载吞吐。

核心抽象是：**一个 `proxy_url` = 一条线路**。本项目不运行、不解析、不管理代理软件，只通过每个代理入口发起同口径探测，并把结果写入 InfluxDB，再由 Grafana 展示。

## 特性

- 开箱即用：`docker compose up -d` 后通过网页配置线路和目标。
- 通用代理入口：支持 `http://`、`socks5://`、`socks5h://` 等 `curl -x` 可用地址。
- 长期质量视图：成功率、错误数、total/TTFB p50/p95、下载 MB/s。
- 文件化配置：线路、目标、探测参数和服务参数都保存在 `data/config/`。
- 本地优先：配置页面、Grafana、InfluxDB 默认只绑定 `127.0.0.1`。
- 不绑定代理软件：Clash/Mihomo、sing-box、Xray、Squid 等都可以作为外部代理来源。

## 前置要求

- Docker Engine
- Docker Compose v2
- 能访问 GitHub Container Registry，用于拉取默认镜像

默认 `docker-compose.yml` 使用这些镜像：

- `ghcr.io/qqqasdwx/proxy-line-observer-config-ui:latest`
- `ghcr.io/qqqasdwx/proxy-line-observer-telegraf:latest`
- `influxdb:2.7-alpine`
- `grafana/grafana-oss:11.3.0`

如果 GHCR package 不是 public，未登录用户无法直接拉取镜像。发布正式版本前需要在 GitHub Packages 中确认镜像可公开拉取，或让用户先执行 `docker login ghcr.io`。

## 快速开始

```bash
git clone https://github.com/qqqasdwx/proxy-line-observer.git
cd proxy-line-observer
docker compose up -d
```

打开：

- 配置页面：<http://localhost:8080>
- Grafana：<http://localhost:3000>
- InfluxDB：<http://localhost:8086>

默认账号密码在 `data/config/stack.env` 中。首次启动后建议立即在配置页面或文件中修改 Grafana、InfluxDB 密码和 token，然后重新创建相关容器。InfluxDB 初始化参数只在首次创建 `data/runtime/influxdb` 时生效。

## 配置流程

1. 打开配置页面。
2. 在线路页添加或启用代理入口。
3. 点击线路测试，确认代理可连通。
4. 在目标页确认 latency/download 目标。
5. 打开 Grafana 查看 `代理线路质量对比` dashboard。

如果需要临时运行代理软件提供端口，可参考：

- [使用 Clash/Mihomo 提供代理线路](docs/clash.md)
- [使用 sing-box 提供代理线路](docs/sing-box.md)

## 用户版与开发版 Compose

用户版：

```bash
docker compose up -d
```

开发版：

```bash
docker compose -f docker-compose.dev.yml up -d --build
```

用户版 `docker-compose.yml` 只拉取已发布镜像。开发版 `docker-compose.dev.yml` 会从当前仓库构建 `config-ui` 和 `telegraf`，并挂载源码，适合调试。

如果你 fork 了仓库，可以覆盖镜像来源：

```bash
CONFIG_UI_IMAGE=ghcr.io/<owner>/proxy-line-observer-config-ui:latest \
TELEGRAF_IMAGE=ghcr.io/<owner>/proxy-line-observer-telegraf:latest \
docker compose up -d
```

## 目录结构

```text
.
  docker-compose.yml
  docker-compose.dev.yml
  data/
    config/
    config-ui/
    grafana/
    probes/
    telegraf/
    runtime/        # Git 忽略，保存运行数据
  docs/
  scripts/
```

关键路径：

- `data/config/lines.csv`：线路配置。
- `data/config/targets.csv`：探测目标配置。
- `data/config/probe.env`：探测间隔和超时。
- `data/config/stack.env`：InfluxDB、Grafana、Telegraf 启动参数。
- `data/runtime/`：InfluxDB 和 Grafana 持久化数据，默认不提交。

## 线路配置

配置页面会编辑 `data/config/lines.csv`：

```csv
line,proxy_url,enabled
line_a_http,http://host.docker.internal:7890,false
line_b_socks,socks5h://host.docker.internal:7891,false
```

- `line` 是观测标签，建议使用稳定、抽象的名字。
- `proxy_url` 是 `curl -x` 使用的代理地址。
- 代理跑在同一台 Docker 宿主机时，可使用 `host.docker.internal`。
- `socks5h://` 会让目标域名由代理侧解析，通常更适合线路对比。
- 每个 `proxy_url` 应固定到一条线路，避免自动切换导致数据不可解释。

## 目标配置

配置页面会编辑 `data/config/targets.csv`：

```csv
test,url,expected_codes,kind,enabled
google_204,https://www.google.com/generate_204,204|200,latency,true
gstatic_204,https://www.gstatic.com/generate_204,204|200,latency,true
cloudflare_trace,https://www.cloudflare.com/cdn-cgi/trace,200,latency,true
cloudflare_10mb,https://speed.cloudflare.com/__down?bytes=10000000,200,download,false
cloudflare_50mb,https://speed.cloudflare.com/__down?bytes=50000000,200,download,false
```

- `kind=latency`：小请求，用于延迟、TTFB、成功率。
- `kind=download`：下载请求，用于吞吐测试，默认关闭。
- `expected_codes` 支持 `204|200` 这种多状态码格式。
- CSV 字段中不要包含未转义逗号。
- 下载目标建议低频启用，线路越多，下载流量越大。

## 指标说明

探测脚本输出 measurement `proxy_probe`，主要字段：

- `success`：HTTP 状态码命中 `expected_codes` 时为 `1i`。
- `error`：curl 发生连接、超时、TLS、代理等错误时为 `1i`。
- `http_code`：最终 HTTP 状态码，失败时通常为 `0i`。
- `dns`、`connect`、`tls`、`ttfb`、`total`：curl 请求阶段耗时。
- `speed_download`：下载速度，单位 bytes/sec。
- `size_download`：下载字节数。

通过代理探测时，阶段耗时反映的是 `Telegraf -> proxy_url -> 代理链路 -> 目标站` 的综合表现，不等同于协议层分段诊断。

Grafana dashboard 会基于原始字段计算：

- 最近 5 分钟和 1 小时成功率。
- 最近 1 小时错误数。
- `total` 的 p50 / p95 曲线。
- `ttfb` 的 p50 / p95 曲线。
- 下载速度最近值和历史曲线。

## 运维命令

```bash
docker compose ps
docker compose logs -f config-ui
docker compose logs -f telegraf
docker compose exec -T telegraf /probes/proxy_probe.sh
./scripts/check.sh
```

## 安全说明

- 不要提交真实节点配置、订阅 URL、UUID、private key、password、short id 或代理密码。
- `data/config/lines.csv` 可能包含带凭据的 `proxy_url`，提交前必须检查。
- 配置页面、Grafana、InfluxDB 默认只绑定本机。暴露到公网前必须加鉴权、防火墙或反向代理保护。
- 如果修改 `INFLUXDB_BUCKET`，需要同步调整 dashboard 的 `bucket` 变量或重新生成 dashboard。

## 局限

- 本项目不是完整协议层诊断工具。
- 测到的是用户请求视角的综合链路质量，不是某个代理协议的纯粹性能。
- 公共测试目标自身波动会影响结果。
- 如果代理入口背后会自动切换节点，观测结果会变得不稳定。

## 开发与发布

开发前运行：

```bash
docker compose -f docker-compose.dev.yml up -d --build
./scripts/check.sh
```

GitHub Actions 会在 push 到默认分支（`main`/`master`）或 tag `v*.*.*` 时构建并推送 GHCR 镜像。PR 只构建，不推送。

## 许可证

本项目使用 MIT License，详见 [LICENSE](LICENSE)。
