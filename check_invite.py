#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Elysian Horizon Discord 邀请码监控脚本
=====================================

这个脚本会定期检查指定的 Discord 邀请码（默认是 ``elysianhorizon``）当前
是处于「开放」还是「暂停」状态，并在状态从「暂停」变为「开放」时，通过
Server酱（Server Chan）向你的微信推送通知。

整体流程：
1. 读取上一次保存的状态（保存在 state.json 文件里）。
2. 调用 Discord 官方 API 查询邀请码现在的状态。
3. 对比新旧状态，决定要不要发送通知：
   - 第一次发现「开放」          -> 发送「🚨 Elysian Horizon开放了！」
   - 已经开放且持续超过 30 分钟  -> 发送「⚠️ Elysian Horizon仍然开放中」
4. 把最新状态写回 state.json，供下一次运行时对比。

这个脚本被设计为在 GitHub Actions 里每 10 分钟运行一次。因为 GitHub Actions
的运行环境是「一次性」的（每次跑完就销毁），所以我们把状态保存到仓库里的
state.json 文件中，并在 workflow 里把它提交（commit）回仓库，这样下一次运行
时就能读到上一次的状态了。
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests


# ---------------------------------------------------------------------------
# 配置区：这些值你一般不需要改，如有需要可以通过环境变量覆盖。
# ---------------------------------------------------------------------------

# 要监控的 Discord 邀请码（就是邀请链接 https://discord.gg/XXXX 里的 XXXX 部分）。
INVITE_CODE = os.environ.get("INVITE_CODE", "elysianhorizon")

# Server酱 的 SendKey，从环境变量读取（在 GitHub Secrets 里配置为 SERVERCHAN_SENDKEY）。
SERVERCHAN_SENDKEY = os.environ.get("SERVERCHAN_SENDKEY", "")

# 保存状态的文件名。
STATE_FILE = os.environ.get("STATE_FILE", "state.json")

# 「仍然开放」提醒的间隔（分钟）。开放后每隔这么久就再提醒一次，直到关闭为止。
REMIND_AFTER_MINUTES = int(os.environ.get("REMIND_AFTER_MINUTES", "30"))

# Discord API 地址。with_counts=true 让接口顺便返回服务器的在线/成员人数。
DISCORD_API_URL = f"https://discord.com/api/v10/invites/{INVITE_CODE}?with_counts=true"

# Discord 要求请求里必须带 User-Agent，否则可能会被拒绝。
REQUEST_HEADERS = {
    "User-Agent": "ElysianWatcher/1.0 (+https://github.com/cyanusay/elysian-watcher)"
}


# ---------------------------------------------------------------------------
# 状态读写：把监控状态保存到本地 JSON 文件，方便跨次运行对比。
# ---------------------------------------------------------------------------

