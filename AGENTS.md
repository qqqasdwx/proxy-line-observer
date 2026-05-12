# 仓库指南

## 项目结构

本仓库是用于对比代理线路质量的 Docker Compose 观测栈。根目录只放项目入口、文档和脚本：

- `docker-compose.yml`：用户版编排，使用 GHCR 预构建镜像。
- `docker-compose.dev.yml`：开发版编排，本地 build 镜像。
- `scripts/`：重复使用的校验和维护脚本。
- `docs/`：架构、运行和外部代理示例文档。
- `CONTRIBUTING.md`、`SECURITY.md`、`LICENSE`：开源协作、披露和许可证文档。
- `data/`：Compose 挂载的运行配置和服务文件。

`data/` 内部约定：

- `data/config/`：默认 CSV/env 配置，供配置页面编辑。
- `data/config-ui/`：本地网页配置器。
- `data/probes/`：输出 Influx line protocol 的 Bash 探测脚本。
- `data/telegraf/`：Telegraf 镜像和采集配置。
- `data/grafana/`：Grafana datasource 和 dashboard provisioning。
- `.github/workflows/docker-images.yml`：构建并发布 GHCR 镜像。

## 开发命令

- `docker compose up -d`：使用已发布镜像启动用户版栈。
- `docker compose -f docker-compose.dev.yml up -d --build`：本地构建并启动开发版栈。
- `docker compose logs -f config-ui`：查看配置页面日志。
- `docker compose logs -f telegraf`：查看探测和写入日志。
- `docker compose exec -T telegraf /probes/proxy_probe.sh`：手动执行一轮探测。
- `./scripts/check.sh`：运行脚本语法、Python 编译和 Compose 配置校验。

## 代码风格

探测和维护脚本使用 Bash。脚本以 `#!/usr/bin/env bash` 和 `set -euo pipefail` 开头。变量必须加引号，诊断信息写入 stderr，stdout 保持为合法 Influx line protocol。

配置页面使用 Python 标准库和原生 HTML/CSS/JS。不要为了少量交互引入前端构建链。

YAML 使用 2 空格缩进。CSV 头部必须保持稳定。业务逻辑不要硬编码代理软件或节点协议；项目层抽象只有 `line + proxy_url`。

## 测试要求

交付前至少运行 `./scripts/check.sh`。涉及运行时行为时，使用 `docker-compose.dev.yml` 启动服务，在 Telegraf 容器内手动执行探测，并在本地打开配置页面验证。

修改 line protocol 输出时，必须确认字段类型稳定：整数带 `i` 后缀，耗时字段为浮点数，tag 值已转义。

## 安全与配置

不要提交真实代理配置、订阅、UUID、private key、short id、代理密码或节点域名。`data/config/lines.csv` 会提交安全默认值，但本地编辑后可能包含敏感代理 URL，提交前必须检查。

## 提交与 PR

提交信息使用简短祈使句，例如 `Add probe lock` 或 `Document dashboard setup`。PR 应说明配置变更、验证命令，以及对 dashboard 或指标契约的影响。
