#!/usr/bin/env bash

shopt -s extglob

warn() {
  printf 'proxy_probe: %s\n' "$*" >&2
}

trim() {
  local value="${1:-}"
  value="${value//$'\r'/}"
  value="${value##+([[:space:]])}"
  value="${value%%+([[:space:]])}"
  printf '%s' "$value"
}

lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

is_true() {
  local value
  value="$(lower "$(trim "${1:-}")")"
  case "$value" in
    true | 1 | yes | y | enabled) return 0 ;;
    *) return 1 ;;
  esac
}

lp_escape_tag() {
  local value="${1:-unknown}"
  value="${value//$'\n'/ }"
  value="${value//$'\r'/ }"
  value="${value//$'\t'/ }"
  value="${value//\\/\\\\}"
  value="${value//,/\\,}"
  value="${value// /\\ }"
  value="${value//=/\\=}"
  printf '%s' "$value"
}

lp_escape_string_field() {
  local value="${1:-}"
  value="${value//$'\n'/ }"
  value="${value//$'\r'/ }"
  value="${value//$'\t'/ }"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  printf '"%s"' "$value"
}

num_or_zero() {
  local value="${1:-0}"
  if [[ "$value" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
    printf '%.6f' "$value"
  else
    printf '0.000000'
  fi
}

int_or_zero() {
  local value="${1:-0}"
  if [[ "$value" =~ ^[0-9]+$ ]]; then
    printf '%d' "$((10#$value))"
  elif [[ "$value" =~ ^[0-9]+[.][0-9]+$ ]]; then
    printf '%d' "$((10#${value%%.*}))"
  else
    printf '0'
  fi
}

seconds_sub_nonnegative() {
  local left right
  left="$(num_or_zero "${1:-0}")"
  right="$(num_or_zero "${2:-0}")"
  awk -v left="$left" -v right="$right" 'BEGIN {
    value = left - right
    if (value < 0) value = 0
    printf "%.6f", value
  }'
}

code_expected() {
  local code expected raw accepted
  code="$(int_or_zero "${1:-0}")"
  expected="${2:-}"
  IFS='|' read -r -a accepted <<< "$expected"

  for raw in "${accepted[@]}"; do
    if [[ "$(int_or_zero "$(trim "$raw")")" == "$code" ]]; then
      return 0
    fi
  done

  return 1
}
