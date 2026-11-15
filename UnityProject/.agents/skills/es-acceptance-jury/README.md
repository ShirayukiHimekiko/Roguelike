# ES Acceptance Jury

一句话安装：把完整ZIP或文件夹交给AI，说“安装这个陪审Skill”。

一句话使用：在当前任务里说“陪审介入”。收尾说“开始收尾”或“开始辩论”；有想法就说“开始考虑：”并接上自己的话。

[打开单页新手教程](assets/tutorial/index.html)：左侧选场景，右侧直接复制短句、看协作动画。离线使用，不调用模型。也可让AI打开教学，或从实际Skill根运行 `python -X utf8 -B scripts/jury_tutorial.py`（浏览器优先，失败打开文件夹）。

当前版本2.9.12，适用于通用中大方案评估、Unity游戏与生产工具链制作及本Skill维护。默认单一用户入口由对话AI本人理解目标／实际产物、判断关键决定与证据盲区、按可审成果统筹并核回结果，后台原生工作AI制作／验证并唯一写正式源，F/A独立审查；普通聊天不另造制作。实际职责、阶段与读取入口见[SKILL.md](SKILL.md)；原需求／独立判断／必要品质与真实消费者结果为准。使用下列工具只准备或读取材料，不代真实角色执行。

本机若要覆盖未调用陪审Skill的普通任务，在实际Codex home的全局AGENTS接自足短规则并引用[唯一正文](references/source-authority.md#grounded-consideration)；本包不替其它机器自动改全局文件。全局指导在会话启动时加载，已有窗口须实际补读，不能冒已热更新所有会话。入口依据见[官方AGENTS说明](https://learn.chatgpt.com/docs/agent-configuration/agents-md)。

本 Skill 的细则面向 AI 执行：人没必要看懂细则，AI 能准确理解并执行即可。

安装/分发保完整目录并核宿主真实发现路径。 选择检查前按[显隐影响相关性](references/verification-scope.md#relevance)在原记录说明实际消费者、可能影响及有据排除；微小改动、不同模块或只有提示文字不免必检，AST相同也不免AI语义／相关行为核查。普通正文小修用`python -X utf8 -B scripts/validate_package.py --structure-only --require-full-integrity`核文件、链接与全量指纹；受影响用例从`scripts/`用`python -X utf8 -B -m unittest <模块.测试类.测试方法>`运行。共享读取/派发的执行逻辑或显式接线、验证器执行逻辑，或其它需代码回归查证的包级技术行为改变时，用`python -X utf8 -B scripts/validate_package.py --require-full-integrity`做完整回归。纯正文语义或声明读集整理另核当前实际读取、必要语义与相称检查，不以重复代码测试代替。已有同版回归且代码、接线、依赖、配置、消费者、声明及原观察条件仍适用的机械复制，可[复用原结果](references/coordination.md#closeout)，另核当前落盘、实际宿主发现/加载、入口读取及受影响消费者；不因叫“同步”自动豁免。首次安装、冷启动或环境/入口/依赖等条件变化、旧证不适用时，补对应未知的安装/运行检查与必要回归；hash和重复单元测试均不代真实宿主消费。测试超时保已捕获stdout/stderr的有界诊断及timeoutSeconds，仍passed=false、不自动重跑或放宽截止。默认超时600秒是退出边界，非耗时预期；历史60秒默认值可能不足。结构/指纹、已运行测试、安装加载与产品结果分别留据，不认证作者、权限或语义。

目录按用途分开：`references/`放当前规则、角色工作卡与方法；[knowledge/index.md](knowledge/index.md)索引领域知识、行业依据与项目经验，包括案例、原话和来源材料；`scripts/`放工具及机器路由配置。规则决定怎么审，知识支撑专业判断与方案推荐；阻断、高风险或高要求时按[知识检索合同](references/reading-guide.md#knowledge-use)必须定向查库并落实下一动作；读取案例不自动采用其项目条件，知识归档不替当前验收。具体边界见[核心分工](SKILL.md#material-boundaries)。

Unity制作/游戏审查按[8+2工作区](references/game-workspaces.md#approach)组织：八块兼顾游戏设计与资源/工具/架构等工程生产，游戏流程、可玩性两个贯穿区核其实际游戏影响。工程交付可独立核证，工程通过不代游戏优质。各区从真实痛点做区分原因的查证，缺资源/工具主动调查权威成熟、Unity常用且合项目的方案并落地。路由schema3唯一登记原32项方法，多块引用保触发来源并去重读取；plan/prepare实际接入工作区正文，不认证游戏品质。

Unity游戏及其生产工具链的方案评估是[核心内置流程](SKILL.md#planning-workflow)：完整读Skill，向用户区分基础功能与细节/进阶功能，实际安排双职责，取得同版明确通过并向用户和实际执行端交接，叠加适用领域读集。本Skill自身维护沿同一[宿主原生派发](references/juror-prompt.md#planning-dispatch)与维护合同，按实际产物核验，不调用游戏域plan/prepare或强造Player；共享方法不扩展为其它行业服务。

核心工具使用Python>=3.10标准库；可选媒体助手另用现有FFmpeg与Pillow，缺能力时按[安装建议](references/ai-tooling.md#installation)主动提出，不自动安装。

双角色首选GPT-6.1 SOL/xhigh；只指定模型时Astra默认high，其它默认xhigh，明确具体选择优先。Unity项目的架构/系统/生态审查按[全项目基线与追踪](references/p0-architecture.md#project-tracking)深查整个项目并接续依赖/证据记录；规则库仍按需，不把项目覆盖缩成当前diff。

- `jury_read.py --section <包内Markdown#锚点>`默认只读指定正文；加 `--follow` 直接接回明确必读续文、去重并整段分页，无需游戏plan。`--measure`仅量字节，`--round-context`只给核心。`--from-plan <绝对plan/prepare.json>` 保留原分页读集，多职责prepare加 `--role progress|architecture`；两种分页都直接沿 `nextArgs`继续。默认每页正文24KiB（不含JSON元数据），单段超额明确给完整接回方式；输入变化拒旧续页，需重新读取当前批。普通链接不自动跟随，返回材料不证明已读／理解。
- `jury_io.py --current <本责current> --candidate <已保存候选> --history <保史目录>`按明确原根保raw、stage读回再单文件替换；错误返回phase，commit-outcome-unverified先核终态不自动重放。`jury_read.py --emit-page N --emit-bytes B`按最终封装字节取完整JSON片段，逐页按outputSHA256重组后才消费内层nextArgs；不删必要意见、不认证已读，也不拦截宿主其它调用或大聚合。
- `jury_media.py doctor|capture|sample`核媒体依赖、按明确窗口/区域录屏及按实际时标取帧，输出原尺寸帧/联系表/变化信号；sample须显式`--every`选择采样，`--reuse`可只读接续同输入/工具/参数且完整未改的产物；用法及连续观察边界见[抓帧与动效分析](references/capture-motion.md#helper)。不自动判品质，Windows采集入口无音频；doctor不安装依赖，capture的dry-run不录屏。
- `jury_candidates.py inspect|plan --role progress|architecture|both --block <命中块> --template U1`给Unity生产审查的声明选择；单角色首轮读自己的P0执行合同/摘要及共同裁定，F方法在p0-progress、A方法在p0-architecture。--product 当前适用ID展开自己的方法，拒绝错角色选择；角色工作卡保执行义务/工作块导航，不签已发生P0或已审查通过。
- `jury_review_roles.py packet|prepare`：默认independent-first与领域general，首发nativeTasks/taskText；源绑定用户指定/成熟工作/控制原件首发，新推断后交，原schema本职动作保持，来源由caller核，不新增表单门。旧完整材料显式inputMode=legacy-complete。--role/--view选材料，--emit-page/--emit-bytes绑定最终JSON。见[任务包](references/juror-prompt.md#task-packet)。

初期路线评估明确`--review-stage planning`，成熟路线详审明确review；省略不再兼容静默详审。实际taskId/waveId、原文/来源、结果/原件/边界、assignments的result/firstAction/methods沿[任务包](references/juror-prompt.md#task-packet)交人消费。阶段/ready只表示材料声明，不能代原生收发、理解、品质或授权。
- `jury_session.py relay-message --source-file <绝对原件> --source-role <真实来源>`可多源，`--draft-file <绝对拟稿>`逐字核生成正文，失败给有界首差定位；加 `--check-receipts` 同次完成原件格式存在预检，仅对相同原件集合／hash复用成功receiptCheck、免再单调check-roles；最终排版与必要意见仍逐源核。`check-message --message-file <绝对正文>`只核可见正文存在，均不发送/认证语义或来源全集。
- `jury_session.py check-roles --draft-file <拟发正文> --receipt-file <真实回传原件>`可重复传回执；含角色标识却漏参时返回`receipt-required`（退出码2），先补核真实原件，未证来源只暂缓其角色转述。只检查至少一份所声明UTF-8原件可读且非空：`.json`须合法标准JSON并非null/空串/空白串/空容器，其余按非空白文本接收，不按Markdown渲染。保绝对路径及4MiB限制，原字节指纹不变；一文件可含多源。`receiptAuthenticated=false`及`receiptCoverageVerified=false`，不认证身份、逐源覆盖或已经发送，统筹仍须逐源核真实创建、发送和已收到原文。

当前撤销旧单链session/checkpoint、模型缓存、Stop Hook、日志/队列适配、旧合同重播及旧叶CLI/别名。历史完整包、原意见、版本和未闭在本次包外归档保全；不在本Skill另建兼容嵌套。旧接口明确退役不妨碍具名新问题调查；历史原件按当时合同解释，不回写为新通过。当前Unity领域正文及U操作卡按真实命中读，不默认扩读旧索引。

重整只改陪审包，未修/运行原游戏，也不关闭原0分、独立否决、Player/预算/AV/存档等产品未闭；包体/默认读取量是可量字节，不能冒Token、未来检出率或等待收益。维护政策见[维护须知](references/skill-improvement.md)，授权条款见[使用授权](使用授权.md)。

原生prepare的顶层`roles`仅返回本次所选职责并保请求顺序，选中条目的字段仍保留；`inspect`继续提供完整双职责目录。依赖未选角色目录的外部调用须改从inspect取得发现信息，字段键不变不代表目录语义完全无兼容影响。防遗忘Reminder仍保留，任务细则按当前动作取读；缓存维护沿[真实空闲旁支](references/evidence-lifecycle.md#idle-cache)，不挡无关制作主线。

读取／plan／prepare在同一命令内共享稳定输入与段解析，返回前复核所用字节；下一命令新读，不保跨任务缓存。该复用减少内部打开和解析，不改变九Reminder、材料ready、真实身份与实际审查的边界。

用户展示由前台实际发送。先`select-opinion`选本人具名当前源；同波修订由本人jury-current明确替代关系。`compose`/`probe --audience user`带预期task/wave，消费完整messageText和逐源双basis/必要限制/root本人回应；`check-user-view`核实际draft可见保真，实际公开仍由消费者读回。`probe`默认internal历史可读，声明投影不冒真实准停。具体命题、考虑/回件、争议恢复与单责/历史正常边界见[呈现入口](references/message-style.md#user-facing)。
本次prepare有明确字段迁移：roles/dispatch不再带displayBoundary、displayLayout、displayRoleTitle、messageContractVersion这组用户格式字段，改给factContractVersion=1、presentationOwner=dialogue及呈现命令定位；依赖旧展示字段的调用者改从前台probe视图取得格式。schemaVersion=3、F/A选择/顺序/模型/真实身份边界不变，不宣称旧展示字段完全兼容。

- `jury_candidates.py route --domain general|maintenance|unity --role 本人 --review-stage planning|review`与`jury_read --profile`共用readProfiles；外部current用--material-file与精确--material-anchor/--json-pointer，typed probe不猜多历史块。