def load_state():
    """读取上一次保存的状态。

    如果文件不存在（比如第一次运行），就返回一个「初始状态」。

    状态字段说明：
        status         当前状态："paused"（暂停）或 "open"（开放）。
        open_since     最近一次变为开放的时间（ISO 格式字符串），暂停时为 None。
        notified_open  是否已经发过「开放了」的通知。
        last_remind_at 上次发送「仍然开放」提醒的时间（ISO 格式字符串）。
                       用它来实现「每隔 30 分钟重复提醒一次」。
    """
    if not os.path.exists(STATE_FILE):
        return {
            "status": "paused",       # 题目说明：当前初始状态为「邀请已暂停」。
            "open_since": None,
            "notified_open": False,
            "last_remind_at": None,
        }

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    """把最新状态写回 JSON 文件。"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print(f"[状态] 已保存到 {STATE_FILE}: {state}")


# ---------------------------------------------------------------------------
# 核心：查询 Discord 邀请码当前状态。
# ---------------------------------------------------------------------------

def check_invite_status():
    """查询 Discord 邀请码现在是「开放」还是「暂停/失效」。

    返回字符串 "open" 或 "paused"。

    判断逻辑：
        - Discord 在邀请有效时返回 HTTP 200，并带有完整的邀请信息（含 guild）。
        - 当邀请被暂停（Pause Invites）、失效或不存在时，接口通常返回 404
          并带有错误码（例如 10006 "Unknown Invite"）。
        - 因此：能正常拿到邀请数据 => open；否则 => paused。

    注意：Discord 的「暂停邀请」行为在不同情况下表现可能略有差异，如果将来
    发现判断不准，可以在这里根据实际返回内容调整。
    """
    try:
        resp = requests.get(DISCORD_API_URL, headers=REQUEST_HEADERS, timeout=15)
    except requests.RequestException as e:
        # 网络异常时，为了安全起见当作「暂停」处理，避免误报开放。
        print(f"[警告] 请求 Discord API 失败: {e}")
        return "paused"

    print(f"[查询] HTTP 状态码: {resp.status_code}")

    # 邀请有效：HTTP 200 且响应里没有错误码 code。
    if resp.status_code == 200:
        try:
            data = resp.json()
        except ValueError:
            print("[警告] 响应不是合法 JSON，当作暂停处理。")
            return "paused"

        # 正常的邀请数据里会有 "code" 字段等于邀请码本身，并且包含 guild 信息；
        # 错误响应里 "code" 是一个数字错误码。这里通过有没有 guild 来判断。
        if data.get("code") == INVITE_CODE or "guild" in data:
            print("[查询] 邀请有效 -> 开放(open)")
            return "open"
        print(f"[查询] 返回 200 但内容异常: {data} -> 暂停(paused)")
        return "paused"

    # 其它情况（404 等）一律视为暂停/失效。
    print(f"[查询] 邀请不可用(状态码 {resp.status_code}) -> 暂停(paused)")
    return "paused"


# ---------------------------------------------------------------------------
# 通知：通过 Server酱 推送微信通知。
# ---------------------------------------------------------------------------

def send_notification(title, content=""):
    """通过 Server酱（Server Chan Turbo）发送微信服务通知。

    参数：
        title    通知标题（微信里看到的主标题）。
        content  通知正文，支持 Markdown。

    Server酱 的接口地址是 https://sctapi.ftqq.com/<SendKey>.send
    """
    if not SERVERCHAN_SENDKEY:
        print("[错误] 未配置 SERVERCHAN_SENDKEY，无法发送通知。")
        return False

    url = f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send"
    payload = {"title": title, "desp": content}

    try:
        resp = requests.post(url, data=payload, timeout=15)
        result = resp.json()
    except requests.RequestException as e:
        print(f"[错误] 发送通知请求失败: {e}")
        return False
    except ValueError:
        print(f"[错误] 通知接口返回非 JSON: {resp.text}")
        return False

    # Server酱 成功时返回 {"code": 0, ...}
    if result.get("code") == 0:
        print(f"[通知] 发送成功: {title}")
        return True

    print(f"[错误] 通知发送失败: {result}")
    return False


# ---------------------------------------------------------------------------
# 主流程：把上面的部件组合起来。
# ---------------------------------------------------------------------------

def main():
    # 当前时间（统一用 UTC，避免时区混乱）。
    now = datetime.now(timezone.utc)

    # 1. 读取旧状态。
    state = load_state()
    print(f"[状态] 读取到旧状态: {state}")

    # 2. 查询当前状态。
    current_status = check_invite_status()

    # 3. 根据新旧状态决定要不要发通知。
    if current_status == "open":
        if state["status"] != "open":
            # —— 情况 A：从「暂停」变成「开放」（首次发现开放）——
            print("[判断] 状态变化：暂停 -> 开放，发送首次开放通知。")
            send_notification(
                "🚨 Elysian Horizon开放了！",
                "Discord 邀请码 `elysianhorizon` 现在已经开放，赶紧加入！\n\n"
                f"链接: https://discord.gg/{INVITE_CODE}",
            )
            # 记录开放起始时间，并把「上次提醒时间」设为现在（首次开放通知就算一次提醒），
            # 这样接下来每隔 30 分钟才会再发「仍然开放」提醒。
            state["status"] = "open"
            state["open_since"] = now.isoformat()
            state["notified_open"] = True
            state["last_remind_at"] = now.isoformat()
        else:
            # —— 情况 B：之前就已经开放，检查距离上次提醒是否又过了 30 分钟 ——
            # 用「上次提醒时间」来判断，从而实现每 30 分钟重复提醒一次，直到关闭为止。
            last_remind_at = state.get("last_remind_at") or state.get("open_since")
            if last_remind_at:
                last_remind = datetime.fromisoformat(last_remind_at)
                elapsed_minutes = (now - last_remind).total_seconds() / 60.0
                print(f"[判断] 距离上次提醒约 {elapsed_minutes:.1f} 分钟。")

                if elapsed_minutes >= REMIND_AFTER_MINUTES:
                    print("[判断] 距上次提醒已满间隔，再次发送「仍然开放」提醒。")
                    send_notification(
                        "⚠️ Elysian Horizon仍然开放中",
                        f"Discord 邀请码 `elysianhorizon` 依然处于开放状态，可以加入！\n\n"
                        f"（每 {REMIND_AFTER_MINUTES} 分钟提醒一次，直到关闭为止）\n\n"
                        f"链接: https://discord.gg/{INVITE_CODE}",
                    )
                    # 更新「上次提醒时间」，开始下一个 30 分钟的计时。
                    state["last_remind_at"] = now.isoformat()
            else:
                print("[判断] 仍然开放，但无需再次通知。")
    else:
        # —— 情况 C：当前是暂停状态 ——
        if state["status"] != "paused":
            print("[判断] 状态变化：开放 -> 暂停，重置状态。")
        else:
            print("[判断] 仍然暂停，无需通知。")
        # 重置为暂停状态，清空开放相关记录，方便下次重新开放时能再次提醒。
        state["status"] = "paused"
        state["open_since"] = None
        state["notified_open"] = False
        state["last_remind_at"] = None

    # 4. 保存最新状态。
    save_state(state)


if __name__ == "__main__":
    # 用 try/except 包一层，保证脚本异常时以非 0 退出码结束，便于在 Actions 里发现问题。
    try:
        main()
    except Exception as e:  # noqa: BLE001 - 这里有意捕获所有异常并打印
        print(f"[致命错误] 脚本运行出错: {e}")
        sys.exit(1)
