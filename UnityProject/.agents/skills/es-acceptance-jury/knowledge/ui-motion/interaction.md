# 交互连续性与状态反馈

<a id="retarget-progress"></a>
## K1：途中反向保当前进度

同一对端点的抽屉/折叠过渡收到相反意图时，保当前可见位置或时间进度，再改方向/目标。可持有一条时间轴反向，也可从当前值重建；核调用当刻是否跳位、重复意图是否重启、最终是否到最新目标。W3C的current time与保时间改速率支持该机制；移用到自驱UI是本包推导。

剩余距离与时长要按产品节奏另核，不能把“必须按距离缩时”强加所有实现。首次初始化、明确从头重播的剧情可重置；位置连续不自动要求速度连续。WAAPI `reverse()`还涉及解除暂停、完成后的回卷和inactive timeline异常，不是任意seek无跳变保证。

来源：[W3C Web Animations 1](https://www.w3.org/TR/web-animations-1/)，current time、updating playback rate、reversing、Animation接口；2026-10-15快照。

<a id="spring-state"></a>
## K2：二阶跟随改目标保位置和速度

已认可惯性的选中光条/跟随指示器，普通改目标只改平衡点，沿当前x/v继续积分。Juckett临界阻尼的位移含`(v0+ωx0)t`，清v会改变下一帧轨迹；Unity `SmoothDamp(...,ref currentVelocity,...)`同样要求调用者保速度状态。每个独立动效持有自己的x/v，不能每帧局部置零。

新建、新池绑定或产品明确瞬移可同时重置x/v；直接跟手的音量控件另保即时输入。保动量可能短暂沿旧方向走，允许范围与限速由产品决定。SmoothDamp有近似、限速和防越界，不等同任意欠阻尼解析弹簧；数学迁移到UI不证明玩家偏好。

来源：[Ryan Juckett, Damped Springs](https://www.ryanjuckett.com/damped-springs/)；[Unity Mathf源码](https://github.com/Unity-Technologies/UnityCsReference/blob/master/Runtime/Export/Math/Mathf.cs)，SmoothDamp；2026-10-15原字节快照。

<a id="input-presence"></a>
## K3：淡出时分开交接输入和选中项

CanvasGroup的alpha、interactable、blocksRaycasts分别表达视觉、控件交互与图形射线关系。先定面板何时不再消费命令、遮罩何时释放下层，再驱动透明度。接受关闭后可立即锁旧命令，但模态淡出期间仍挡背景；宿主直接重复Close还需自身状态幂等。EventSystem的选中对象另行交接，结束时核打开者仍可用，否则选合法fallback。

低alpha模态遮罩继续挡点击、教程高亮从开始就穿透都可能正确；不按alpha自动统一关raycast。只修pointer不证明手柄submit正确；Button提交检查active/interactable，CanvasGroup也不替任意自定义命令检查业务状态。

来源：[Unity CanvasGroup](https://docs.unity3d.com/Packages/com.unity.ugui@2.0/manual/class-CanvasGroup.html)；维护方[Button](https://github.com/Unity-Technologies/uGUI/blob/main/com.unity.ugui/Runtime/UGUI/UI/Core/Button.cs)与[EventSystem](https://github.com/Unity-Technologies/uGUI/blob/main/com.unity.ugui/Runtime/UGUI/EventSystem/EventSystem.cs)源码。交接时点是按本项目合同作的工程选择。

<a id="authority-display"></a>
## K6：模型收事件，展示追目标

数值滚动时，增减先作用于权威模型，再让显示值追新目标；不能用尚在路上的slider.value继续算余额。只读HUD动画写Slider可用`SetValueWithoutNotify`，或等效隔离业务监听器，避免模型→动画→onValueChanged→业务写回。100依次收+20/+5/−10后权威值应为115，与当帧展示位置无关。

交互式音量的用户拖动仍是合法提交，不统一删通知。展示归并不授权吞业务事件，也不替服务器去重/回滚。Slider会clamp且可wholeNumbers，需核实际范围；其源码证明通知语义，模型归属由当前业务决定。

来源：[Unity uGUI Slider源码](https://github.com/Unity-Technologies/uGUI/blob/main/com.unity.ugui/Runtime/UGUI/UI/Core/Slider.cs)，value、Set、SetValueWithoutNotify；2026-10-15原字节快照。权威/展示拆分是本包工程推导。
