#!/usr/bin/env python3
import csv
import json
import os
import subprocess
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

APP_HOST = os.environ.get("CONFIG_UI_HOST", "0.0.0.0")
APP_PORT = int(os.environ.get("CONFIG_UI_PORT", "8080"))
CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", "/app/config"))

LINES_FILE = CONFIG_DIR / "lines.csv"
TARGETS_FILE = CONFIG_DIR / "targets.csv"
PROBE_ENV_FILE = CONFIG_DIR / "probe.env"
STACK_ENV_FILE = CONFIG_DIR / "stack.env"

LINE_FIELDS = ["line", "proxy_url", "enabled"]
TARGET_FIELDS = ["test", "url", "expected_codes", "kind", "enabled"]
PROBE_KEYS = [
    "LATENCY_PROBE_INTERVAL_SECONDS",
    "DOWNLOAD_PROBE_INTERVAL_SECONDS",
    "CURL_CONNECT_TIMEOUT_SECONDS",
    "LATENCY_PROBE_MAX_TIME_SECONDS",
    "DOWNLOAD_PROBE_MAX_TIME_SECONDS",
]
STACK_KEYS = [
    "INFLUXDB_ORG",
    "INFLUXDB_BUCKET",
    "INFLUXDB_TOKEN",
    "INFLUXDB_URL",
    "DOCKER_INFLUXDB_INIT_USERNAME",
    "DOCKER_INFLUXDB_INIT_PASSWORD",
    "DOCKER_INFLUXDB_INIT_ORG",
    "DOCKER_INFLUXDB_INIT_BUCKET",
    "DOCKER_INFLUXDB_INIT_ADMIN_TOKEN",
    "GF_SECURITY_ADMIN_USER",
    "GF_SECURITY_ADMIN_PASSWORD",
    "TELEGRAF_INTERVAL",
    "TELEGRAF_EXEC_TIMEOUT",
]

DEFAULT_LINES = [
    {"line": "line_a_http", "proxy_url": "http://host.docker.internal:7890", "enabled": "false"},
    {"line": "line_b_socks", "proxy_url": "socks5h://host.docker.internal:7891", "enabled": "false"},
]
DEFAULT_TARGETS = [
    {
        "test": "google_204",
        "url": "https://www.google.com/generate_204",
        "expected_codes": "204|200",
        "kind": "latency",
        "enabled": "true",
    },
    {
        "test": "gstatic_204",
        "url": "https://www.gstatic.com/generate_204",
        "expected_codes": "204|200",
        "kind": "latency",
        "enabled": "true",
    },
    {
        "test": "cloudflare_trace",
        "url": "https://www.cloudflare.com/cdn-cgi/trace",
        "expected_codes": "200",
        "kind": "latency",
        "enabled": "true",
    },
    {
        "test": "cloudflare_10mb",
        "url": "https://speed.cloudflare.com/__down?bytes=10000000",
        "expected_codes": "200",
        "kind": "download",
        "enabled": "false",
    },
    {
        "test": "cloudflare_50mb",
        "url": "https://speed.cloudflare.com/__down?bytes=50000000",
        "expected_codes": "200",
        "kind": "download",
        "enabled": "false",
    },
]
DEFAULT_PROBE = {
    "LATENCY_PROBE_INTERVAL_SECONDS": "30",
    "DOWNLOAD_PROBE_INTERVAL_SECONDS": "300",
    "CURL_CONNECT_TIMEOUT_SECONDS": "10",
    "LATENCY_PROBE_MAX_TIME_SECONDS": "20",
    "DOWNLOAD_PROBE_MAX_TIME_SECONDS": "120",
}
DEFAULT_STACK = {
    "INFLUXDB_ORG": "proxy-observer",
    "INFLUXDB_BUCKET": "proxy_metrics",
    "INFLUXDB_TOKEN": "proxy_observer_change_me_token",
    "INFLUXDB_URL": "http://influxdb:8086",
    "DOCKER_INFLUXDB_INIT_USERNAME": "admin",
    "DOCKER_INFLUXDB_INIT_PASSWORD": "proxy_observer_change_me",
    "DOCKER_INFLUXDB_INIT_ORG": "proxy-observer",
    "DOCKER_INFLUXDB_INIT_BUCKET": "proxy_metrics",
    "DOCKER_INFLUXDB_INIT_ADMIN_TOKEN": "proxy_observer_change_me_token",
    "GF_SECURITY_ADMIN_USER": "admin",
    "GF_SECURITY_ADMIN_PASSWORD": "proxy_observer_change_me",
    "TELEGRAF_INTERVAL": "30s",
    "TELEGRAF_EXEC_TIMEOUT": "150s",
}

HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>代理线路观测</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #1f2328;
      --muted: #656d76;
      --border: #d8dee4;
      --accent: #0969da;
      --danger: #cf222e;
      --ok: #1a7f37;
      --shadow: 0 1px 2px rgba(31, 35, 40, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      font-size: 14px;
      line-height: 1.45;
    }
    header {
      position: sticky;
      top: 0;
      z-index: 5;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 24px;
      background: #ffffff;
      border-bottom: 1px solid var(--border);
    }
    h1 {
      margin: 0;
      font-size: 18px;
      font-weight: 650;
      letter-spacing: 0;
    }
    main {
      width: min(1440px, 100%);
      margin: 0 auto;
      padding: 18px 24px 40px;
    }
    .toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }
    .tabs {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 18px;
    }
    .tab {
      border: 1px solid var(--border);
      background: #ffffff;
      color: var(--text);
      border-radius: 6px;
      padding: 8px 12px;
      cursor: pointer;
    }
    .tab.active {
      color: #ffffff;
      border-color: var(--accent);
      background: var(--accent);
    }
    .panel {
      display: none;
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 16px;
      margin-bottom: 16px;
    }
    .panel.active { display: block; }
    .panel-head {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 12px;
    }
    h2 {
      margin: 0 0 4px;
      font-size: 16px;
      letter-spacing: 0;
    }
    p {
      margin: 0;
      color: var(--muted);
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th, td {
      border-top: 1px solid var(--border);
      padding: 9px 8px;
      text-align: left;
      vertical-align: middle;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    input, select {
      width: 100%;
      min-width: 0;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 8px 9px;
      background: #ffffff;
      color: var(--text);
      font: inherit;
    }
    input[type="checkbox"] {
      width: 18px;
      height: 18px;
    }
    .grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(180px, 1fr));
      gap: 12px;
    }
    .field label {
      display: block;
      margin-bottom: 5px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
    }
    button {
      border: 1px solid var(--border);
      border-radius: 6px;
      background: #ffffff;
      color: var(--text);
      padding: 8px 11px;
      cursor: pointer;
      font: inherit;
      white-space: nowrap;
    }
    button.primary {
      border-color: var(--accent);
      background: var(--accent);
      color: #ffffff;
    }
    button.danger {
      border-color: #ffebe9;
      color: var(--danger);
      background: #fff5f5;
    }
    button:disabled {
      opacity: 0.55;
      cursor: not-allowed;
    }
    .status {
      min-height: 20px;
      color: var(--muted);
    }
    .status.ok { color: var(--ok); }
    .status.err { color: var(--danger); }
    .notice {
      border: 1px solid #f0d98c;
      background: #fff8c5;
      border-radius: 8px;
      padding: 10px 12px;
      color: #5d4411;
      margin-bottom: 12px;
    }
    pre {
      overflow: auto;
      white-space: pre-wrap;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: #f6f8fa;
      padding: 12px;
      min-height: 72px;
    }
    .actions {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .col-enabled { width: 86px; }
    .col-actions { width: 150px; }
    .col-kind { width: 132px; }
    .col-code { width: 130px; }
    @media (max-width: 860px) {
      header { align-items: flex-start; flex-direction: column; padding: 12px 14px; }
      main { padding: 14px; }
      .grid { grid-template-columns: 1fr; }
      table, thead, tbody, tr, th, td { display: block; width: 100%; }
      thead { display: none; }
      tr { border-top: 1px solid var(--border); padding: 8px 0; }
      td { border: 0; padding: 6px 0; }
      td::before {
        content: attr(data-label);
        display: block;
        margin-bottom: 4px;
        color: var(--muted);
        font-size: 12px;
        font-weight: 650;
      }
    }
  </style>
</head>
<body>
  <header>
    <h1>代理线路观测</h1>
    <div class="toolbar">
      <span id="save-status" class="status">加载中</span>
      <button id="reload-btn">重新加载</button>
      <button id="save-btn" class="primary">保存配置</button>
    </div>
  </header>
  <main>
    <nav class="tabs">
      <button class="tab active" data-tab="lines">线路</button>
      <button class="tab" data-tab="targets">目标</button>
      <button class="tab" data-tab="probe">探测参数</button>
      <button class="tab" data-tab="stack">服务配置</button>
    </nav>

    <section id="lines" class="panel active">
      <div class="panel-head">
        <div>
          <h2>代理线路</h2>
          <p>每个 proxy_url 代表一条被观测线路。SOCKS 推荐使用 socks5h://。</p>
        </div>
        <button id="add-line-btn">添加线路</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>线路名称</th>
            <th>代理地址</th>
            <th class="col-enabled">启用</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody id="lines-body"></tbody>
      </table>
      <pre id="test-output">代理测试结果会显示在这里。</pre>
    </section>

    <section id="targets" class="panel">
      <div class="panel-head">
        <div>
          <h2>测试目标</h2>
          <p>latency 用于小请求延迟和成功率，download 用于吞吐测试。</p>
        </div>
        <button id="add-target-btn">添加目标</button>
      </div>
      <table>
        <thead>
          <tr>
            <th>测试名称</th>
            <th>目标地址</th>
            <th class="col-code">期望状态码</th>
            <th class="col-kind">类型</th>
            <th class="col-enabled">启用</th>
            <th class="col-actions">操作</th>
          </tr>
        </thead>
        <tbody id="targets-body"></tbody>
      </table>
    </section>

    <section id="probe" class="panel">
      <div class="panel-head">
        <div>
          <h2>探测参数</h2>
          <p>这些值由探测脚本每轮读取，保存后无需重启 Telegraf。</p>
        </div>
      </div>
      <div id="probe-grid" class="grid"></div>
    </section>

    <section id="stack" class="panel">
      <div class="panel-head">
        <div>
          <h2>服务配置</h2>
          <p>这些值来自 data/config/stack.env，修改后需要重新创建相关容器。</p>
        </div>
      </div>
      <div class="notice">InfluxDB 初始化账号、bucket 和 token 只在首次创建 data/runtime/influxdb 时生效。已有数据目录时修改这些值不会自动迁移旧实例。</div>
      <div id="stack-grid" class="grid"></div>
    </section>
  </main>

  <script>
    const state = { lines: [], targets: [], probe: {}, stack: {} };
    const probeLabels = {
      LATENCY_PROBE_INTERVAL_SECONDS: '小请求间隔秒',
      DOWNLOAD_PROBE_INTERVAL_SECONDS: '下载测试间隔秒',
      CURL_CONNECT_TIMEOUT_SECONDS: '连接超时秒',
      LATENCY_PROBE_MAX_TIME_SECONDS: '小请求最大耗时秒',
      DOWNLOAD_PROBE_MAX_TIME_SECONDS: '下载最大耗时秒'
    };
    const stackLabels = {
      INFLUXDB_ORG: 'InfluxDB Org',
      INFLUXDB_BUCKET: 'InfluxDB 存储桶',
      INFLUXDB_TOKEN: 'InfluxDB Token',
      INFLUXDB_URL: 'InfluxDB URL',
      DOCKER_INFLUXDB_INIT_USERNAME: 'Influx 初始用户',
      DOCKER_INFLUXDB_INIT_PASSWORD: 'Influx 初始密码',
      DOCKER_INFLUXDB_INIT_ORG: 'Influx 初始 Org',
      DOCKER_INFLUXDB_INIT_BUCKET: 'Influx 初始存储桶',
      DOCKER_INFLUXDB_INIT_ADMIN_TOKEN: 'Influx 初始 Token',
      GF_SECURITY_ADMIN_USER: 'Grafana 用户',
      GF_SECURITY_ADMIN_PASSWORD: 'Grafana 密码',
      TELEGRAF_INTERVAL: 'Telegraf 执行间隔',
      TELEGRAF_EXEC_TIMEOUT: 'Telegraf 执行超时'
    };

    function setStatus(text, mode = '') {
      const el = document.getElementById('save-status');
      el.textContent = text;
      el.className = `status ${mode}`;
    }

    function input(value, onChange, type = 'text') {
      const el = document.createElement('input');
      el.type = type;
      el.value = value || '';
      el.addEventListener('input', () => onChange(el.value));
      return el;
    }

    function checkbox(value, onChange) {
      const el = document.createElement('input');
      el.type = 'checkbox';
      el.checked = String(value).toLowerCase() === 'true';
      el.addEventListener('change', () => onChange(el.checked ? 'true' : 'false'));
      return el;
    }

    function cell(label, child) {
      const td = document.createElement('td');
      td.dataset.label = label;
      td.appendChild(child);
      return td;
    }

    function renderLines() {
      const body = document.getElementById('lines-body');
      body.replaceChildren();
      state.lines.forEach((line, index) => {
        const tr = document.createElement('tr');
        tr.appendChild(cell('线路名称', input(line.line, v => line.line = v)));
        tr.appendChild(cell('代理地址', input(line.proxy_url, v => line.proxy_url = v)));
        tr.appendChild(cell('启用', checkbox(line.enabled, v => line.enabled = v)));

        const actions = document.createElement('div');
        actions.className = 'actions';
        const test = document.createElement('button');
        test.textContent = '测试';
        test.addEventListener('click', () => testProxy(index));
        const del = document.createElement('button');
        del.textContent = '删除';
        del.className = 'danger';
        del.addEventListener('click', () => {
          state.lines.splice(index, 1);
          renderLines();
        });
        actions.append(test, del);
        tr.appendChild(cell('操作', actions));
        body.appendChild(tr);
      });
    }

    function renderTargets() {
      const body = document.getElementById('targets-body');
      body.replaceChildren();
      state.targets.forEach((target, index) => {
        const tr = document.createElement('tr');
        tr.appendChild(cell('测试名称', input(target.test, v => target.test = v)));
        tr.appendChild(cell('目标地址', input(target.url, v => target.url = v)));
        tr.appendChild(cell('期望状态码', input(target.expected_codes, v => target.expected_codes = v)));

        const kind = document.createElement('select');
        ['latency', 'download'].forEach(value => {
          const option = document.createElement('option');
          option.value = value;
          option.textContent = value;
          option.selected = target.kind === value;
          kind.appendChild(option);
        });
        kind.addEventListener('change', () => target.kind = kind.value);
        tr.appendChild(cell('类型', kind));
        tr.appendChild(cell('启用', checkbox(target.enabled, v => target.enabled = v)));

        const actions = document.createElement('div');
        actions.className = 'actions';
        const del = document.createElement('button');
        del.textContent = '删除';
        del.className = 'danger';
        del.addEventListener('click', () => {
          state.targets.splice(index, 1);
          renderTargets();
        });
        actions.appendChild(del);
        tr.appendChild(cell('操作', actions));
        body.appendChild(tr);
      });
    }

    function renderEnvGrid(id, values, labels, passwordPattern) {
      const grid = document.getElementById(id);
      grid.replaceChildren();
      Object.keys(labels).forEach(key => {
        const wrap = document.createElement('div');
        wrap.className = 'field';
        const label = document.createElement('label');
        label.textContent = labels[key];
        const type = passwordPattern.test(key) ? 'password' : 'text';
        wrap.append(label, input(values[key] || '', v => values[key] = v, type));
        grid.appendChild(wrap);
      });
    }

    function render() {
      renderLines();
      renderTargets();
      renderEnvGrid('probe-grid', state.probe, probeLabels, /never/);
      renderEnvGrid('stack-grid', state.stack, stackLabels, /(TOKEN|PASSWORD)/);
    }

    async function loadConfig() {
      setStatus('加载中');
      const response = await fetch('/api/config');
      if (!response.ok) throw new Error(await response.text());
      const data = await response.json();
      state.lines = data.lines;
      state.targets = data.targets;
      state.probe = data.probe;
      state.stack = data.stack;
      render();
      setStatus('已加载', 'ok');
    }

    async function saveConfig() {
      setStatus('保存中');
      const response = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(state)
      });
      if (!response.ok) {
        setStatus(await response.text(), 'err');
        return;
      }
      setStatus('已保存', 'ok');
    }

    async function testProxy(index) {
      const line = state.lines[index];
      const target = state.targets.find(t => t.enabled === 'true' && t.kind === 'latency') || state.targets[0];
      const out = document.getElementById('test-output');
      out.textContent = '测试中...';
      const response = await fetch('/api/test-proxy', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          proxy_url: line.proxy_url,
          target_url: target ? target.url : 'https://www.google.com/generate_204',
          expected_codes: target ? target.expected_codes : '204|200'
        })
      });
      const result = await response.json();
      out.textContent = [
        `结果: ${result.ok ? '成功' : '失败'}`,
        `curl 退出码: ${result.curl_exit ?? ''}`,
        `HTTP 状态码: ${result.http_code ?? ''}`,
        `期望状态码: ${result.expected_codes ?? ''}`,
        `耗时: ${result.elapsed_seconds ?? ''} 秒`,
        result.stderr ? `错误输出: ${result.stderr}` : '',
        result.timing ? `详细计时:\n${JSON.stringify(result.timing, null, 2)}` : ''
      ].filter(Boolean).join('\n');
    }

    document.getElementById('add-line-btn').addEventListener('click', () => {
      state.lines.push({ line: 'new_line', proxy_url: 'http://host.docker.internal:7890', enabled: 'false' });
      renderLines();
    });
    document.getElementById('add-target-btn').addEventListener('click', () => {
      state.targets.push({ test: 'new_test', url: 'https://www.google.com/generate_204', expected_codes: '204|200', kind: 'latency', enabled: 'true' });
      renderTargets();
    });
    document.getElementById('save-btn').addEventListener('click', saveConfig);
    document.getElementById('reload-btn').addEventListener('click', loadConfig);
    document.querySelectorAll('.tab').forEach(tab => {
      tab.addEventListener('click', () => {
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(tab.dataset.tab).classList.add('active');
      });
    });
    loadConfig().catch(error => setStatus(error.message, 'err'));
  </script>
