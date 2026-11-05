# 华山医院 114 号源云端提醒（只提醒，不挂号）

监控陈嬿医生：

- 总院：`hospitalid=17`, `doctorid=16765`
- 虹桥院区：`hospitalid=208`, `doctorid=32470`

数据源是 114 移动端免登录接口，不需要微信 Cookie，不需要手机常亮，不需要电脑开机。

## 部署到 GitHub Actions

### 1. 新建公开仓库

在 GitHub 新建一个 **Public** 仓库，例如：

```text
huashan-114-monitor
```

公开仓库的 Actions 分钟数免费，且本项目不含个人隐私数据。

### 2. 上传本目录

把本目录全部文件上传到仓库，包括隐藏目录：

```text
.github/workflows/monitor.yml
```

使用 git 上传最稳妥：

```bash
cd github-114-monitor
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/你的用户名/huashan-114-monitor.git
git push -u origin main
```

### 3. 配置 Server酱 SendKey

仓库页面：

```text
Settings → Secrets and variables → Actions → New repository secret
```

名称：

```text
SERVERCHAN_SENDKEY
```

值是 `SCT...` 开头的 SendKey。

### 4. 手动测试一次

仓库页面：

```text
Actions → huashan-114-monitor → Run workflow
```

参数：

```text
once = true
dry_run = true
```

先看日志是否能输出：

```text
陈嬿-总院: remainnum=0
陈嬿-虹桥院区: remainnum=0
```

然后把 `dry_run` 改成 `false`，再运行一次，确认手机能收到测试通知。

### 5. 让定时任务运行

不用手动点，GitHub Actions 会按 workflow 里的 cron 自动运行。  
公开仓库免费；如果长时间没有活动，GitHub 可能暂停 schedule，进入 Actions 页面手动 Run 一次即可恢复。

## 提醒逻辑

- `remainnum > 0` 才提醒
- 同一医生默认 15 分钟内不重复提醒
- 每天最多 5 条（Server酱免费额度）
- 17:50—18:15 自动提高到 10 秒一次
- 只提醒，不自动挂号

## 注意

114 的 `remainnum` 是聚合余号，可能包含不同班次/价格；具体日期、时段、价格以 114 页面或华山医院官方渠道为准。

