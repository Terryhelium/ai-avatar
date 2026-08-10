# Git 远程配置

项目目录：D:\SynologyDrive\AG_Workspace\Work\ai-avatar
同名仓库：ai-avatar

## 远程约定

每个项目只使用自己的同名仓库，不复制其他项目的地址。标准远程如下：

| 远程名 | 地址 | 用途 |
|---|---|---|
| `origin` | `https://github.com/Terryhelium/ai-avatar.git` | GitHub 主仓库 |
| `gitea` | `http://192.168.31.217:8080/admin/ai-avatar.git` | 内网 Gitea，同名仓库 |
| `gitea-ext` | `https://gitea.terryhelium.qzz.io/admin/ai-avatar.git` | 公网 Gitea，同名仓库 |

不要把密码、Token、Cookie、登录态或认证 Header 写入 URL、文档、日志、提交或截图。

## 推送前目录边界

所有远程操作都必须在项目自己的 Git 根目录执行。先运行：

```powershell
$gitPrefix = (git rev-parse --show-prefix).Trim()
if ($gitPrefix) { throw "当前目录只是上层仓库的子目录；不得修改上层仓库远程或向同名项目仓库推送" }
```

若命令显示当前项目是上层工作区仓库的子目录，先在该项目目录建立独立仓库并审查首提交，再配置远程：

```powershell
git init -b main
git status --short
git add --all
git status --short
git commit -m "Initial project import"
```

首提交前必须排除本机 `.env`、登录态、密钥、临时目录和其他敏感配置。不要为了“项目同名远程”覆盖上层工作区的 `origin`、`gitea` 或 `gitea-ext`。
## 日常推送

以下脚本推送当前分支到 GitHub，并按网络可达性在两个 Gitea 中只选择一个：

```powershell
git status --short --branch
$branch = (git branch --show-current).Trim()
if (-not $branch) { throw "当前不在有效分支上" }
git push origin $branch

$internalGitea = Test-NetConnection 192.168.31.217 -Port 8080 -InformationLevel Quiet -WarningAction SilentlyContinue
$giteaRemote = if ($internalGitea) { 'gitea' } else { 'gitea-ext' }
git push $giteaRemote $branch
git ls-remote --heads $giteaRemote $branch
```

同一轮不要同时推送 `gitea` 和 `gitea-ext`。内网不可达只表示网络路径不可用，不等于仓库不存在；切换公网远程即可。认证由本机 Git Credential Manager、GitHub CLI 或 Gitea 登录态提供，远程 URL 不嵌入凭据。

## 网络与代理

默认**不使用项目级 Git 代理**。先直连测试；不要把任何代理地址、端口或凭据写入仓库的 `.git/config`。

```powershell
git config --local --unset-all http.proxy 2>$null
git config --local --unset-all https.proxy 2>$null
```

- 在家或其他能访问 `192.168.31.0/24` 的网络：内网 Gitea 走 `gitea`，不使用代理。
- 在外网：公网 Gitea `gitea-ext` 始终直连；GitHub 也先直连。仅当 GitHub 直连失败时，启动 Karing 的系统代理或 TUN 后重试 `origin`，不要改写某个项目的 Git 代理配置。
- 不得复用任何历史项目级代理地址或端口。代理状态变化后直接重试推送，不要把代理 URL 记录到 Git 远程地址或文档。

Git for Windows 不一定读取 Windows 的系统代理。若 Karing 已开启但 GitHub 直连失败，只对该次 GitHub 命令使用 Karing 当前的系统代理端口；不要执行 `git config http.proxy` 或 `git config https.proxy`：

```powershell
$karingProxy = 'http://127.0.0.1:<Karing 当前可用的 HTTP 或混合代理端口>'
git -c http.proxy=$karingProxy -c https.proxy=$karingProxy push origin $branch
```

这只是一次性参数，不会保存到项目或全局 Git 配置；`gitea` 和 `gitea-ext` 不使用这组参数。
可用以下命令先测试当前分支的两个目标：

```powershell
$branch = (git branch --show-current).Trim()
git ls-remote --heads origin $branch
$giteaRemote = if (Test-NetConnection 192.168.31.217 -Port 8080 -InformationLevel Quiet -WarningAction SilentlyContinue) { 'gitea' } else { 'gitea-ext' }
git ls-remote --heads $giteaRemote $branch
```
## 新建项目或补齐仓库

1. 确定仓库名：优先使用已有 GitHub 远程的仓库名；没有远程时使用项目目录名，并转换为稳定的小写连字符形式。
2. GitHub 未创建时，在项目目录执行：

```powershell
$owner = 'Terryhelium'
$repo = 'ai-avatar'
if (-not (gh repo view "$owner/$repo" 2>$null)) {
    gh repo create "$owner/$repo" --private --source . --remote origin
}
```

若 `origin` 已存在但地址错误，先修正：

```powershell
git remote set-url origin https://github.com/Terryhelium/ai-avatar.git
```

3. Gitea 未创建时，在内网或公网 Gitea 的管理界面创建一个**私有、同名**仓库 `admin/ai-avatar`。创建后补齐两个不带凭据的远程：

```powershell
git remote set-url origin https://github.com/Terryhelium/ai-avatar.git
git remote add gitea http://192.168.31.217:8080/admin/ai-avatar.git
git remote add gitea-ext https://gitea.terryhelium.qzz.io/admin/ai-avatar.git
```

如果远程名已经存在，使用 `git remote set-url` 修正，不要重复添加。首次推送仍按“日常推送”中的网络二选一规则执行。

## 检查

```powershell
git remote -v
git ls-remote --heads origin $branch
$giteaRemote = if (Test-NetConnection 192.168.31.217 -Port 8080 -InformationLevel Quiet -WarningAction SilentlyContinue) { 'gitea' } else { 'gitea-ext' }
git ls-remote --heads $giteaRemote $branch
```

只检查当前可达的 Gitea。返回 `404` 时先用已认证的 Git 凭据重试；私有仓库对未登录请求可能同样返回 `404`。







