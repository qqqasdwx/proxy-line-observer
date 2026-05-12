# 安全策略

## 支持范围

当前项目处于早期版本。安全修复会优先面向默认分支和最新发布版本。

## 报告安全问题

请不要在公开 issue 中披露可利用的安全细节。建议通过 GitHub Security Advisories 私下报告，或先开一个不包含敏感细节的 issue 说明需要安全联系。

## 部署安全

- 配置页面、Grafana、InfluxDB 默认只绑定 `127.0.0.1`。
- 暴露到公网前必须加鉴权、防火墙或反向代理保护。
- 修改 `data/config/stack.env` 中的默认密码和 token。
- 不要把包含真实代理凭据的 `data/config/lines.csv` 提交到公开仓库。
- 不要在指标、日志或 dashboard 中输出代理 URL、订阅 URL、UUID、private key、short id 或代理密码。
