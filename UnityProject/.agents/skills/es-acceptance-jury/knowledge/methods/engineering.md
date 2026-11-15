# 工具、架构与交付方法

<a id="issues"></a>
## 按问题定位

| 问题 | 选段 |
| --- | --- |
| G6：原图未变却烤出旧主题，或工具更新仍错hit | [任务与实际依赖](#build-inputs) |
| G7：停服导出正常，运行中导出漏已提交进度 | [SQLite一致快照](#sqlite-snapshot) |
| G8：跑分p99漂亮，固定到达负载仍成串迟缓 | [计划到达与尾延迟](#scheduled-latency) |

<!-- jury-read-continue: knowledge/index.md#scope -->

<a id="build-inputs"></a>
## 缓存键跟随任务与实际读集

确定性资产构建的复用依据可写成`H(有效选项,任务/工具身份,[(依赖路径,H(内容))])`。清单选出的descriptor及其继续选出的文件也是依赖；控制清单变化后须重发现读集。可廉价重扫当前依赖，或验证上次成功的读集后重建；未引用素材不必使目标失效。任务代码/工具版本本身也会改变输出，不只核原图。

Ninja命令行记录和depfile可承接调度/依赖日志，不会自动发现所有资源读取或工具二进制变化，仍须明确接线。随机、时间、环境及绕过已跟踪入口的I/O另核可缓存前提；这不是每个小游戏都必须上构建框架。

来源：[Mokhov等，Build Systems à la Carte作者源码](https://github.com/snowleopard/build/tree/main/papers/icfp)，Background动态依赖、verifying trace、Engineering/Self-tracking；[Ninja手册](https://ninja-build.org/manual.html)的The Ninja log / depfile；2026-10-15实读快照，不把2018工具比较当当前能力表。

<a id="sqlite-snapshot"></a>
## 在线导出SQLite逻辑快照

WAL是数据库持久状态的一部分，已提交页未必回到主文件；主库复制可打开、integrity_check通过，也可能漏进度。在线导出可用SQLite Backup API或VACUUM INTO，完成并关闭目标后再发布独立文件；错误不提前报成功。固定等待、复制两遍、逐个复制活跃db/wal/shm都不是一致快照协议。

干净关闭、checkpoint完成且无新写者时复制主库可以正常。增量备份遇其它连接提交可能重启，默认不承诺精确按钮时点；需锁定读快照则由合法连接/线程所有者设计。Python标准库有Connection.backup，连接with块不负责close；Windows替换前须关闭。运行时绑定、持续写入成本和断电持久性另核，不擅关源连接。

来源：[SQLite WAL §4](https://www.sqlite.org/wal.html)、[Online Backup §1/3.1](https://www.sqlite.org/backup.html)、[VACUUM INTO](https://www.sqlite.org/lang_vacuum.html)及[Python sqlite3](https://docs.python.org/3/library/sqlite3.html)；2026-10-15实读。

<a id="scheduled-latency"></a>
## 固定到达计划下的尾延迟

独立到达负载应保计划产生、实际发送和完成时刻，按业务合同核`完成-计划产生`，并另报`实际发送-计划`。同步客户端停等后才发下一条，只计发送后周转会隐藏本应早到的请求；迟发不能无证据全归服务端。保目标/实际吞吐、失败超时丢弃未完成与收尾，不只筛成功样本。

真正闭环业务、或计划与发送一致时，发送后计时有正常用途。HdrHistogram按预期间隔补样依赖有效模型；已有完整计划记录应直接算，不再二次补偿或造成功响应。wrk2是HTTP工具，可借方法，不能直接冒游戏协议接通。

来源：[Gil Tene / wrk2](https://github.com/giltene/wrk2)的latency measurement technique；[HdrHistogram](https://github.com/HdrHistogram/HdrHistogram)的Corrected vs. Raw value recording calls；2026-10-15实读原作者README快照。
