#!/usr/bin/env python3
"""华山医院 114 号源云端监控（只提醒，不挂号）。

数据源：114 名医导航移动端免登录接口
通知：Server酱（环境变量 SERVERCHAN_SENDKEY）
运行：GitHub Actions 或普通 Python
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Asia/Shanghai")
API = "https://m.114-91.com/common/api"
STATE = ROOT / "state.json"

HEADERS_LIST = {
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
        "Mobile/15E148 Safari/604.1"
    ),
    "Referer": "https://m.114-91.com/doctor/list",
    "Accept": "application/json, text/plain, */*",
}
HEADERS_DETAIL = dict(HEADERS_LIST, Referer="https://m.114-91.com/doctor/detail")


def log(message: str) -> None:
    print(f"{datetime.now(TZ).strftime('%Y-%m-%d %H:%M:%S')} | {message}", flush=True)


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as file:
        return json.load(file)


def fetch_json(url: str, headers: dict[str, str]) -> Any:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw)
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(str(last_error))


def list_url(doc: dict[str, Any]) -> str:
    params = {
        "cmd": "DoctorList",
        "sr": 1,
        "keyword": doc["keyword"],
        "hospitalid": doc["hospitalid"],
        "ipage": 1,
        "pagesize": 20,
        "sectiontype": 0,
    }
    return API + "?" + urllib.parse.urlencode(params)


def detail_url(doctorid: int) -> str:
    return API + "?" + urllib.parse.urlencode(
        {"cmd": "DoctorDetailApp", "doctorid": doctorid}
    )


def find_doctor(data: Any, doctorid: int) -> dict[str, Any] | None:
    if not isinstance(data, dict):
        return None
    for item in data.get("list", []) or []:
        if not isinstance(item, dict):
            continue
        try:
            if int(item.get("id")) == int(doctorid):
                return item
        except Exception:
            continue
    return None


def detail_summary(doctorid: int) -> str:
    try:
        data = fetch_json(detail_url(doctorid), HEADERS_DETAIL)
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    clinics = data.get("cliniclist")
    if not isinstance(clinics, list) or not clinics:
        return str(data.get("clinicinfo", "") or "")
    lines = []
    for item in clinics[:10]:
        if not isinstance(item, dict):
            continue
        parts = []
        for key, label in (
            ("date", "日期"),
            ("week", "星期"),
            ("time", "时段"),
            ("type", "门诊"),
            ("regfee", "费用"),
            ("remainnum", "余号"),
            ("status", "状态"),
        ):
            value = item.get(key)
            if value not in ("", None):
                parts.append(f"{label}={value}")
        if parts:
            lines.append("；".join(parts))
    return "\n".join(lines[:10])


def send_serverchan(sendkey: str, title: str, content: str) -> bool:
    if not sendkey:
        log("未配置 SERVERCHAN_SENDKEY，跳过推送")
        return False
    body = urllib.parse.urlencode({"title": title, "desp": content}).encode("utf-8")
    request = urllib.request.Request(
        f"https://sctapi.ftqq.com/{sendkey}.send",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            text = response.read().decode("utf-8", errors="replace")
        log(f"Server酱返回：{text[:250]}")
        return True
    except Exception as exc:
        log(f"Server酱失败：{exc}")
        return False


def today() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")


def in_window(now: datetime, start: str, end: str) -> bool:
    return dt_time.fromisoformat(start) <= now.time().replace(tzinfo=None) <= dt_time.fromisoformat(end)


def load_state() -> dict[str, Any]:
    if STATE.exists():
        try:
            return load_json(STATE)
        except Exception:
            pass
    return {"doctors": {}, "daily": {"date": "", "sent": 0}}


def save_state(state: dict[str, Any]) -> None:
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def current_interval(config: dict[str, Any], now: datetime) -> float:
    for window in config.get("release_windows", []) or []:
        if in_window(now, str(window.get("start")), str(window.get("end"))):
            return float(window.get("interval", 10))
    return float(config.get("poll_interval_seconds", 60))


def check_all(
    config: dict[str, Any],
    state: dict[str, Any],
    sendkey: str,
    dry_run: bool = False,
    service_messages: bool = True,
) -> None:
    now = datetime.now(TZ)
    if state.get("daily", {}).get("date") != today():
        state["daily"] = {"date": today(), "sent": 0, "heartbeat_date": ""}

    total = 0
    success_count = 0
    failure_count = 0
    remain_lines: list[str] = []
    error_lines: list[str] = []

    for doc in config.get("doctors", []) or []:
        total += 1
        label = str(doc.get("label", doc.get("keyword", "")))
        doctorid = int(doc.get("doctorid"))
        try:
            data = fetch_json(list_url(doc), HEADERS_LIST)
            item = find_doctor(data, doctorid)
            if item is None:
                log(f"{label}: 未返回该医生")
                failure_count += 1
                error_lines.append(f"{label}: 未返回医生")
                continue
            remain = int(item.get("remainnum", 0) or 0)
            success_count += 1
        except Exception as exc:
            log(f"{label}: 查询失败 {exc}")
            failure_count += 1
            error_lines.append(f"{label}: {exc}")
            continue

        remain_lines.append(f"{label}: remainnum={remain}")
        dstate = state.setdefault("doctors", {}).setdefault(
            str(doctorid), {"last_remain": 0, "last_alert": None}
        )
        previous = int(dstate.get("last_remain", 0) or 0)
        dstate["last_remain"] = remain
        log(f"{label}: remainnum={remain}")
        if remain <= 0:
            continue

        cooldown = float(config.get("alert_cooldown_minutes", 15)) * 60
        last_alert = dstate.get("last_alert")
        if last_alert:
            try:
                gap = (now - datetime.fromisoformat(last_alert)).total_seconds()
                if gap < cooldown:
                    log(f"{label}: 有号，但提醒冷却中")
                    continue
            except Exception:
                pass
        if state["daily"]["sent"] >= int(config.get("daily_push_cap", 5)):
            log(f"{label}: 有号，但达到每日推送上限")
            continue

        summary = detail_summary(doctorid)
        if summary:
            content = (
                f"114 显示 {label} 当前余号：{remain}\n"
                f"具体排班：\n{summary}\n"
                "请打开 114 名医导航或华山医院微信确认。"
            ).strip()
        else:
            content = (
                f"114 显示 {label} 当前余号：{remain}\n"
                "114 暂未返回具体日期/时段，请打开页面确认是哪一天。"
            ).strip()
        if not dry_run and send_serverchan(sendkey, f"陈嬿有号：{label}", content):
            state["daily"]["sent"] += 1
            dstate["last_alert"] = now.isoformat(timespec="seconds")

    if service_messages and not dry_run:
        # 连续失败（所有医生都失败）时告警；6 小时内部重复。
        if total > 0 and success_count == 0:
            last_failure = state.get("failure_alert_ts")
            should_send = True
            if last_failure:
                try:
                    gap = (now - datetime.fromisoformat(last_failure)).total_seconds()
                    should_send = gap >= 6 * 3600
                except Exception:
                    pass
            if should_send:
                if send_serverchan(
                    sendkey,
                    "华山114云端监控异常",
                    "所有医生查询均失败：\n" + "\n".join(error_lines[:5]),
                ):
                    state["failure_alert_ts"] = now.isoformat(timespec="seconds")

        # 每天 12:00 左右发一条平安简报（使用 1 条免费额度）。
        daily = state["daily"]
        if (
            success_count > 0
            and now.hour == 12
            and now.minute < 10
            and daily.get("heartbeat_date") != today()
            and daily.get("sent", 0) < int(config.get("daily_push_cap", 5))
        ):
            content = "云端监控正常运行。\n" + "\n".join(remain_lines)
            if send_serverchan(sendkey, "华山114云端监控平安简报", content):
                daily["heartbeat_date"] = today()
                daily["sent"] += 1

    save_state(state)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-push", action="store_true")
    parser.add_argument("--loop-minutes", type=int, default=330)
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    config = load_json(config_path)
    sendkey = os.environ.get("SERVERCHAN_SENDKEY", "").strip()
    state = load_state()

    if args.test_push:
        ok = send_serverchan(
            sendkey,
            "华山114云端监控测试",
            "GitHub Actions 已成功运行，手机提醒通道正常。",
        )
        return 0 if ok else 2

    if args.once:
        check_all(config, state, sendkey, dry_run=args.dry_run, service_messages=True)
        return 0

    started = time.monotonic()
    log(f"云端监控启动，循环 {args.loop_minutes} 分钟")
    while (time.monotonic() - started) / 60 < args.loop_minutes:
        now = datetime.now(TZ)
        active = in_window(
            now,
            str(config.get("active_hours", {}).get("start", "07:00")),
            str(config.get("active_hours", {}).get("end", "22:30")),
        )
        if active:
            try:
                check_all(config, state, sendkey, dry_run=args.dry_run)
            except Exception as exc:
                log(f"本轮异常：{exc}")
            interval = current_interval(config, now)
        else:
            interval = 300
        time.sleep(max(5.0, interval) + random.uniform(0, 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

