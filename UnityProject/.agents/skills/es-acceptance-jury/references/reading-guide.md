# 按需读取

对话AI、后台工作AI与实际陪审亲读完整`SKILL.md`，有效旧读复用，变化补受影响段。本页只定义实际读集；工作端负责制作，不代演双陪审或默认全读双方P0。多人共用事实，各角色亲读自己适用正文，不能由同伴已读替代。

<a id="first-round"></a>
## 角色／阶段读取定位

先完整亲读SKILL，先定本人职责、阶段、领域，再消费同源读集；SKILL已直达下列组合，本定位保留供旧入口接续。有效旧读复用，变化只补受影响段。工作端不代读双陪审，本人不默认载另一职责规则。

| 当前角色／阶段 | 实际入口 |
| --- | --- |
| 对话统筹 | [本人角色卡](dialogue-coordinator.md#dialogue-duty)；制作派发／接续再接[分工](window-interaction.md) |
| 后台工作端接回／制作 | [工作端](#worker-round) |
| 方案评估（通用任务、Unity或本Skill维护） | [方案](#planning-round)；Unity再接[领域](#unity-planning) |
| Unity制作／采用／审查的F或A | [制作](#unity-round)的本人合同 |

再按[对象触发](#task-additions)追加；普通链接不全库展开，明确续文需实际读。工具边界取[reader合同](#reader-contract)。

读取选择由`scripts/candidate-routing.json`的`readProfiles`统一承担，`jury_candidates.py route --domain general|maintenance|unity --role worker|dialogue|progress|architecture --review-stage planning|review`返回当前读集，`jury_read --profile`直接消费该结果。领域是适用读集；packet的currentScope.kind保持原非空身份标签，不推导领域/授权。prepare的宿主/模型控制scope仍按原四容器合同核，不把其枚举前移到纯材料生成。旧Unity `plan`默认保Unity，通用规划显式general；不相关领域不载游戏P0/8+2/全项目基线。


<a id="worker-round"></a>
## 工作端

先取得当前有效原需、原记录及本人制作职责；方案触发才进入[评估](#planning-round)。Unity／实际项目动作按触发表接项目理解，Skill维护不自动载游戏项目基线。

<!-- jury-read-continue: references/worker-execution.md#worker-duty -->
<!-- jury-read-continue: references/task-plan.md#consume -->
<!-- jury-read-continue: references/source-authority.md#current-mainline -->
<!-- jury-read-continue: references/must-read-work-priority.md#core-loop-progress -->
<!-- jury-read-continue: references/coordination.md#message-delivery -->
对象新增或条件改变时回[触发表](#task-additions)选择受影响正文，不预读无关专题。


<a id="planning-round"></a>
## 方案评估组合

实际读下列续文与本人[F0](progress-correctness.md#obligations-progress)或[A0](architecture-ecology-playability.md#obligations-architecture)，不重复列同义草案。Unity另接[方案领域](#unity-planning)；通用方案按自身专业来源、成果与消费者，Skill维护按当前包与消费者核，二者不载游戏全库。定案按[开工](task-plan.md#start-readiness)完成同版双认可及工作端承接。

各自然成果只补本人承担的变化／反证，已有效检查复用。越出主责的决定性事实立即转对应职责，不用边界推开已见失败；未获可靠专业证据就不给该项通过，交具名补供给。完整目标由对话AI在原记录整合，任何未接／未查必要结果都不能被两票open0抹掉。

需要改采用／路线时给原件、影响及可执行后继，推荐不自带路线指令权；任何人的决定性反证都能推翻当前许可。原发现职责核修正，但其判断被同件反证时须重核或撤回，不能用“只有我能关”护旧票。不能只看作者已报问题，也不为角色名义凑打回。

当前[元素模型](recognition.md#unit-state)按本责实际关系核，不以字段齐签整体；交付与停止和本次结果审查[一次接回](review-completion.md#completion-coverage)，保本人已查／未查及原评分事件，不重复两份完整誓言。

<!-- jury-read-continue: references/task-plan.md#plan-evaluation -->
<!-- jury-read-continue: references/source-authority.md#current-mainline -->
<!-- jury-read-continue: references/coordination.md#independent-input -->
<!-- jury-read-continue: references/coordination.md#message-delivery -->
<!-- jury-read-continue: references/review-standard.md#decision-order -->


<a id="unity-planning"></a>
## Unity方案：先判断路线与当前关键关系

先从完整原需和原始产物独立判断路线值不值得制作、品质是否有可达依据，核机制／内容／空间／反馈怎样整合及最薄弱前提；即使作者稿平庸、摘要重工程，仍给具体目标内改进路线，不能等工作端先变好。F/A具体职责只取本人角色卡。

本人P0合同和摘要、共同P0、项目权威／权限／来源／旧消费者及关键能力供给仍须实际读查；已知风险立即限制依赖动作。读适用合同不等于先完成每个后续模块详审：优先查能改变选路、推翻必要品质可达性或影响当前安全开工的未知，详细审计按制作／采用／交付的真实依赖接续。完整项目认可仍须完整基线，限定路线初判不代普通生产许可。

**已停用的通用前置用法：全模块详审或候选目录先清完，才允许给初期路线判断。** 这不取消任何实际必要保护／最终覆盖，也不统一加试样、代表段、多方案或签字轮。成熟有效依据可直接支持整合首版；显式指定的相关block/product/symptom/template继续合取，不能借规划用途绕过当前风险。

使用工具时，普通`plan --review-stage planning`与`prepare`输入`reviewStage="planning"`共用本组合；成熟详审明确review，省略返回stage-unresolved由caller先判当前工作。实际原需／原件及本职首作业沿[任务包](juror-prompt.md#task-packet)交齐；不让兼容默认代选题，也不新增用户批准。工具只准备材料，不认证调查、路线、身份或权限。后续切review按[制作组合](#unity-round)接必要详审，复用有效旧证，不以阶段化遗忘未闭。

<!-- jury-read-continue: references/game-workspaces.md#approach -->
<!-- jury-read-continue: references/game-workspaces.md#flow -->
<!-- jury-read-continue: references/game-workspaces.md#playability -->
<!-- jury-read-continue: references/project-understanding.md#project-fit -->
<!-- jury-read-continue: references/verification-scope.md#relevance -->
<!-- jury-read-continue: references/reading-guide.md#knowledge-use -->

<a id="unity-round"></a>
## Unity制作／游戏审查组合

用于实际制作、采用及成果审查；初期方案先用[方案领域组合](#unity-planning)，不能把本组合无差别前移成路线讨论门槛。当前风险或动作依赖已需详查时立即进入相应正文。

SKILL.md、[工作区方法](game-workspaces.md#approach)与两个贯穿区（[游戏流程](game-workspaces.md#flow)、[可玩性／可用性](game-workspaces.md#playability)）、[项目事实与推荐边界](project-understanding.md#project-fit)、自己的P0执行合同及products摘要（进度读[p0-progress](p0-progress.md#review-contract)，架构读[p0-architecture](p0-architecture.md#review-contract)）、[P0共同裁定与阻断](p0-review.md#review-contract)、candidate-mechanism的selection/candidate-contract/blocks、角色工作卡的obligations、review-standard的decision-order。各自先按[问题线索](review-perspectives.md#exploration-first)主动搜索同类问题，未发现后按[机制与前提](review-methods.md#method-match)精确匹配自己的methodSelector并实际查证（plan --role progress|architecture --product ID）；不默认加载另一角色合同/五项方法。按命中工作区追项目痛点、区分疑因并给具体采用/修正；缺工具按[能力调查](project-understanding.md#capability-fit)自主研究成熟方案并落地，工程必要性不先索玩家故障，U卡供原因核查，不代替搜索或具体匹配；规则库不默认全读。缺运行先分析[可用源码、资产与截图](review-methods.md#available-evidence)。跨职责事实须当轮转交，各自亲查；旧读仍适用则复用，正文变化补受影响部分。

“规则库按需”及阶段化不缩减目标项目最终覆盖。Unity项目架构/系统/生态审查按当前动作依赖及整体认可范围读[全项目基线与追踪](p0-architecture.md#project-tracking)，深查整个项目的生产模块、装配及依赖并建立可接续记录；后续据追踪复验变化影响与未闭。进度仍按自己的业务主责检查，不默认接管A的全项目技术审查。

<a id="task-additions"></a>
## 按任务追加

按当前动作／对象命中下表，**实际读正文再执行**；无关行不默认全读，缺工具／无异常不免必要查验。旧读／旧证仍有效可复用，目标／规则／对象／观察前提变动补原文；日常主线/依据机制保持；本职责P0按真实领域适用，不把Unity产品P0套通用任务。

| 当前触发 | 必须直达的正文与范围 |
| --- | --- |
| 制作派发／角色接续；用户明确多窗口分工 | [单一入口与后台制作](window-interaction.md)：对话统筹、真实作者与F/A接通，安全交接、唯一writer及独立工作连续推进 |
| Unity／目标项目的制作／审查／推荐／恢复（不指本包维护） | [项目理解](project-understanding.md#project-fit)：先同一活记录，缺必要关系限依赖，不等全画像才报有据P0 |
| 选批／排序／修链／承诺未兑现 | [优先队列](must-read-work-priority.md#core-loop-progress)：核上次消费者与当前观察；制作／查证继续与改法用[统一判据](must-read-work-priority.md#continue-or-change)，不以目标未闭续签失效方法 |
| UI整页／窗口／成套控件交付、布局／流程改变 | [03/11](constraints/03-ui.md#03-11)及其03/01、02、03、08：核任务用途／主次／总负担；不强加仅接口查询或非UI |
| 视觉／交互方案或设计改进；认可参照／跨宿主／改善声明 | [专项触发](review-standard.md#specialist-quality)的设计／对照正文；视觉提交必读[视觉验收](review-standard.md#visual-review)及续文，制作前核[依据](evidence-recovery.md#production-readiness) |
| 还原／复刻／参考、视角判断、单位状态 | [复刻档位](recognition.md#replication)、[视角](recognition.md#perspective)、[单位三问](recognition.md#unit-state)的实际命中段 |
| 实质任务当前内容（不待点名）；推进中新元素／命题、世界规则／意图／表现／预算变化及主动查缺 | [元素模型与三问](recognition.md#unit-state)和[原活理解](project-workspace.md#workspace)：共用当前修订／证据／未闭，适用职责各自独立核，现probe按实际模型事实呈现 |
| 一句可观察异常需查来源 | [症状→静态追查](recognition.md#symptom-trace)，再选实际机制，不只列疑点 |
| 供继续制作／可扩展基座；声明完整 | 分别读[交付类型](recognition.md#delivery-type)、[应有而缺失](recognition.md#absence)，不凭已做清单缩范围 |
| 易用／减负／复用／继续生产／委托纠偏；默认新增前置 | [11/07](constraints/11-methods.md#early-value-check)：按真实消费者，不强套Player |
| 实际调用jury_read／plan／prepare或消费其分页 | [reader合同](#reader-contract)：读取、分页／快照与声明边界；直接读文件不预载CLI参数 |
| 验证／复验／采用 | [相关性](verification-scope.md#relevance)及续文：可能影响必检，有据排除／旧证可复用 |
| 生成／隔离；恢复；退出／处置派生物 | 分别读[环境](evidence-lifecycle.md#environment)、[恢复](evidence-lifecycle.md#recovery)及同身份已知压缩/摘要冲突的[当前接回](coordination.md#activation)、[退役](evidence-lifecycle.md#retirement)，不全篇常驻；闲时缓存不挡主线 |
| 每条实质发言／送审／回传／转述／采用意见 | [两必发必答项](source-authority.md#grounded-consideration)与完整[消息](coordination.md#message-delivery)共同履行：后台实质回传保本人意见、角色/原分/原事件事实，前台保真呈现，两项不取代，工作端不代答；[保存](coordination.md#opinion-records)／[表达](message-style.md#user-facing)仍保真实送达 |
| 执行错误／复盘 | [工作流整改](review-correction.md#workflow-correction)：保原错与出处、修责任源，并在由前台用户呈现correction用户事件及处置 |
| 拟采用／发布／宣告完整交付，或实际停止受托推进 | 按真实动作读[完整核回](review-completion.md#completion-coverage)及[停止申请](review-completion.md#stop-request)与相应品质／权限；阶段答复本身不新增准停轮。命中[辩论](closeout-debate.md#workflow)才实际消费，prepare不自动识别 |
| 修改本Skill规则／配置／分发执行 | [维护](skill-improvement.md)、[授权](source-authority.md#rule-write)、[写前消费](source-authority.md#write-consumption)及续文；旧票不自造许可 |
| 阻断、高风险或高要求的必要取舍 | [知识检索](#knowledge-use)，只定向命中段及来源，不默认读知识全库 |
| 概念／根因／设计实现；方案／代码质量复核 | 分别[first-principles](first-principles.md)、[adversarial-review](adversarial-review.md)，两者匹配先生成后审；普通聊天／非代码小执行／纯格式不触发，方法不启Agent或扩权 |

本表是现有义务的角色／阶段／对象入口，不增记录表或逐工具打卡；具体裁定、许可与解除仍由原正文和职责承担。

<a id="reader-contract"></a>
## 实际读取与派发边界

只在实际调用读取/计划工具时消费本节。`jury_read --profile general|maintenance|unity --role 本人 --review-stage planning|review`直接读同源当前组合，沿nextArgs接回，不先生成并重抄整份plan。

外部原件用`--material-file <绝对路径>`，可配精确唯一`--material-anchor`或RFC6901 `--json-pointer`；不配则读完整原文件。页绑定原rawSHA/定位/页目标与reader版本，续页变化拒绝；外部注释不跟读、不授指令/状态权威，JSON数值/布尔业务值保留。typed probe继续拒绝多历史块歧义，不猜最新。该入口用于真实current，替代手切/Tail。`jury_read --section`默认返回所选正文与明确续读目标；`continuationRequired=true`须继续读对应正文。加`--follow`可直接展开明确必读续边并去重、整段分页，无需先生成plan；普通Markdown链接不自动展开。`--from-plan <绝对JSON>`仍消费所选读集并展开续文，多职责prepare用`--role`选本人；精确选段单次至多32个种子。

分页按`nextArgs`接续，保选择／角色、页目标和快照；默认24KiB只计正文，单段超目标按所需增大`--page-bytes`。这不是工具最终输出预算：封装、转义和多结果合并另计；必要长正文完整续页，不截取前若干项。显式`--emit-bytes B`必须配`--emit-page N`，缺页参数在读正文前报错，不能静默忽略预算；只给`--emit-page N`时仍默认6144B。可用两参数逐次取得最终JSON有界片段，后页加`--expect-emission <首输出SHA>`拒串源，按同一输出SHA／顺序重组后再消费内层`nextArgs`；普通调用保持旧格式。调用者不得再合并所有页制造大输出。`--expect-snapshot`拒变化后的旧续页；`--measure`只统计，页可达或已返回都不证明本人读懂、履责或评分合规。

plan/route同样支持--emit-page/--emit-bytes/--expect-emission，最终JSON预算与reader一致；旧不带预算调用保原输出。

Unity plan／prepare准备声明选择和派发材料，不执行角色或认证身份／权限／语义；目录外命题仍需调查。独立输入、裁定和消息各由其通用合同承担，不在工具节复制。


<a id="knowledge-use"></a>
## 阻断、高风险或高要求时必须检索知识

任一条件命中，工作AI与相关陪审必须在选择下一方案或给整改方向前定向检索：必要结果被现有方法/依赖卡住或反复返工；存在毁档、错写、错归属、生命周期穿透、公共合同传播或不可逆后果的具体风险；用户明确要求高品质、高保真、高精度或严格性能目标。已知扩大损失的风险先做授权内止损，检索不拖必要处置。

触发后先把问题落到实际对象、机制与缺失结果，从[知识入口](../knowledge/index.md#issues)选择命中分区，再定位正文锚点，只读相关选段及其来源范围；已知落点可直达。索引未命中先带关键词搜索knowledge正文，再读相关段，不顺序通读文件。首次使用、选中工作区不自动预读知识，高要求也只触发相关问题检索；知识正文不加入默认readSelectors，索引普通链接不自动展开全部分区或专题。命中后把结论、适用条件、反例及可借用手法映射到本对象，给下一动作与验证信号，可有据维持已有方法；只报标题或链接不算执行。原始材料调查继续，知识不代当前证据。

接续现有任务记录中的问题、对象/条件、已读selector/来源版本、采用/排除/无匹配及下一动作；仍适用就沿原落点继续，不重走总索引。必要新问题、相关要求/条件或知识内容变化、原依据失效/新反证时，只重查受影响段；索引增条、换批名和普通收件不触发重读。记录缺失/无法定位时补查相关入口，不假称已读。无匹配保真实查询并转具体项目/外部依据，不循环返回入口、不降要求或停无关工作。库不强制技术栈/案例参数，也不新增权限、逐条审批或固定来源数量。
