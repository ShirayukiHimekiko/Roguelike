# EntitasDemo 残留清理方案

## 目标和范围

清理工作区已删除的 `EntitasDemo` 业务代码还在使用的入口、场景节点和生成配置。保留 Entitas 1.14.1 官方插件、Jenny 解析工程的通用部分以及 Project B 正式接入设计。正式 Context 和生成路径由后续业务实现确定。

## 执行步骤

| 进度 | 修改目标 | 原因和处理方式 |
| --- | --- | --- |
| [ ] | `Assets/Editor/EntitasDemoTest.cs` 和同名 `.meta` | 删除单独的 Demo 测试入口及元数据。它仍依赖已删除的 `Contexts.sharedInstance`、`DemoMoveSystem` 和 Demo 组件扩展。 |
| [ ] | `Assets/Scenes/main.unity` | 移除独立的 `EntitasDemoBehaviour` 根节点。该节点没有子对象，只有 Transform 和一个指向已删除脚本 GUID `6d167e5c0cb3d884dab7dc879ef03c1d` 的 MonoBehaviour。同步去掉对应的 `SceneRoots` 条目，保留其余场景节点。 |
| [ ] | `UnityProject/Jenny.properties`、仓库根的 `Tools/Entitas/EntitasGen/` | 删除 Unity 项目根的 Demo 生成配置，保留工具目录里的通用模板。移除模板内 Demo 的目标目录和 `Game` Context，删除工具工程的 `GameAttribute.cs` 及其编译项、Demo 组件 glob。更新工具说明，由正式业务填写 Context、显式源码输入和独占生成目录后再生成。 |
| [ ] | Project B 架构文档及执行手册中的相关段落 | 更新把 Demo 入口当作现状的说明，修正指向已移除脚本或配置的链接。保留正式业务方案及其接入目标。 |

场景修改只涉及如下文件 ID。

```text
main.unity
  删除 GameObject 2006534194
  删除 MonoBehaviour 2006534195
  删除 Transform 2006534196
  SceneRoots 移除 2006534196

Jenny
  移除 Demo 生成入口及其专用输入
  保留解析工程引用和通用生成器模板
  正式接入时配置 Context、输入源码和独占输出目录
```

## 验收标准

- 项目代码和场景没有指向已删除 Demo 类型或脚本 GUID 的引用。
- 生成工具没有指向 Demo 组件目录或 Demo 生成目录的配置，仓库仍提供正式接入可复用的 Jenny 模板。
- 相关设计文档链接指向现存配置模板或清理记录。
- Unity 编译、运行和 Jenny 生成按用户后续指定的范围执行。
