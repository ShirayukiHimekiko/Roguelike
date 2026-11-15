# 裁剪、数字、减少动态与闪烁

<a id="clip-boundaries"></a>
## P3：形状与允许越界的祖先分别核

RectMask2D做共面二维矩形裁剪；Mask按图形形状/模板材料裁子图形。矩形列表可用前者，alpha圆头像不能只换成矩形。跨Row但不能跨Viewport的Glow要处在正确裁剪祖先下：去掉无必要Row裁剪，或搬到Viewport内同步效果层；关maskable可能连需要的上层裁剪也一起放弃。

保圆形/非矩形裁剪及外窗边界，搬层还要保坐标、滚动、排序与输入。非共面转面效果、自定义材质/Shader须核实际裁剪支持，组件存在不证明画面正确。

来源：[固定uGUI7.0.0源码](https://github.com/Unity-Technologies/uGUI/tree/854155341e6ba568aa84eed807332bb2ae19e294)，RectMask2D/Mask/MaskableGraphic；[Mask手册](https://docs.unity3d.com/Packages/com.unity.ugui@2.0/manual/script-Mask.html)。层级选择为本包推导，未做Unity渲染验证。

<a id="numeric-advance"></a>
## P4：固定文本框不等于固定数字列

比例数字的glyph advance不同，右对齐只固定整体右端。稳定HUD列位可只对数字/标点run用TMP `<mspace=...>...</mspace>`，选择容纳实际资产的槽宽；或用已验证表格数字资产/逐位固定槽。一起固定格式、整数小数位、分隔符和auto-size；位数改变另扩外层。

OpenType `tnum`不保证TMP自动应用，不能假定存在同名TMP富文本标签或CSS接口；新闻标题仍可比例排版。原Inter字体同字符数`111.1`/`888.8`名义advance为3922/5658，说明锚点不足；hmtx不代TMP字偶、atlas及感知可读性实测。

来源：[TMP Monospacing](https://docs.unity3d.com/Packages/com.unity.textmeshpro@4.0/manual/RichTextMonospace.html)（4.0.0-pre.2）、[固定TMP解析实现](https://github.com/Unity-Technologies/uGUI/blob/854155341e6ba568aa84eed807332bb2ae19e294/com.unity.ugui/Runtime/TMP/TMP_Text.cs#L8277)、[OpenType tnum](https://learn.microsoft.com/en-us/typography/opentype/spec/features_pt#tag-tnum)。[Inter原字体](https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz,wght%5D.ttf)的2026-10-15快照SHA256为`29160a80ff49ddcab2c97711247e08b1fab27a484a329ce8b813d820dc559031`，数值取该原件默认轴hmtx；可变URL后续版本须重核。两个旧3.0地址404不证明旧版无功能，采用须核目标版本。

<a id="reduced-motion"></a>
## P5：减少运动仍交同一状态和反馈

减少动态可移除/替换装饰过渡，不能early return连数字、Ready、选中和获奖结果也不更新。先提交并显示最终状态，再按偏好加飞入/弹跳；减少时即时到位或用稳定标识替代。中途切设置要终止旧驱动并结清状态，防旧回调复写。Unity平台偏好接口需具体核，不虚构通用SystemInfo字段。

玩家主动拖动的动作逐帧预览可能正是核心功能，不能用全局开关删掉；保反馈也不要求保所有运动，颜色/透明变化另核注意力和闪烁。Web AAA与Xbox建议不是所有游戏自动采用的合同。

来源：[W3C Understanding2.3.3](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html)、[减少动态偏好](https://www.w3.org/TR/mediaqueries-5/#prefers-reduced-motion)、[Xbox XAG117](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/117)。游戏状态/过渡拆分为本包工程推导。

<a id="flash-analysis"></a>
## P6：完整往返、任意时间窗、红闪与同时面积

采用WCAG2.2 SC2.3.1作分析时，按任意1秒内完整flash（两次相反变化）核，而非整数秒桶或单数transition。一般flash看相对亮度差≥0.1且暗端<0.8；红flash另核饱和红。该条的频率≤3或同时面积不超.006steradians（任意10°视野25%）是其定义下的途径，不是“所有超过3Hz都失败”。Understanding的WCAG2.2红闪working definition为至少一个状态的线性RGB满足`R/(R+G+B)≥0.8`，且两状态CIE1976色度距离>0.2；不能只因普通亮度差小就放行。

XAG118另有近似3/s、近似全屏20%、旧红闪表达与持续/空间图样，应分开引用，不拼标准。先离线核合成后颜色、滚动窗和同时区域，再取对应实际捕获/工具证据；警告或可关选项不消除触发。参考341×256的10°窗口25%=21824像素，不是全屏25%或任意设备通用值；SDR小面积/低对比正常例不签整游戏、HDR或所有观看条件安全。

来源：[WCAG2.2 SC2.3.1及定义](https://www.w3.org/TR/WCAG22/#three-flashes-or-below-threshold)、[Understanding2.3.1](https://www.w3.org/WAI/WCAG22/Understanding/three-flashes-or-below-threshold.html)、[Xbox XAG118](https://learn.microsoft.com/en-us/gaming/accessibility/xbox-accessibility-guidelines/118)，2026-10-15快照。只做安全离线数据分析，不播放危险样本；具体合规范围由项目实际采用目标决定。
