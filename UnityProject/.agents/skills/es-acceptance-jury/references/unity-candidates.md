# Unity 对象导航与条件性调查

游戏与工程任务按[8+2工作区](game-workspaces.md#approach)判断并形成改法；本页是[统一候选机制](candidate-mechanism.md#selection)供执行义务、产品对象、工作块与定向调查复用的操作模板，U卡不是全部候选。与交付候选不同；选中不等于发现缺陷。先从已确定用户目标、阶段、真实变化和消费者选链，不按题目关键词遍历。每个命中给可达坏例、合法对照、实际对象／观察及复验信号；编号和准备计划不代调查。

<a id="routing"></a>
## 按实际变化直接进入正文

| 当前变化 | 直接读取 | 何时扩查 |
| --- | --- | --- |
| 规则、新旧来源、定义／资源映射 | [U4需求变化](#u4)、[05/03映射](constraints/05-business.md#content-mapping) | 真实一次提交／经济或身份问题再进05/02／U5 |
| 共享职责、公共类型或策略状态 | [U1职责](#u1)、[01/07接线](constraints/01-architecture.md#strong-wiring) | 按实际owner、静态依赖和批准扩展核，不因武器名全查 |
| 身份、重复、回调或池寿命 | [U5身份](#u5)、[06/05回调后身份](constraints/06-lifecycle.md#callback-identity) | 有取消／输入／部分取得才读06对应叶；无该机制不造它 |
| Scene／Prefab／SO、资源路径/加载释放或平台接入 | [U8装配](#u8)、[01/09执行域](constraints/01-architecture.md#execution-context) | 值／覆盖、绑定／格式、依赖／加载、平台／构建声明各按影响 |
| UI、动作、视听与玩法后果 | [U9真实过程](#u9)、[03UI](constraints/03-ui.md)或[专项表](review-standard.md#specialist-quality) | 当前对象才进入动态／3D／参照／剧情；静态资产不强求完整战斗 |
| 性能与资源成本 | [02/03—05预算段](constraints/02-performance.md#project-budget) | 实际涉及存档／线程／加载时读对应边界，按项目预算同效果观察 |

方案／静态资产先验其真实委托，已要求可玩不能事后降成原型。实际采用、源码、保存、构建、Player各保范围；有前提反证／累计未兑现／旧证据失效时进入下方相应定位，不每轮执行四类纠偏。旧领域号从[稳定索引](constraint-index.md)定位唯一正文，不另建分类或状态服务。

<a id="u1"></a>
## U1｜职责落点

共享控制器、通用数据／接口/helper新增具体内容类型或状态时，读字段写者／重置者、caller、实际事件／消费与asmdef，问其随通用合同还是某内容规则变化。无职责依据而修改一项内容仍迫使共享层改变则迁回真实owner；改名或藏helper不解决。

通用事实快照、生命身份、现有回调和批准共享装配器可以成立，一般引用不自动错误。保原迟到／重复／归还／反馈及合法路径，复验实际静态依赖和运行调用；具体合同读[01/07](constraints/01-architecture.md#strong-wiring)。

<a id="u4"></a>
## U4｜需求增量

用户新增／替换／删除／纠错时，从有效原话到原配置／入口、提交与反馈比较本次条件及旧合法行为。新来源不能自动变全局替换或额外抵扣玩法，测试清单不能反推规格。明确批准的删除／纠错可改变旧行为。

先恢复仍合法的原来源并保新增机制，再验新行为、旧入口和应拒绝条件；设计细节在范围内主动取舍，真正改变方向的歧义才澄清。不把[018历史案例](../knowledge/cases/responsibility-identity.md#case-source)中的空放例当所有游戏都有弹体销毁来源。

<a id="u5"></a>
## U5｜生产身份与测试前提

ID、owner、快照、去重、迟到回调或复用决定结果时，从声明到真实创建／赋值、取得／刷新／归还、事件提交和消费者查语义。类型／定义、运行对象、当前生命与一次业务操作不同；GUID定位资源，GetInstanceID不单独代表池对象新生命。

测试double的工厂、时钟、唯一性和事件顺序须据实际来源；真实方法加伪唯一typeName仍是假前提。按当前规则核同类不同实例、同对象新代、同次提交重发、旧A晚于B等实际相关顺序并保正常路径；按类型统计合法，无跨寿命风险的同步路径不加token，不强制四种ID。

原身份或策略owner承担修正，不用可变引用冒发送时快照；实际回调后保护读[06/05](constraints/06-lifecycle.md#callback-identity)，规则映射读[05/03](constraints/05-business.md#content-mapping)。

<a id="u8"></a>
## U8｜实际装配与执行域

当前Scene／Prefab／SO、脚本／包、公共空值／寿命合同、加载／格式或平台变化时，追真实实例／override、GUID/meta、保存字段、程序集域与实际消费者。公共合同查参数／返回／可空／身份／有效期／副作用与释放，签名不变也要接齐直接调用方和绑定；合法触发下解引用空值或无条件退出吞结果须修。普通参数且绑定／格式／依赖未变，只查新值采用和相关行为，旧有效平台证据复用；数值若改变真实负载／奖励语义则扩相应链。

文件名/路径按项目惯例与实际loader核根、键、大小写/分隔符/扩展名及打包依赖，比较当前需要的Editor/目标构建等环境；沿加载取得、共享持有、失败/切换释放和后继再用核生命周期。动态加载、反射／AOT、剥离或目标构建真实命中才查Packages／link.xml／IL2CPP及Player。Editor作者工具可用UnityEditor，runtime不能误带编辑器依赖；现有合法库和批准单Scene原型可保。修原装配保meta和旧数据，已写／保存／编译／构建／运行分记。

<a id="u9"></a>
## U9｜真实输入、反馈、过程与负载

任务要求实际可用／可玩、操作／视听或性能，或有相关原反例/完成声明时命中。先分析[可用源码、资产及截图](review-methods.md#available-evidence)，执行或观察条件未就绪不能跳过现有分析；动态问题待对应入口/绑定具备条件后补证。工程可Play、.NET夹具或单Clip播放不自动代表目标入口就绪。独立选正常入口、完整画面和风险过程，核输入被接收→权威提交→可见后果→下一操作及必要退出；发送输入、Accepted、按钮／动效／录制成功不代这些结果。

按当前目标观察尺寸／可读、焦点／命中、动画／镜头／声音和正常速度时序；技术净空或终态不代目标画面。批准风格化、滑步／跳切／叠层按真实取舍判断，方案、静态资产、无存档原型可限定验收。已有必要可玩要求不能靠作者不宣称通过一直不观察。

完整过程按同候选及可追踪同局状态，保存Continue可跨进程，不拼多版成功。反例与正常路径复验，按真实预算／负载和同效果，用能回答命题的计时／分配／内存测量并核采集影响。反例区分自然入口、受控生产API及隔离夹具，查延迟／临时监听／复用由谁安排；受控通过不证明自然触发或全域防御必要。顺序重复刷新须指明两次读取间实际writer或改状态调用；工具失败查采集链，不写游戏失败或降标。累计只有前置才读[选批纠偏](must-read-work-priority.md#core-loop-progress)，阻断、高风险或高要求沿[知识检索](reading-guide.md#knowledge-use)从库中找同机制线索并落实本次查证。

命中本次可玩/视觉对象时，按[实际视觉验收](review-standard.md#visual-review)在P0轮查看全部有效目标、选择代价/后果、威胁辨认、反馈恢复与观感细节；必要品质差距与必要漏查按超级P0同轮直显并阻断。每次本次提交整幅/状态先全目标完整亲看，源码因果/无关对象复用不豁免本图；纯转述/控制不新审，不扩全游戏运行。
<!-- jury-read-continue: references/review-standard.md#visual-review -->

<a id="u2"></a>
## U2｜跨领域不抵消

功能／寿命通过而另一必要项失败时，查同候选两角色原事实与真实owner；保有效保护，批准共享策略可合法。完整裁定转读[decision-order](review-standard.md#decision-order)，再按U1查职责；本段不是平行裁定正文。
<!-- jury-read-continue: references/review-standard.md#decision-order -->

<a id="u3"></a>
## U3｜陪审旧路线反证

新原话／生产赋值／绑定挑战陪审自己的建议时，追旧前提与新事实，明确维持／修订／撤回及下一验证，反证不成立可保原判断。完整方法转读[strategy-recheck](project-understanding.md#strategy-recheck)，不限制真实新事实反驳次数。
<!-- jury-read-continue: references/project-understanding.md#strategy-recheck -->

<a id="u6"></a>
## U6｜共同前提与承诺兑现

方案持续扩大错误依赖或累计仅有前置而承诺未兑现时，查必要结果、新增成本及上次消费者／观察，给停止方法、下一有限结果和兑现信号；单次合理前置不按轮数否决。完整选批／纠偏转读[core-loop-progress](must-read-work-priority.md#core-loop-progress)，不是高级宿主协议。
<!-- jury-read-continue: references/must-read-work-priority.md#core-loop-progress -->

<a id="u7"></a>
## U7｜旧证据适用

需求／owner／入口／依赖前提变化时，追受影响未改字段与旧观察条件，重开失效项；无关通用保护和条件仍真旧证据可复用。完整边界转读[decision-order](review-standard.md#decision-order)的证据适用正文，保历史不冒本版重测。
<!-- jury-read-continue: references/review-standard.md#decision-order -->