</body>
</html>
"""


def ensure_files() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not LINES_FILE.exists():
        write_csv(LINES_FILE, LINE_FIELDS, DEFAULT_LINES)
    if not TARGETS_FILE.exists():
        write_csv(TARGETS_FILE, TARGET_FIELDS, DEFAULT_TARGETS)
    if not PROBE_ENV_FILE.exists():
        write_env(PROBE_ENV_FILE, DEFAULT_PROBE, PROBE_KEYS)
    if not STACK_ENV_FILE.exists():
        write_env(STACK_ENV_FILE, DEFAULT_STACK, STACK_KEYS)


def truthy(value: str) -> str:
    return "true" if str(value).strip().lower() in {"1", "true", "yes", "y", "enabled", "on"} else "false"


def read_csv(path: Path, fields: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            clean = {field: str(row.get(field, "") or "").strip() for field in fields}
            clean["enabled"] = truthy(clean.get("enabled", "false"))
            rows.append(clean)
        return rows


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: str(row.get(field, "") or "").strip() for field in fields})


def read_env(path: Path, keys: list[str], defaults: dict[str, str]) -> dict[str, str]:
    values = dict(defaults)
    if not path.exists():
        return values
    with path.open(encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if key in keys:
                values[key] = value.strip()
    return values


def write_env(path: Path, values: dict[str, str], keys: list[str]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for key in keys:
            handle.write(f"{key}={str(values.get(key, '') or '').strip()}\n")


def validate_lines(lines: list[dict[str, str]]) -> list[dict[str, str]]:
    clean = []
    seen = set()
    for row in lines:
        name = str(row.get("line", "") or "").strip()
        proxy_url = str(row.get("proxy_url", "") or "").strip()
        if not name:
            raise ValueError("线路名称不能为空")
        if name in seen:
            raise ValueError(f"线路名称重复：{name}")
        if "," in name or "," in proxy_url:
            raise ValueError(f"线路字段不能包含逗号：{name}")
        if proxy_url and urlparse(proxy_url).scheme not in {"http", "https", "socks4", "socks4a", "socks5", "socks5h"}:
            raise ValueError(f"线路 {name} 使用了不支持的代理协议")
        seen.add(name)
        clean.append({"line": name, "proxy_url": proxy_url, "enabled": truthy(row.get("enabled", "false"))})
    return clean


def validate_targets(targets: list[dict[str, str]]) -> list[dict[str, str]]:
    clean = []
    seen = set()
    for row in targets:
        name = str(row.get("test", "") or "").strip()
        url = str(row.get("url", "") or "").strip()
        expected_codes = str(row.get("expected_codes", "") or "").strip()
        kind = str(row.get("kind", "") or "").strip().lower()
        if not name:
            raise ValueError("测试名称不能为空")
        if name in seen:
            raise ValueError(f"测试名称重复：{name}")
        if "," in name or "," in url or "," in expected_codes or "," in kind:
            raise ValueError(f"测试目标字段不能包含逗号：{name}")
        if urlparse(url).scheme not in {"http", "https"}:
            raise ValueError(f"测试目标 {name} 的 URL 必须是 http 或 https")
        if kind not in {"latency", "download"}:
            raise ValueError(f"测试目标 {name} 使用了不支持的类型")
        for code in expected_codes.split("|"):
            if not code.strip().isdigit():
                raise ValueError(f"测试目标 {name} 的期望状态码无效")
        seen.add(name)
        clean.append(
            {
                "test": name,
                "url": url,
                "expected_codes": expected_codes,
                "kind": kind,
                "enabled": truthy(row.get("enabled", "false")),
            }
        )
    return clean


def parse_curl_output(output: str) -> dict[str, str]:
    values = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def expected_ok(code: str, expected_codes: str) -> bool:
    return code in {part.strip() for part in expected_codes.split("|") if part.strip()}


def test_proxy(payload: dict) -> dict:
    proxy_url = str(payload.get("proxy_url", "") or "").strip()
    target_url = str(payload.get("target_url", "") or "https://www.google.com/generate_204").strip()
    expected_codes = str(payload.get("expected_codes", "") or "204|200").strip()
    if not proxy_url:
        raise ValueError("代理地址不能为空")
    if urlparse(target_url).scheme not in {"http", "https"}:
        raise ValueError("测试目标 URL 必须是 http 或 https")

    start = time.monotonic()
    args = [
        "curl",
        "-x",
        proxy_url,
        "--connect-timeout",
        "10",
        "--max-time",
        "20",
        "--location",
        "--max-redirs",
        "3",
        "--output",
        "/dev/null",
        "--silent",
        "--show-error",
        "--write-out",
        "http_code=%{http_code}\ntime_namelookup=%{time_namelookup}\ntime_connect=%{time_connect}\ntime_appconnect=%{time_appconnect}\ntime_starttransfer=%{time_starttransfer}\ntime_total=%{time_total}\nspeed_download=%{speed_download}\nsize_download=%{size_download}\nremote_ip=%{remote_ip}\n",
        target_url,
    ]
    completed = subprocess.run(args, text=True, capture_output=True, timeout=25, check=False)
    values = parse_curl_output(completed.stdout)
    code = values.get("http_code", "0")
    return {
        "ok": completed.returncode == 0 and expected_ok(code, expected_codes),
        "curl_exit": completed.returncode,
        "http_code": code,
        "expected_codes": expected_codes,
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "timing": values,
        "stderr": completed.stderr.strip(),
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "ProxyLineObserverConfig/1.0"

    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)

    def send_json(self, payload, status=HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text: str, status=HTTPStatus.OK, content_type="text/plain; charset=utf-8") -> None:
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_payload(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:
        try:
            if self.path == "/":
                self.send_text(HTML, content_type="text/html; charset=utf-8")
            elif self.path == "/health":
                self.send_json({"ok": True})
            elif self.path == "/api/config":
                ensure_files()
                self.send_json(
                    {
                        "lines": read_csv(LINES_FILE, LINE_FIELDS),
                        "targets": read_csv(TARGETS_FILE, TARGET_FIELDS),
                        "probe": read_env(PROBE_ENV_FILE, PROBE_KEYS, DEFAULT_PROBE),
                        "stack": read_env(STACK_ENV_FILE, STACK_KEYS, DEFAULT_STACK),
                    }
                )
            else:
                self.send_text("未找到", HTTPStatus.NOT_FOUND)
        except Exception as exc:
            self.send_text(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        try:
            if self.path == "/api/config":
                payload = self.read_payload()
                lines = validate_lines(payload.get("lines", []))
                targets = validate_targets(payload.get("targets", []))
                probe = {key: str(payload.get("probe", {}).get(key, DEFAULT_PROBE.get(key, ""))).strip() for key in PROBE_KEYS}
                stack = {key: str(payload.get("stack", {}).get(key, DEFAULT_STACK.get(key, ""))).strip() for key in STACK_KEYS}
                write_csv(LINES_FILE, LINE_FIELDS, lines)
                write_csv(TARGETS_FILE, TARGET_FIELDS, targets)
                write_env(PROBE_ENV_FILE, probe, PROBE_KEYS)
                write_env(STACK_ENV_FILE, stack, STACK_KEYS)
                self.send_json({"ok": True})
            elif self.path == "/api/test-proxy":
                self.send_json(test_proxy(self.read_payload()))
            else:
                self.send_text("未找到", HTTPStatus.NOT_FOUND)
        except subprocess.TimeoutExpired:
            self.send_json({"ok": False, "error": "curl 超时"}, HTTPStatus.REQUEST_TIMEOUT)
        except ValueError as exc:
            self.send_text(str(exc), HTTPStatus.BAD_REQUEST)
        except Exception as exc:
            self.send_text(str(exc), HTTPStatus.INTERNAL_SERVER_ERROR)


def main() -> None:
    ensure_files()
    server = ThreadingHTTPServer((APP_HOST, APP_PORT), Handler)
    print(f"config-ui listening on {APP_HOST}:{APP_PORT}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
