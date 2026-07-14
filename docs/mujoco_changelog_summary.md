# MuJoCo 版本变更总览（Changelog 摘要）

> 来源: https://mujoco.readthedocs.io/en/latest/changelog.html
> 范围: 最新（未发布）→ 3.2.6
> 用途: 项目文档，快速查阅各版本关键变更、破坏性改动与新特性。
> 说明: **破坏性变更 (Breaking)** 指升级需改代码/模型的改动；⚠️ 标注需重点关注。

---

## 版本变更表

| 版本 | 日期 | 新特性 / 改进 | ⚠️ 破坏性变更 (Breaking) | 重要修复 |
|------|------|--------------|--------------------------|----------|
| **未发布 (Upcoming)** | — | PGS 求解器加入 Nesterov 动量（迭代次数约减半）；`mj_encode` 支持 MJB/TXT；`mj_setConst` 重算 sameframe 标志；新增 `body/simple` 属性；支持自附着 (self-attachment)；simulate 修复 `.mjz` 加载；新增 `mju_writeResource` | `mj_encode` 返回 `mjtSize`；`mjd_inverseFD` 用 CSR `mjData.M`；移除旧版 `mjData.qM`；`mju_round` 半数向远离零取整；`sleep_tolerance` 默认 1e-4→1e-3 | `body_margin` gap 排除；mesh 编译法线缩放 |
| **3.10.0** | 2026-06-22 | `mju_threadpool` 并行仿真；统一日志 API (`mjfLogHandler`/`mjLogMessage`/`mju_setLogHandler`)；`mjs_numWarnings`/`mjs_getWarning`；附着用 `compiler/conflict`；float32 下 primal 求解器改进；CG 求解器用 Hager-Zhang 更新；`mjs_makeFlex`；OBJ 线段生成 1D flex；Qhull Q9 粗凸包 | 移除 `mjthread.h`；island 矩阵移入 stack；`efc_diagApprox`→`efc_diagA`；移除 `mju_{error,warning}_{i,s}`；`mj_fullM` 签名变更 | sysid `allow_pickle` 漏洞；mjz 解码路径 bug；凸包法线非单位 bug |
| **3.9.0** | 2026-05-27 | `mjData.efc_Y` 白化雅可比；`diagexact` 约束空间惯量精确对角；PGS 随机访问固定种子；flex 可休眠；编译计时诊断 (`mjtCTimer`/`mjs_getTimer`)；新增 `mjtBool` 取代 `mjtByte` | ⚠️ 重设计 `margin`/`gap` 语义（margin=膨胀，gap=额外检测缓冲）；`mjfCollision` 填充 `mjPreContact`；`mjtnum.h`→`mjtype.h`；触觉传感器报告原始深度；MJX 移除 `nconmax`；新增 `mjassert.h` | — |
| **3.8.1** | 2026-05-11 | PGS 支持 island；PGS 伪随机迭代（约快 20%）；trilinear/quadratic flex 的 `elastic2d`；中点积分限于 `implicitfast`（含流体时禁用）；`mjs_getOriginSpec`/`mju_sym2dense` | (未来) `mj_fullM` 将变更 | multiccd 默认值 (mjcPhysics)。Python: `MjSpec.encode`、`MjVfs` 绑定（assets dict 弃用） |
| **3.8.0** | 2026-04-24 | Python 3.14 支持；多单元 trilinear/quadratic flex；逐单元应变等式约束；`mj_maxContact`；VFS 存在性检查函数 | ⚠️ `multiccd` 现默认开启 | 子 spec 资源路径相对子级解析 |
| **3.7.0** | 2026-04-14 | `dcmotor` 执行器；执行器向传动目标贡献阻尼/电枢；非线性多项式力曲线 (`mjNPOLY`)；自由体中点积分；connect/weld 加入向心/科氏项；`mjpEncoder` 接口 (`mj_encode` + 注册) | ⚠️ `mjs` 刚度/阻尼扩为数组；`.obj`/`.stl` 解码器内置；移除 `vertcollide`；`mjPLUGIN_LIB_INIT` 需名称参数；移除 `mjWARN_VGEOMFULL`；URDF 不再硬编码 strippath | 负 mesh 缩放处理 |
| **3.6.0** | 2026-03-10 | `mjs_getCompiler` 与 `compiler` 属性；trilinear/quadratic 的 `strain` 等式；flex-SDF 碰撞；内存边界 `nJten`/`nJmom` 缩减。MJX: MJX-Warp 批量渲染 | ⚠️ `ten_J` 恒为稀疏并移入 `mjModel` | `mjs_attach` 丢失无 `sidesite` 空间腱 |
| **3.5.0** | 2026-02-12 | **MuJoCo Warp 正式发布**；**系统辨识 (System ID) 工具箱** (Python)；执行器/传感器支持任意延迟（历史缓冲）；布料 `flexvert` 等式；flex 隐式积分；测距-相机附着（多射线）；测距输出增强 | ⚠️ 射线投射函数增可选 `normal[3]`；`mju_rayFlex`→`mj_rayFlex`；`cam_orthographic`→`cam_projection` (`mjtProjection`)；移除 `getdir`；`margin`/`gap` 组合改为求和（非取最大）；分配用 `mjtSize` (64 位) | 隐式积分器导数 (forcerange/actearly)；多线程 mesh 处理真正启用；无关节嵌套体 `gravcomp` |
| **3.4.0** | 2025-12-05 | **休眠 island**（初步）；quadratic flexcomp dof；解析期名称冲突报错；Windows 栈 16MB；`mj_fwdKinematics`/`mj_extractState`/`mj_copyState`；Python 腱路径查询；`MjsWrap` 字段。MJX: warp-lang 1.10.0，`pmap` 可用 | `mjx.Model.tex_data` 改为 numpy ndarray（ABI 非破坏：`mjtSize` 现为 `int64_t`） | box-box 距离 |
| **3.3.7** | 2025-10-13 | 关节装饰/腱超限重着色；`mju_getXMLDependencies` + `dependencies` 示例；要求 C++20；移除未用 `mjOption.apirate` | ⚠️ `meshdir`/`texturedir`→`compiler.meshdir`/`compiler.texturedir`；MJX 移除 `_full_compat`；`nconmax`/`njmax` 默认 `None` | fitaabb 偏移/坐标系变换 |
| **3.3.6** | 2025-09-15 | 约束 island 现为默认（已文档化）；contact 传感器 subtree1/subtree2 支持任意体；曲面壳；被动 flex 接触；mesh 材质默认。MJX: `ten_length` 公开、Warp `mjx.tendon` | ⚠️ `qacc_warmstart` 更新移到 `mj_step` 末尾（使 `mj_forward` 幂等，改变 RK4）；`mjDSBL_PASSIVE`→`mjDSBL_SPRING`/`mjDSBL_DAMPER`；移除 `mjMOUSE_SELECT`；islanding 改为 disable 标志 | MjData 序列化（含 islanding） |
| **3.3.5** | 2025-08-08 | `insidesite`/`contact`/`tactile` 传感器；移除 SdfLib 插件（SDF 原生化）；内置 mesh；`mj_makeM` 合并 CRB 与腱电枢项。Python: Linux wheel 改 `manylinux_2_28`。MJX: Warp 后端 (beta) | ⚠️ 移除 `mjVIS_FLEXBVH` | 附着子对象列表；仅碰撞对 mesh 的凸包 |
| **3.3.4** | 2025-07-08 | 视口初始相机 `visual/global/cameraid`；被动 viewer 仅状态同步 | ⚠️ `mjs_detachBody`/`mjs_detachDefault`→`mjs_delete`；`element.delete`→`spec.delete(element)`；命名 `mjs_setString`→`mjs_setName`；MJX Option 分公/私字段 | 含腱电枢的逆动力学；MJX `put_data` actuator_moment |
| **3.3.3** | 2025-06-10 | island 内存连续化重构；移除 shell 插件（并入 flexcomp）；`mj_makeM`/`mj_copyBack`；移除 fusestatic 限制。Simulate: 移除 `mjv_sceneState`。MJX: 腱电枢 | ⚠️ `light/directional`→`light/type` (`mjtLightType`)；新增 `mjtColorSpace` 及纹理 `colorspace`（sRGB PNG 渲染变化） | — |
| **3.3.2** | 2025-04-28 | MJX: 逆动力学；腱执行器力传感器；`make_data` 复制 mocap 字段 | — | — |
| **3.3.1** | 2025-04-09 | 腱电枢；`compiler/saveinertial`；composite `orientation`；腱执行器力限位与传感器。MJX: 腱执行器力限位。Python: 程序化建模 colab；无名 mjSpec bind | ⚠️ flex 内部接触默认 false；附着函数统一为 `mjs_attach` | `mj_jacDot` 缺项；附着父坐标系；阴影闪烁 (macOS) |
| **3.3.0** | 2025-02-26 | **特性升级**："trilinear" flexcomp dof（快速可变形体，24 dof）；原生 CCD 默认开启；自定义 viewer 图表；碰撞/变形 flex 网格分离；势能/动能传感器；阴影渲染改进。MJX: 球/柱缠绕空间腱；box-box 修复 | ⚠️ `mjs_setDeepCopy`；mesh 惯量推断移到 asset (`asset/mesh/inertia`)，体积失败即报错；移除 composite `grid`/`particle` | — |
| **3.2.7** | 2025-01-14 | Python: `rollout` 原生多线程；`mjpython` 命名空间修复 | (次要) 移除 `mjData.qLDiagSqrtInv`；PGS A 矩阵内存缩减 | box-sphere 深穿透；`mj_mulM2` |
| **3.2.6** | 2024-12-02 | 移除 composite rope/loop。MJX: 肌肉执行器。Python: 3.13 wheel；mjSpec `bind` 方法；rollout 接受 MjModel 序列 | — | MJX `get_data` 类型错误；`texrepeat` 浮点转换 |

---

## 主线趋势速览

- **变形体 (Flex/软体)**：3.3.0 引入 trilinear dof → 3.3.x/3.5.0 隐式积分与布料 → 3.6.0 flex-SDF 碰撞 → 3.8.x/3.9.0 多单元与逐单元应变约束。
- **模型编辑 (mjSpec)**：3.3.x 起持续演进（附着/删除 API 统一），3.3.3 移除 `mjv_sceneState`。
- **性能与休眠 (Island/Sleep)**：3.3.6 island 默认化 → 3.4.0 休眠 island → 3.8.1/3.9.0 PGS island 与 flex 休眠 → 未发布版 PGS Nesterov 动量。
- **MJX / Warp 后端**：3.3.5 beta → 3.5.0 正式发布 → 3.6.0 批量渲染。
- **⚠️ 升级高风险点**：3.3.6 (`qacc_warmstart` 时机改变 RK4)、3.5.0 (`margin`/`gap` 改为求和、64 位 `mjtSize`)、3.9.0 (margin/gap 语义再改)、3.3.7 (`meshdir`/`texturedir` 迁移)。跨这些版本升级务必核对模型 XML 与自定义 C API 调用。
