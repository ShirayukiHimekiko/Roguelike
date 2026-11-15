# 用户呈现与当前源消费

<a id="user-facing"></a>
## 对话AI实际发送，工具只查声明与保真

作者/F/A交本人事实，不拟用户Emoji/阶段稿。前台以原目标/原件作采用判断，显示有意义职责、原整数及范围、原主事件、实质判断／变化、必要来源、否决／未闭／条件／损失／关闭职责和本人处置；不默认展示后台Agent分配名、会话／任务分配号或调度容器定位。原actor/id/task/wave/event/评分与历史在后台完整保，不能靠删记录实现不展示。两项本人依据和🔎考虑到/🧩请考虑同名实答沿[source-authority](source-authority.md#grounded-consideration)；两basis仍按原格式，不机械把actualUse改成🧩。

**给用户看的正文用普通开发者能直接读懂的中文。** 职责标识（🟦F 进度／功能、🔶A 架构／技术生态／可玩性、🟪T 目标／美术（视觉／风格任务启用，格式见 [T 本职](target-art-review.md#obligations-target)）、工作AI、主交流AI）、【📈 本波推进增益：原整数】、`主事件：`、🔎考虑到｜用户需求偏移、🔎考虑到｜真实的视觉理解、🔎考虑到 / 🧩请考虑、【🧭开始评估方案】等格式照旧。格式之外的说明：先说画面或结果现在怎样，再说和目标差多少，最后说下一步做什么；不使用本包内部术语（如“原接点”“闭权”“不冒”“承担层”），非用不可时先用一句白话解释。分数旁边必须有这三句白话，不能只给数字。

**阶段消息：标题开头，每个参与职责各一块。** 第一行写当前事件的标题，原样取 `scripts/jury_session.py` 的 `USER_EVENTS`，不自造（例如继续制作写【🔁 继续制作与复验】，改路线写【🧭 重新定案】，汇报进度写【📍 进度】）；涉及本次功能时接【基础功能】【细节／进阶功能】。然后本段实际参与的每个职责各一块：工作AI、本波出意见的 🟦F／🔶A／🟪T、主交流AI 本人，每块都有本人原分、`主事件：` 和两项 🔎考虑到。不能只放一位陪审的块，再用统筹的散文代替其余人。最小示例（两项依据各块都有，此处只写一次）：

```text
【🔁 继续制作与复验】
**工作AI／计划中 【📈 本波推进增益：原整数】**（第 3 波计划）
主事件：重新定案
**🟪T 目标／美术／未通过 【📈 本波推进增益：原整数】**（v2 主机位）
主事件：……
**🔶A 架构／技术生态／可玩性／阻断 【📈 本波推进增益：原整数】**（v2 俯视）
主事件：……
**主交流AI／继续 【📈 本波推进增益：原整数】**（本波取舍）
主事件：继续制作与复验
🔎考虑到｜用户需求偏移：……
🔎考虑到｜真实的视觉理解：……
```

在自然关键成果/实质决定消费各人简洁但完整的当前源，不逐工具造新块、不每步强跑四源长dump。只选择本段实际参与/需采用的来源，旧证同条件复用；root也给本人当前两项事实。worker/dialogue不进F/A quorum，F/A原标签和原分机制保。

### 本人当前意见与已知后到修订

在本人原记录根部jury-opinion JSON块（或本人JSON原件）给id、taskId/waveId、role/真实actor、state/scope/event/judgment、gain原整数及basis.userNeed/actualUse各自source/evidence/disposition/action；必要open/conditions/losses/limits/closureOwner/next原样保。缺分仍按原规则-1/真实补正，不重评；只给指针/标题不合实质回件，字段齐仍不证理解。

`jury_session.py select-opinion --source-file <绝对本人原件> --opinion-id <id> --expect-task <taskId> --expect-wave <waveId>`只选唯一根部原块，返回块原字节指纹/定位；引用、HTML、注释、外层代码不作当前。原文件追加历史不改变同一块。本人同波新意见，用jury-current给同一taskId/waveId/role/actor、currentOpinionId、supersedes实际旧ids，形成唯一当前头；多份无头/冲突/选已替代项拒当前，不按mtime/编号猜最新。`select-opinion --history`只读历史，不能供当前compose/许可；新块也不无据撤销旧已闭事实。

前台不替本人填判断，writer不代root采用。root当前块responses每项给to目标id、目标blockSha256和source/evidence/disposition/action；compose从实际所选root源取得，并核目标当时原字节。同id内容/限制实改不得迁移旧回应，须本人真重判；历史追加不自动失效。该源自己的disposition不冒root回应。

### 原任务、投影与公开正文

复用原JSON或唯一jury-state块（schemaVersion=1），不另建状态服务。taskId/waveId与participants接[真实任务包](juror-prompt.md#task-packet)；当前消费带预期身份，缺/错波拒当前，不从同文件、hash或同名planning-start推现状。旧/无结构原件可internal历史读，未解析/风险未知不冒完成。

`probe --record-file <原件>`默认internal；`--audience user --expect-task … --expect-wave … [--event <实际事件>]`核当前本人源/完整意见并给messageText。`compose`带相同record/身份及成对可重复的`--source-file/--opinion-id`汇合当前源，不写原件；直接record.opinions用户入口同样不许删原源限制。当前回复两端绑定核实，不能只保指针再改正文。

消费完整messageText，不只取passed/sources/receiptCheck元数据。用户投影在专属责任字段按真实角色显示职责，保原event及其顺序，不输出后台wave/意见容器定位或审查版本指纹；可核原件仍在facts和来源选择中。未参与本段意见的执行者可复用真实职责绑定responsibilityRoles（actor→既有role），不用补一份意见／投票；没有角色对应的原生身份拒用户投影，不按名字猜职责。实际宿主仍核身份，绑定不认证真人或权限。只把精确命中的当前意见容器／块指针呈为该职责原始意见；实际业务路径、版本、许可证、引用、实质details和legacy wave范围保，不对任意文本全局替换／删ID。实质正文若仍夹调度名，应由该来源给有意义说明，不由工具猜或抹内容。`check-user-view --record-file … --draft-file <实际拟发正文>`带同一后台身份/来源/事件，核必要正文可见保留；不认证需求解释、理解或实际送达，前台须公开，再由真实消费者核回。普通控制/同文不另造波。

### 当前事实与许可边界

progress保已做/在做/待做/阻断及具名next；features只给本次基础/进阶事实。propositions接会改变选择的命题、支持/推断/未知/反证、证据/条件、受影响动作与后继；adoptions给动作、承担、依赖命题及proposed/held/allowed。已声明未知/反证、其它current限制不能支持allowed，不强每项双来源或全盘怀疑用户授权。

considerations接具名提出源、kind=consideration|request、实际收件owner、请求/state/nextAction及必要limitedActions/appliesTo；非open须同名response四事实。按原kind呈🔎/🧩和实际答复，不以两basis齐冒已答；未答只限依赖。risks保原来源/状态/影响/动作/后继/解除信号/严重性与范围；recovery和review-step唯一沿[否决恢复](must-read-work-priority.md#route-leadership)，released不等无其它限制的restored。

elementModel仍只投影原活模型sourceRef/scope/declaration与已发生questions/reposition/openRisks，不建第二模型库。关联current未闭不渲accepted，parent/other不随局部许可消失；字段/标签不认证世界、心理、预算或实际动作。

事件须原记录支持。accepted仅前台显式请求、当前无声明矛盾且实际requiredRoles各有当前allow时渲“原记录声明允许收尾”；不认证身份、语义合取、品质、真实许可或授权。审查集合仅适用F/A，单责/合法不同子scope保，不按字符串相等代语义；真正准停沿[完整核回](review-completion.md#completion-coverage)。

--expect-sha256只拒快照漂移，不代task/wave。urgent未closed给声明预警候选，严重反证/控制实际送达不等探查。relay-message保所选整原文，check-roles只查原件存在/格式，均不认证身份/逐源语义/已发，也不代当前选取和正文消费。工具不启动角色、执行采用或写状态；host真实收发/采用责任不转给字段。
