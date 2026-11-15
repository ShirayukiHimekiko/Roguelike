# 本机Unity工具的默认发现与接入

<a id="default-access"></a>
## 任务命中即主动接入

当前陪审任务需要Editor状态、场景/资源读取、截图或其它Unity操作时，工作AI与执行该项取证的陪审默认主动发现并核验本机入口，不等用户再点名MCP/CLI。纯静态检查不为此启动Editor；同一目标的有效调用证据可共享。已有适用工具优先，Unity 2022.3与2023.1/2023.2缺合适入口时，默认选用[便携包来源与接法](../knowledge/sources/unity-cli-portable.md#sources)处理对应缺口；其它版本按实际兼容性调查，不套旧包。

先核当前委托工程根目录、完整项目级AGENTS、ProjectVersion及已有Bridge/工具；发现当前宿主实际Unity MCP工具及schema。宿主未暴露MCP但有Shell时，继续查项目既有CLI、匹配版本的本机便携包和PATH中的unity-cli，以明确工程路径调用。按[定位与命令](../knowledge/sources/unity-cli-portable.md#local-entry)选真实入口，不把本Skill可读、二进制存在、MCP已登记或以前连通过当当前可达，也不以MCP未注册为由停掉已有CLI路径。

本次发现须绑定当前任务工程；知识中的安装目录是查找线索，验证工程、PID、端口和全局active实例不是默认操作目标。每次调用显式绑定工程路径；环境中的host/port/project覆盖若冲突，只在本次子进程内协调，不泄露发现文件的authToken，不改他方实例或在用端口。

发现入口后，读取并执行[当前可达与交接](#verification)；本机入口、工程Bridge或必要后端缺失时，读取并执行[缺失处理](#missing)。
<!-- jury-read-continue: references/unity-tool-access.md#verification -->

<a id="missing"></a>
## 本机缺失时的默认处理

区分缺本机CLI/匹配适配包、缺目标工程Bridge、Editor未启动/未编译完成、宿主缺Shell/MCP入口，以及可选后端缺包。已有入口能完成任务就继续使用；真实缺失时，同轮给对应[发布包与安装指南](../knowledge/sources/unity-cli-portable.md#sources)、补哪项结果、具体安装/接入动作及装后验证，不只报“本机不可达”。安装与配置沿[既有授权](ai-tooling.md#installation)：已覆盖就直接完成；未覆盖先备好具体方案，仅为必要新增动作询问，不重复索权。此默认选择随Skill固化，不等于每次安装，也不内嵌Unity、CLI二进制或新增宿主权限。

向工程安装Bridge前先核现有接入归属与依赖，使用对应便携包的Verify和Install预览核实际变化；目标Editor正常关闭且项目可写时才执行。已有Bridge不覆盖，活跃锁/租约不删除；连接已有Editor优先，不为取证关闭或重启他方Editor，不默认启用批处理宿主、改输入设置或另开验证工程。确需启动目标时沿其正常工作流及现有授权，保当前唯一writer。

可选功能按本次目标补缺：连续录屏缺Recorder时，主动提出安装`com.unity.recorder`及对应Editor兼容版本，并说明需要后续实录验证；没有当前必要性不安装其它包。截图、解码/取帧与连续动效感知分别按[采集与动效分析](capture-motion.md#scope)处理。
<!-- jury-read-continue: references/unity-tool-access.md#verification -->

<a id="verification"></a>
## 当前可达与交接

先读实时Editor身份/能力，核返回工程路径、Unity及Bridge版本，再执行本次需要的最小实际查询并读业务结果。已有Bridge不提供版本扩展capabilities时，可用get_editor_info等现成查询核身份，不因单个扩展名未知就重装。目录列出工具不证明后端可用；CLI调用、MCP协议调用、宿主暴露工具及游戏结果分别报告。未注册MCP时可以报告CLI可达，不能报告当前宿主已加载Unity MCP；需永久登记才按[配置边界](ai-tooling.md#configuration)改真实配置源并验证。

只在当前任务记录保已核入口、工程/版本、实际调用与未闭及下一动作，交接角色沿同一显式工程入口复用仍有效证据；新会话或目标/进程变化重核受影响事实，不继承历史PID/端口或重放写操作。超时和重连按[执行与恢复](ai-tooling.md#recovery)，连接失败原因可查[实测经验](../knowledge/sources/unity-cli-portable.md#observations)，不把工具不可达判成游戏故障。
