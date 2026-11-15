# 操作、音画与资源处理

<a id="issues"></a>
## 按问题定位

| 问题 | 选段 |
| --- | --- |
| G3：摇杆直接满推正常，绕圈后部分方向欠速 | [可信输入区间](#stick-range) |
| G4：换帧率或长帧改变已确认的跟随手感 | [保参考的时间阻尼](#time-damping) |
| G5：叶片缩小变稀，普通透明素材却不应加浓 | [alpha覆盖mip](#alpha-coverage) |

<!-- jury-read-continue: knowledge/index.md#scope -->

<a id="stick-range"></a>
## 从设备可信区间到连续幅值

摇杆原始长度m、可信内界L、满推界F时，`m<=L`归零，否则输出`v*min(1,(m-L)/(F-L))/m`，保方向和慢走。只修中心的`(m-L)/(1-L)`仍会欠速；离中心即normalize则丢中间速度。直接左推正常不能排除绕圈后外圈内缩，应看完整动作轨迹并用已支持设备确定F。

硬件归一与游戏响应曲线分开；已处理输入不重复套。独立双轴、键盘和批准的轴吸附有不同语义，不能为修移动一并替换。例子阈值不是所有手柄的校准值。

来源：[Ryan Juckett / Hypersect, Interpreting Analog Sticks](https://blog.hypersect.com/interpreting-analog-sticks/)，2016，Outer Radial Dead Zone / Radial Dead Zone Interpolation；2026-10-15实读。

<a id="time-damping"></a>
## 从已确认响应反求时间阻尼

递归跟随在f₀ Hz下每步系数a₀，若要保原手感，变步长用`a(dt)=1-(1-a₀)^(f₀*dt)`；等价`1-exp(-λdt)`，`λ=-f₀*ln(1-a₀)`。只乘dt是近似，长帧可能被Lerp截到目标。该组合等价针对恒定目标或已声明的逐段常值采样，不保证任意移动轨迹完全一致。

固定tick且渲染有快照插值可以正常；改tick率才需换算参数。按保存起点、固定时长推进的线性淡入仍用elapsed/duration，不能全改成递归追逐。暂停时钟、切镜直接落位由现有设计决定。

来源：[Rory Driscoll, Frame Rate Independent Damping using Lerp](https://www.rorydriscoll.com/2016/03/07/frame-rate-independent-damping-using-lerp/)，2016，The Great Lerping Problem—Exponential Decay；2026-10-15实读正文与公式。

<a id="alpha-coverage"></a>
## 裁剪素材的覆盖率mip

平均alpha不保过阈值面积。保mip0及材质实际阈值/比较规则，逐层求缩放，使该层过滤后的覆盖率接近基准；离散小mip未必能完全相等。测量须匹配采样：Castaño链接的NVTT固定实现先缩放并截断角点，再作双线性子采样，不能用未饱和值或单纯texel计数冒最终面积。

可用有界单调搜索并保最佳误差；原实现用scale范围[0,4]、10步，是可查的工程选择，不保证其它输入范围都够。每层重测，保1×1只能0/1等限制。连续软透明雾片不应强套二值覆盖目标；压缩、三线性和真实画面另验。

来源：[Ignacio Castaño, Computing Alpha Mipmaps](https://www.ludicon.com/castano/blog/articles/computing-alpha-mipmaps/)及其链接的[NVTT FloatImage.cpp固定提交](https://raw.githubusercontent.com/castano/nvidia-texture-tools/adce1a00da096570f0c396fc038809979ec281d5/src/nvimage/FloatImage.cpp)，L1379–1489启用分支；2026-10-15实读。当前作者迁移页不冒原2010页面同字节。
