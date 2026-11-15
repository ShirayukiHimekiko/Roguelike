# 动效的时钟、生命周期与重建

<a id="sequence-clock"></a>
## K4：检查实际推进的时钟所有者

暂停时仍需完成的UI，要让实际推进它的整条链用允许继续的时钟。DOTween子Tween进入Sequence后，其`SetUpdate`不决定整组时钟；应核外层Sequence，例如`SetUpdate(UpdateType.Normal,true)`。自写Update可明确传`Time.unscaledDeltaTime`。Fixed加independent也不能绕过timeScale=0时没有FixedUpdate。

世界冷却/回合计时可合法随游戏暂停，不能因画在UI就全改unscaled或改全局默认。unscaled不保证失焦仍有帧，也不是服务器时间；恢复大帧/跳跃应按产品策略核，不能假设它仍受scaled最大步长限制。

来源：[Unity Time.unscaledDeltaTime](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/Time-unscaledDeltaTime.html)；[DOTween官方文档](https://dotween.demigiant.com/documentation.php)，SetUpdate/Sequence作用域；2026-10-15快照。

<a id="completion-ownership"></a>
## K5：取消不自动等于完成本次绑定

DOTween `Kill(true)`先完成再kill，可触发OnComplete；撤销旧显示若沿用自然完成的关闭/归池副作用，可能伤到新绑定。由真实外层所有者先终止旧展示、清理旧句柄，再发布新绑定；跨绑定存活的回调捕获并核本次身份。主线程同步取消顺序已排除旧回调时，不强制另加代数架构。

正常播放完成仍可归还本次对象；明确“跳过即完成”的产品也可有意complete。子Tween进Sequence后`SetLink`无效，须核根与禁用/销毁路径；recycling还可能让旧引用指向后来复用的Tween，OnKill清句柄要避免抹新句柄。不能只凭IsActive认定仍属此绑定。

来源：[DOTween官方文档](https://dotween.demigiant.com/documentation.php)，Kill/OnComplete/OnKill、SetLink、SetRecyclable。取消和业务提交的分工是本包按来源语义作的工程推导，未运行目标DOTween/Unity。

<a id="layout-dirty"></a>
## P1：固定布局占位，运动放视觉节点

图标脉冲挤动兄弟时，追真正写入的RectTransform及布局祖先；可保固定占位，把scale/位移放内部视觉节点，一次性效果结束就停驱动。Unity说明Animator即使值未变也可能每帧使UI变脏；固定源码`OnDidApplyAnimationProperties→SetAllDirty`涉及布局、顶点和材质，LayoutRebuilder还会沿有效布局祖先找根。

普通`Graphic.color` setter有等值判断，不能把所有Update赋值都说成每帧全脏；scale/alpha也不是零重建。需要本地化伸缩的LayoutGroup、持续变化的Animator可保，具体帧耗要测目标版本和负载。

来源：[Unity UI optimization tips](https://unity.com/how-to/unity-ui-optimization-tips)，Animators/Layout；[固定uGUI源码](https://github.com/Unity-Technologies/uGUI/tree/854155341e6ba568aa84eed807332bb2ae19e294)，Graphic与LayoutRebuilder，源包7.0.0。布局/视觉拆分为本包实现选择。

<a id="canvas-cohorts"></a>
## P2：Canvas按共同变化分组

子Canvas隔离自己的几何/批次分析范围，但不同Canvas不能合批。先按更新频率和共同变化分组：倒计时/进度可同组，与大量静态框架分离；动态组确有不同变化模式再细分。比较同负载BuildBatch/UI rebuild、实际批次与GPU相关成本，节点数模型不等于实机收益。

12个共同淡入淡出的图形不因数量就逐个拆Canvas；静态组遇本地化/分辨率也可更新。父布局引起子Canvas尺寸变化时，不假设隔离消除所有传播。没有预算与抓帧，最优Canvas数量仍未知。

来源：[Unity完整UI优化教程](https://learn.unity.com/tutorial/optimizing-unity-ui)与[当前tips](https://unity.com/how-to/unity-ui-optimization-tips)，Canvas/Sub-canvas/Splitting；只取机制，不继承旧Unity5.x性能百分比。
