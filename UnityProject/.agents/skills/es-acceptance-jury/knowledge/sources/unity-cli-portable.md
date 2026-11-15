# Unity CLI便携适配：来源、入口与连接经验

<a id="sources"></a>
## 已核发行源与版本

以下是用户指定的社区适配来源，基于akiojin/unity-cli 0.18.1，不是Unity官方工具。2026-10-16已从GitHub API核到两个公开仓库的v0.18.1-r1及ZIP、`.zip.sha256`资产；本机已有便携包，连接验证未重新下载。2023来源由用户直接提供，2022仓库及精确资产地址经API定位。

| 目标版本 | 来源与安装指南 | 已公开ZIP |
| --- | --- | --- |
| Unity 2022.3；本机实测2022.3.17f1c1 | [仓库](https://github.com/0everey/unity-cli-2022-portable) · [中文安装](https://github.com/0everey/unity-cli-2022-portable/blob/main/INSTALL.zh-CN.md) | [UnityCLI2022-Portable-0.18.1-r1-20261015.zip](https://github.com/0everey/unity-cli-2022-portable/releases/download/v0.18.1-r1/UnityCLI2022-Portable-0.18.1-r1-20261015.zip) |
| Unity 2023.1/2023.2；本机实测2023.2.14f1c1 | [仓库](https://github.com/0everey/unity-cli-2023-portable) · [中文安装](https://github.com/0everey/unity-cli-2023-portable/blob/main/INSTALL.zh-CN.md) | [UnityCLI2023-Portable-0.18.1-r1-20261015.zip](https://github.com/0everey/unity-cli-2023-portable/releases/download/v0.18.1-r1/UnityCLI2023-Portable-0.18.1-r1-20261015.zip) |

本次使用Windows Editor、PowerShell与Python 3.12；安装指南要求Python 3.10+。各包有`Verify.ps1`、`Install.ps1 -Project <工程> -DryRun`、`Install.ps1 -Project <工程>`、`Unity.ps1`、对应`unity2022.py`/`unity2023.py`和`unity-cli.exe`。安装器把Bridge嵌入工程Packages并写manifest，回执与备份在`.unity-cli-portable`，依赖由Unity解析；不是只装一个本机可执行文件。

2022包的依赖基线为Input System 1.7.0、Newtonsoft JSON 3.2.1、Test Framework 1.1.33、UGUI 1.0.0；2023包后两项为1.3.9、2.0.0。已装但低版本、定制依赖来源或已有Bridge需按工程实际协调，旧测试副本的包名/0.18.1版本号不能证明源码已适配。上述基线不证明其它补丁版本、平台或Unity 6兼容。

<a id="local-entry"></a>
## 本机定位线索与实际命令

2026-10-16本机已存在：

| 对象 | 当时路径 |
| --- | --- |
| 2022便携包 | `D:\MyDownload\UnityCLI2022-Portable-0.18.1-r1-20261015` |
| 2023便携包 | `D:\MyDownload\UnityCLI2023-Portable-0.18.1-r1-20261015` |
| PATH中的CLI | `C:\Users\asus\.unity\tools\unity-cli\win-x64\unity-cli.exe` |
| 匹配Editor | `D:\unityeditor\2022.3.17f1c1\Editor\Unity.exe`、`D:\unityeditor\2023.2.14f1c1\Editor\Unity.exe` |

这些是本机查找起点，换机器或目录迁移后可由`Get-Command unity-cli -ErrorAction SilentlyContinue`与实际解压位置继续定位。便携包中的Python包装器可显式绑定目标并校验capabilities返回的工程身份；示例中的两个变量需取当前任务的真实工程及匹配版本的现存包，不填历史验证工程：

```powershell
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
# $unityProject：当前任务工程根目录；$unityPortable：已发现的对应版本便携目录。
# 2023示例；2022换为unity2022.py。
python -X utf8 -B (Join-Path $unityPortable 'unity2023.py') --project $unityProject status
python -X utf8 -B (Join-Path $unityPortable 'unity2023.py') --project $unityProject capabilities
python -X utf8 -B (Join-Path $unityPortable 'unity2023.py') --project $unityProject schema get_editor_info
python -X utf8 -B (Join-Path $unityPortable 'unity2023.py') --project $unityProject call get_editor_info
```

包装器还有`tools`、`schema <工具>`及`call <工具> --params-file <UTF8 JSON>`；写操作超时不能按新请求重发。没有包装器时，CLI的同类入口为`unity-cli --project-path <工程> --output json editor status`、`tool list`、`tool schema <工具>`、`tool call <工具> --params-file <文件>`，以当前`--help`及实时schema为准。CLI默认可能受host/port/project环境变量影响；包装器会清除子进程的`UNITY_CLI_HOST`、`UNITY_CLI_PORT`、`UNITY_PROJECT_ROOT`并禁用自动更新。

MCP stdio启动参数为`<对应unity-cli.exe> --project-path <工程> mcp`。本次通过initialize、tools/list、tools/call get_editor_info，协议2024-11-05。此入口不等于宿主自动发现或永久配置；同机具有Shell的角色可直接走CLI。

<a id="observations"></a>
## 实测边界与可复用失败线索

原始证据位于本机`C:\Users\asus\.codex\task-archives\unity-cli-dual-connect-20261016-002017`，含stdout、MCP transcript、Editor日志和失败记录；本段保留可迁移的事实，不要求运行时能访问该归档。

- 2022与2023各用独立验证工程，实时身份、Editor状态、编译状态、层级及MCP实际读取均成功，当前编译/Console错误计数为0。CLI各列157项，MCP各列154项；未逐项测试全部工具。验证场景分别返回2/4个对象；没有业务工程或Player品质声明。
- 两个Bridge自动避开占用端口，最终用6401/6402，曾有额外旧测试Editor占用6400。实例发现文件在用户目录`.unity-cli/editors/<PID>.json`，含authToken；CLI可自行消费。历史端口/PID及注册表中的down实例不足以指明当前目标。
- 2022首轮CLI open给Editor传入扩展路径前缀，窗口显示File access error且未生成请求日志；用匹配Editor与普通Windows工程/日志路径直接启动成功。后续CLI读取可正常接受同一中文工程路径。遇同症状可沿实际进程/日志核查并改走正常Editor启动，不据此判包完全不可用。
- 一个旧2023验证副本出现`Physics2D.velocityThreshold`的CS0619；日志记录Unity API Updater改写文件并自重启，ProjectVersion/ProjectSettings哈希变化。最终选择源码对应发布包的r2验证工程。启动Editor可能触发导入、API更新或输入提示，不能把启动当纯读取。
- CLI close对额外旧Editor返回Cannot identify the local Editor process；核本次父子进程后用CloseMainWindow正常关闭。此记录不授权按名称批量杀进程。
- 交互式Editor提供Bridge；仅`-batchmode`默认不提供，包支持显式`UNITY_CLI_ALLOW_BATCH_HOST=1`供自己的批处理宿主选择。本次未把他方批处理改作Bridge宿主。
- 最终两个目标均在Input System后端启用提示选择No；未测虚拟输入/物理输入。虚拟输入后端与游戏现有输入设计需要分别核，不能为连通改模式。
- 两版均缺`com.unity.recorder`，有截图和视频接口名称；本次未抓真实帧、录屏、分析连续动效或验证声音。Recorder可从Unity Package Manager按Editor兼容版本接入；本包没有为本次连通安装可选依赖。

执行默认与安装授权见[本机接入规则](../../references/unity-tool-access.md#default-access)，媒体采集方法见[抓帧与连续动效](../../references/capture-motion.md#scope)。
