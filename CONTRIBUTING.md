# 贡献指南

感谢你关注 `proxy-line-observer`。本项目的目标是提供一个简单、可复现、可长期运行的代理线路质量观测栈。

## 开发环境

```bash
docker compose -f docker-compose.dev.yml up -d --build
./scripts/check.sh
```

开发版 Compose 会本地构建 `config-ui` 和 `telegraf` 镜像，并挂载源码，适合调试配置页面和探测脚本。

## 提交前检查

提交前至少运行：

```bash
./scripts/check.sh
```

如果修改了探测逻辑，还应手动执行：

```bash
docker compose exec -T telegraf /probes/proxy_probe.sh
```

如果修改了 dashboard，请确认 JSON 合法：

```bash
jq empty data/grafana/dashboards/proxy-line-comparison.json
```

## 代码约定

- Bash 脚本使用 `set -euo pipefail`。
- 探测脚本 stdout 必须保持为合法 Influx line protocol。
- 诊断信息写入 stderr。
- CSV header 不要随意改名。
- 不要在业务逻辑中绑定 Clash、Mihomo、sing-box 或具体代理协议。

## 安全约定

不要提交真实代理地址、账号密码、订阅 URL、UUID、private key、short id 或节点域名。`data/config/lines.csv` 默认是安全示例，但本地编辑后可能包含敏感信息，提交前必须检查。
