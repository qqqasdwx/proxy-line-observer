#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=data/probes/lib.sh
source "${SCRIPT_DIR}/lib.sh"

LINES_FILE="${LINES_FILE:-/config/lines.csv}"
TARGETS_FILE="${TARGETS_FILE:-/config/targets.csv}"
PROBE_SETTINGS_FILE="${PROBE_SETTINGS_FILE:-/config/probe.env}"
LATENCY_PROBE_INTERVAL_SECONDS="${LATENCY_PROBE_INTERVAL_SECONDS:-30}"
DOWNLOAD_PROBE_INTERVAL_SECONDS="${DOWNLOAD_PROBE_INTERVAL_SECONDS:-300}"
CURL_CONNECT_TIMEOUT_SECONDS="${CURL_CONNECT_TIMEOUT_SECONDS:-10}"
LATENCY_PROBE_MAX_TIME_SECONDS="${LATENCY_PROBE_MAX_TIME_SECONDS:-20}"
DOWNLOAD_PROBE_MAX_TIME_SECONDS="${DOWNLOAD_PROBE_MAX_TIME_SECONDS:-120}"
PROBE_LOCK_FILE="${PROBE_LOCK_FILE:-/tmp/proxy_probe.lock}"
LATENCY_STATE_FILE="${LATENCY_STATE_FILE:-/tmp/proxy_probe_latency_last}"
DOWNLOAD_STATE_FILE="${DOWNLOAD_STATE_FILE:-/tmp/proxy_probe_download_last}"

exec 9>"$PROBE_LOCK_FILE"
if ! flock -n 9; then
  warn "previous run is still active; skipping this interval"
  exit 0
fi

require_file() {
  local path="$1"
  local example="$2"
  if [[ ! -f "$path" ]]; then
    warn "missing $path; copy $example first"
    exit 1
  fi
}

load_probe_settings() {
  local key value

  [[ -f "$PROBE_SETTINGS_FILE" ]] || return 0

  while IFS='=' read -r key value || [[ -n "${key:-}" ]]; do
    key="$(trim "${key:-}")"
    value="$(trim "${value:-}")"

    [[ -z "$key" || "$key" == \#* ]] && continue

    case "$key" in
      LATENCY_PROBE_INTERVAL_SECONDS) LATENCY_PROBE_INTERVAL_SECONDS="$(int_or_zero "$value")" ;;
      DOWNLOAD_PROBE_INTERVAL_SECONDS) DOWNLOAD_PROBE_INTERVAL_SECONDS="$(int_or_zero "$value")" ;;
      CURL_CONNECT_TIMEOUT_SECONDS) CURL_CONNECT_TIMEOUT_SECONDS="$(int_or_zero "$value")" ;;
      LATENCY_PROBE_MAX_TIME_SECONDS) LATENCY_PROBE_MAX_TIME_SECONDS="$(int_or_zero "$value")" ;;
      DOWNLOAD_PROBE_MAX_TIME_SECONDS) DOWNLOAD_PROBE_MAX_TIME_SECONDS="$(int_or_zero "$value")" ;;
    esac
  done < "$PROBE_SETTINGS_FILE"
}

require_file "$LINES_FILE" "data/config/lines.csv"
require_file "$TARGETS_FILE" "data/config/targets.csv"
load_probe_settings

declare -a LINE_NAMES=()
declare -a LINE_PROXY_URLS=()
declare -a TARGET_NAMES=()
declare -a TARGET_URLS=()
declare -a TARGET_EXPECTED_CODES=()
declare -a TARGET_KINDS=()

