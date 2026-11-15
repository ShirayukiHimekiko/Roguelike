# Unity资源与成熟能力来源

<a id="capabilities"></a>
## 可用于当前能力调查的切入

2026-10-15实际读取下列官方/维护方正文；仅来源核对，未安装库、未跑示例或Unity项目。以下不是通用必装表、行业使用率统计或本项目适用认证；现有包、项目设计与实际目标版本决定采用。

| 痛点 | 已读来源支持的能力/机制 | 适用切入与未证范围 |
| --- | --- | --- |
| JSON读写被手写、类型/配置来回失真 | 微软[System.Text.Json概览](https://learn.microsoft.com/en-us/dotnet/standard/serialization/system-text-json/overview)提供现成JSON读写；[反射与源码生成](https://learn.microsoft.com/en-us/dotnet/standard/serialization/system-text-json/reflection-vs-source-generation)区分运行时取元数据与编译期生成 | 可比较真实类型/数据来回和依赖成本；微软.NET Native AOT说明不能直接当Unity IL2CPP兼容证明，需按项目实际API/编译环境核。成熟库内部反射不是无依据业务胶水。 |
| 项目确需C#热更新 | [HybridCLR介绍](https://www.hybridclr.cn/docs/intro)说明为IL2CPP增加解释执行能力，并支持动态程序集与相应Unity工作流 | 用来调查现成热更新接法及项目构建/加载链；本轮未核具体项目版本、平台、补充元数据或发布结果，不照抄页面版本列表和性能宣传。 |
| 动效反复手写、对象退出后仍被驱动 | [DOTween文档](https://dotween.demigiant.com/documentation.php)提供Tween/Sequence、时间更新与回收配置；SetLink连接对象寿命，但被加入Sequence的子Tween不受该设置作用 | 可追真正Tween/Sequence所有者、取消/销毁与引用；现成调用不自动证明手感、暂停或池复用正确。未安装/测量，不推广示例容量。 |
| 加载释放了却常驻、切换抖动 | [Addressables 2.7资源内存](https://docs.unity3d.com/Packages/com.unity.addressables@2.7/manual/memory-assets.html)说明加载/释放计数、Bundle依赖及释放不等于立即卸载；连续卸载再加载可能造成asset churn | 可区分仍被共用、Bundle未卸、漏释放与反复加载；仅适用于采用相应机制的项目，不要求迁移到Addressables，不把Destroy实例等同释放资产。 |
| 文件在盘但loader读不到或取错类型 | [Unity 6 Resources.Load](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Resources.Load.html)定义相对Resources的路径、正斜杠、无扩展名、大小写不敏感及泛型类型过滤 | 说明必须核具体API，而非统一套文件系统规则；不由此推定File I/O、Addressables或远端地址有相同语义，未核本项目打包/路径。 |
| Shader效果被重复手写或选型不明 | [Unity 6关键词与变体](https://docs.unity3d.com/6000.0/Documentation/Manual/SL-MultipleProgramVariants.html)区分关键词、动态分支/变体及Editor/脚本控制入口 | 可找现成材质/Shader能力和实际启用路径；本包据此建议核目标管线、材质/关键词和构建中需要的效果，不能由网页预览签项目兼容或观感。 |

执行方法沿[能力调查与采用](../../references/project-understanding.md#capability-fit)，来源仅提供切入；项目未匹配的事实不补写成已验证。
