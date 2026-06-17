# Elysian Watcher 🛰️

一个用来**监控 Discord 邀请码状态**的小项目。它会每 10 分钟自动检查指定的
Discord 邀请码（默认是 `elysianhorizon`）是处于「邀请已暂停」还是「开放」状态，
并在状态从**暂停**变为**开放**时，通过 [Server酱](https://sct.ftqq.com/) 给你的
**微信**发送服务通知。

> 适合新手：全部用 Python 编写，部署在 GitHub Actions 上，**不需要自己的服务器**，
> 而且完全免费。

---

## ✨ 功能特性

- ✅ **纯 Python 实现**，依赖极少（只用到 `requests`）。
- ✅ **GitHub Actions 每 10 分钟自动运行一次**，无需手动操作。
- ✅ 通过 Discord 官方 API 检查邀请码是否开放。
- ✅ 当前初始状态为「邀请已暂停」。
- ✅ **状态从暂停变为开放时**自动推送通知：
  - 第一次发现开放：`🚨 Elysian Horizon开放了！`
  - 之后只要还开着，**每隔 30 分钟重复提醒一次**：`⚠️ Elysian Horizon仍然开放中`（直到再次关闭为止）
- ✅ 使用 **Server酱** 推送到微信。
- ✅ 状态保存在仓库的 `state.json` 中，自动跨运行记忆。

---

## 🧩 工作原理

```
GitHub Actions 定时器（每 10 分钟）
        │
        ▼
  运行 check_invite.py
        │
        ├─ 读取上次状态 (state.json)
        ├─ 调用 Discord API 查询邀请码状态
        ├─ 对比新旧状态，决定是否发通知
        │     ├─ 暂停 → 开放      ：发送「🚨 开放了！」
        │     └─ 仍然开放（每30分钟）：发送「⚠️ 仍然开放中」
        ├─ 通过 Server酱 推送到微信
        └─ 把新状态写回 state.json 并提交回仓库
```

由于 GitHub Actions 每次运行的环境都是全新的、用完即销毁，所以脚本会把状态保存到
仓库里的 `state.json` 文件，并在每次运行结束后由工作流自动 `commit` 回仓库。
这样下一次运行就能读到上一次的状态，从而判断「是不是刚刚才开放」以及「已经开放多久了」。

---

## 📁 项目结构

```
elysian-watcher/
├── check_invite.py            # 核心脚本：检查状态 + 发送通知
├── requirements.txt           # Python 依赖清单
├── state.json                 # 保存当前监控状态（会被自动更新）
├── README.md                  # 就是你正在看的这份文档
└── .github/
    └── workflows/
        └── check.yml          # GitHub Actions 定时任务配置
```

---

## 🚀 部署步骤（新手向，照着做即可）

### 第 1 步：获取 Server酱 的 SendKey

1. 打开 [Server酱官网](https://sct.ftqq.com/)。
2. 使用微信扫码登录。
3. 登录后在「**SendKey**」页面可以看到你的密钥，形如 `SCT123456xxxxxxxxxxxxxxxxxxxx`。
4. **复制这个 SendKey**，下一步要用到。
5. （建议）在「消息通道」里绑定并测试一下，确保微信能收到通知。

### 第 2 步：把项目放到你自己的 GitHub 仓库

你有两种方式：

**方式 A：Fork 本仓库**
- 直接点击页面右上角的 **Fork** 按钮，复制一份到你自己的账号下。

**方式 B：新建仓库并上传文件**
1. 在 GitHub 上点 **New repository** 新建一个仓库。
2. 把本项目的所有文件（`check_invite.py`、`requirements.txt`、`state.json`、
   `README.md`、`.github/workflows/check.yml`）上传上去。

### 第 3 步：配置 Secrets（填入 SendKey）

这是**最关键**的一步，把你的 SendKey 安全地告诉 GitHub：

1. 进入你的仓库页面，点击顶部的 **Settings**（设置）。
2. 左侧菜单选择 **Secrets and variables → Actions**。
3. 点击 **New repository secret**（新建仓库密钥）。
4. 填写：
   - **Name（名称）**：`SERVERCHAN_SENDKEY`  ← 必须**完全一致**，注意大小写！
   - **Secret（值）**：粘贴你在第 1 步复制的 SendKey。
5. 点击 **Add secret** 保存。

> ⚠️ 名称必须正好是 `SERVERCHAN_SENDKEY`，否则脚本读不到，会无法发送通知。

### 第 4 步：开启 GitHub Actions

1. 进入仓库的 **Actions** 标签页。
2. 如果看到提示「Workflows aren't being run on this forked repository」，
   点击绿色按钮 **I understand my workflows, go ahead and enable them** 启用。
3. 启用后，定时任务（每 10 分钟）就会开始自动运行了。

### 第 5 步：手动测试一次（可选但推荐）

不想等 10 分钟？可以手动触发一次来验证配置是否正确：

1. 进入 **Actions** 标签页。
2. 左侧选择 **Check Discord Invite** 工作流。
3. 点击右侧的 **Run workflow** 按钮，再点一次确认。
4. 等待运行完成，点进去查看日志（Log），确认脚本正常运行、没有报错。

完成！之后只要邀请码从「暂停」变为「开放」，你的微信就会收到通知 🎉

---

## ⚙️ 可选配置（高级）

脚本支持通过环境变量自定义行为，一般保持默认即可。如需修改，可以在
`.github/workflows/check.yml` 的运行步骤里通过 `env:` 添加：

| 环境变量              | 说明                                | 默认值            |
| --------------------- | ----------------------------------- | ----------------- |
| `INVITE_CODE`         | 要监控的 Discord 邀请码             | `elysianhorizon`  |
| `SERVERCHAN_SENDKEY`  | Server酱 的 SendKey（**必填**）     | 无                |
| `REMIND_AFTER_MINUTES`| 「仍然开放」重复提醒的间隔（分钟）   | `30`              |
| `STATE_FILE`          | 状态文件名                          | `state.json`      |

### 修改检查频率

打开 `.github/workflows/check.yml`，找到这一行：

```yaml
- cron: "*/10 * * * *"
```

`*/10` 表示每 10 分钟。例如改成 `*/30` 就是每 30 分钟检查一次。

> 说明：GitHub Actions 的定时任务用的是 **UTC 时间**，并且在平台繁忙时可能延迟几分钟，
> 这属于正常现象。

---

## 🛠️ 本地运行（用于调试）

如果你想在自己电脑上先跑一下试试：

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 设置 SendKey（Linux / macOS）
export SERVERCHAN_SENDKEY="你的SendKey"

# Windows PowerShell 用：
# $env:SERVERCHAN_SENDKEY="你的SendKey"

# 3. 运行脚本
python check_invite.py
```

运行后会在当前目录生成/更新 `state.json`，并在控制台打印检查过程的日志。

---

## ❓ 常见问题（FAQ）

**Q：为什么我没收到通知？**
- 确认 `SERVERCHAN_SENDKEY` 这个 Secret 名称拼写完全正确。
- 确认 Server酱 已绑定微信，并能在官网「测试」里收到消息。
- 只有在状态**从暂停变为开放**时才会通知；如果一直是暂停，是不会有消息的（这是正常的）。

**Q：定时任务没有按时运行？**
- GitHub 对定时任务（schedule）有一定延迟，尤其在整点等高峰期，延迟几分钟是正常的。
- 长期没有任何提交活动的仓库，GitHub 可能会暂停其定时任务；偶尔手动跑一次即可。

**Q：邀请码状态是怎么判断开放还是暂停的？**
- Discord 在「暂停邀请」时**仍然返回 HTTP 200** 和完整的服务器数据，所以**不能只看状态码**。
- 真正的标志是返回数据里 `guild.features` 数组是否包含 `INVITES_DISABLED`：
  包含则为**暂停**，不包含则为**开放**。
- 相关逻辑在 `check_invite.py` 的 `check_invite_status()` 函数里，有详细注释，可按需调整。

---

## 📄 许可证

本项目仅供学习与个人使用。