load_lines() {
  local line proxy_url enabled rest
  while IFS=, read -r line proxy_url enabled rest || [[ -n "${line:-}" ]]; do
    line="$(trim "${line:-}")"
    proxy_url="$(trim "${proxy_url:-}")"
    enabled="$(trim "${enabled:-}")"

    [[ -z "$line" || "$line" == \#* ]] && continue
    [[ "$line" == "line" && "$proxy_url" == "proxy_url" ]] && continue
    is_true "$enabled" || continue

    if [[ -z "$proxy_url" ]]; then
      warn "line '$line' has empty proxy_url; skipping"
      continue
    fi

    LINE_NAMES+=("$line")
    LINE_PROXY_URLS+=("$proxy_url")
  done < "$LINES_FILE"
}

load_targets() {
  local test url expected_codes kind enabled rest
  while IFS=, read -r test url expected_codes kind enabled rest || [[ -n "${test:-}" ]]; do
    test="$(trim "${test:-}")"
    url="$(trim "${url:-}")"
    expected_codes="$(trim "${expected_codes:-}")"
    kind="$(lower "$(trim "${kind:-}")")"
    enabled="$(trim "${enabled:-}")"

    [[ -z "$test" || "$test" == \#* ]] && continue
    [[ "$test" == "test" && "$url" == "url" ]] && continue
    is_true "$enabled" || continue

    if [[ -z "$url" || -z "$expected_codes" || -z "$kind" ]]; then
      warn "target '$test' is incomplete; skipping"
      continue
    fi

    case "$kind" in
      latency | download) ;;
      *)
        warn "target '$test' has unsupported kind '$kind'; skipping"
        continue
        ;;
    esac

    TARGET_NAMES+=("$test")
    TARGET_URLS+=("$url")
    TARGET_EXPECTED_CODES+=("$expected_codes")
    TARGET_KINDS+=("$kind")
  done < "$TARGETS_FILE"
}

should_run_interval() {
  local interval="$1"
  local state_file="$2"
  local now last
  interval="$(int_or_zero "$interval")"
  (( interval > 0 )) || return 1

  now="$(date +%s)"
  last=0
  if [[ -r "$state_file" ]]; then
    read -r last < "$state_file" || true
    last="$(int_or_zero "$last")"
  fi

  if (( now - last >= interval )); then
    printf '%s\n' "$now" > "$state_file"
    return 0
  fi

  return 1
}

probe_once() {
  local line="$1"
  local proxy_url="$2"
  local test="$3"
  local url="$4"
  local expected_codes="$5"
  local kind="$6"
  local max_time curl_status curl_output
  local http_code time_namelookup time_connect time_appconnect
  local time_starttransfer time_total speed_download size_download remote_ip
  local dns connect tls ttfb total speed size success error remote_field
  local escaped_line escaped_test escaped_kind

  max_time="$LATENCY_PROBE_MAX_TIME_SECONDS"
  if [[ "$kind" == "download" ]]; then
    max_time="$DOWNLOAD_PROBE_MAX_TIME_SECONDS"
  fi

  curl_status=0
  curl_output="$(
    curl \
      -x "$proxy_url" \
      --connect-timeout "$CURL_CONNECT_TIMEOUT_SECONDS" \
      --max-time "$max_time" \
      --location \
      --max-redirs 3 \
      --output /dev/null \
      --silent \
      --write-out $'http_code=%{http_code}\ntime_namelookup=%{time_namelookup}\ntime_connect=%{time_connect}\ntime_appconnect=%{time_appconnect}\ntime_starttransfer=%{time_starttransfer}\ntime_total=%{time_total}\nspeed_download=%{speed_download}\nsize_download=%{size_download}\nremote_ip=%{remote_ip}\n' \
      "$url" 2>/dev/null
  )" || curl_status=$?

  http_code=0
  time_namelookup=0
  time_connect=0
  time_appconnect=0
  time_starttransfer=0
  time_total=0
  speed_download=0
  size_download=0
  remote_ip=""

  while IFS='=' read -r key value; do
    case "$key" in
      http_code) http_code="$(int_or_zero "$value")" ;;
      time_namelookup) time_namelookup="$value" ;;
      time_connect) time_connect="$value" ;;
      time_appconnect) time_appconnect="$value" ;;
      time_starttransfer) time_starttransfer="$value" ;;
      time_total) time_total="$value" ;;
      speed_download) speed_download="$value" ;;
      size_download) size_download="$value" ;;
      remote_ip) remote_ip="$(trim "$value")" ;;
    esac
  done <<< "$curl_output"

  dns="$(num_or_zero "$time_namelookup")"
  connect="$(seconds_sub_nonnegative "$time_connect" "$time_namelookup")"
  tls=0.000000
  if [[ "$(num_or_zero "$time_appconnect")" != "0.000000" ]]; then
    tls="$(seconds_sub_nonnegative "$time_appconnect" "$time_connect")"
  fi
  ttfb="$(num_or_zero "$time_starttransfer")"
  total="$(num_or_zero "$time_total")"
  speed="$(num_or_zero "$speed_download")"
  size="$(int_or_zero "$size_download")"

  success=0
  if [[ "$curl_status" -eq 0 ]] && code_expected "$http_code" "$expected_codes"; then
    success=1
  fi

  error=0
  if [[ "$curl_status" -ne 0 ]]; then
    error=1
  fi

  remote_field=""
  if [[ -n "$remote_ip" ]]; then
    remote_field=",remote_ip=$(lp_escape_string_field "$remote_ip")"
  fi

  escaped_line="$(lp_escape_tag "$line")"
  escaped_test="$(lp_escape_tag "$test")"
  escaped_kind="$(lp_escape_tag "$kind")"

  printf 'proxy_probe,line=%s,test=%s,kind=%s success=%si,error=%si,http_code=%si,dns=%s,connect=%s,tls=%s,ttfb=%s,total=%s,speed_download=%s,size_download=%si%s\n' \
    "$escaped_line" \
    "$escaped_test" \
    "$escaped_kind" \
    "$success" \
    "$error" \
    "$http_code" \
    "$dns" \
    "$connect" \
    "$tls" \
    "$ttfb" \
    "$total" \
    "$speed" \
    "$size" \
    "$remote_field"
}

load_lines
load_targets

if [[ "${#LINE_NAMES[@]}" -eq 0 ]]; then
  warn "no enabled lines found in $LINES_FILE"
  exit 0
fi

if [[ "${#TARGET_NAMES[@]}" -eq 0 ]]; then
  warn "no enabled targets found in $TARGETS_FILE"
  exit 0
fi

RUN_LATENCY=0
RUN_DOWNLOAD=0

if should_run_interval "$LATENCY_PROBE_INTERVAL_SECONDS" "$LATENCY_STATE_FILE"; then
  RUN_LATENCY=1
fi

if should_run_interval "$DOWNLOAD_PROBE_INTERVAL_SECONDS" "$DOWNLOAD_STATE_FILE"; then
  RUN_DOWNLOAD=1
fi

for line_index in "${!LINE_NAMES[@]}"; do
  for target_index in "${!TARGET_NAMES[@]}"; do
    kind="${TARGET_KINDS[$target_index]}"
    if [[ "$kind" == "latency" && "$RUN_LATENCY" -ne 1 ]]; then
      continue
    fi

    if [[ "$kind" == "download" && "$RUN_DOWNLOAD" -ne 1 ]]; then
      continue
    fi

    probe_once \
      "${LINE_NAMES[$line_index]}" \
      "${LINE_PROXY_URLS[$line_index]}" \
      "${TARGET_NAMES[$target_index]}" \
      "${TARGET_URLS[$target_index]}" \
      "${TARGET_EXPECTED_CODES[$target_index]}" \
      "$kind"
  done
done
