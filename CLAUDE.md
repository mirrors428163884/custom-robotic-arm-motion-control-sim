# CLAUDE.md — Project Skill & Command History

> 本文件作为项目级提示词 skill 文件，记录每次会话中执行过的终端命令历史总结，
> 标注危险命令与注意事项，防止后续误用危险命令行。
> 每次会话结束后应追加更新本文件的「命令历史总结」章节。

---

## 项目概述

- **项目路径**: 仓库根目录 (以 `$REPO_ROOT` 指代)
- **内容**: 机械臂 URDF 描述包（Kinova Gen3 Lite 6轴 + KUKA iiwa 14 R820 7轴）
- **conda 环境**: `mj311`（Python 3.11）
- **可视化主入口**: [`main_ui_app.py`](main_ui_app.py:1) — yourdfpy + pyrender(pyglet) URDF 可视化与交互式关节角控制；实现拆分在 `robot_viz/` 包。旧 [`visualize_urdf.py`](visualize_urdf.py:1) 现为薄兼容层 (`from main_ui_app import main`)。

## 环境信息

- **OS**: Linux 6.17, X11 (DISPLAY=:1)
- **Shell**: `/bin/bash`（注意：execute_command 默认用 `/bin/sh`，`source` 不可用，需用 `bash -c`）
- **GPU**: NVIDIA RTX 5080, 驱动 570.190, OpenGL 4.6
- **conda**: 安装于 `$CONDA_ROOT`（激活需 `source $CONDA_ROOT/etc/profile.d/conda.sh && conda activate mj311`）

## 已安装依赖（mj311）

| 包 | 版本 | 说明 |
|----|------|------|
| yourdfpy | 0.0.60 | URDF 解析与运动学 |
| pyrender | 0.1.45 | 3D 渲染（glfw 窗口） |
| pyglet | 1.5.31 | 窗口系统 |
| trimesh | 4.12.2 | mesh 处理 |
| glfw | 3.4.0 | 窗口系统 |
| PyOpenGL | 3.1.0 | OpenGL 绑定 |
| xacro | 2.1.1 | xacro→URDF 转换 |
| numpy | 2.4.6 | **需补 `np.infty=np.inf` 别名**兼容 pyrender |

---

## 命令历史总结

### 会话 1: URDF 可视化脚本开发 (2026-07-10)

#### 安全命令（可重复使用）

```bash
# 激活 conda 环境（必须用 bash -c，因为默认 shell 是 /bin/sh）
bash -c 'source $CONDA_ROOT/etc/profile.d/conda.sh && conda activate mj311 && <command>'

# 检查 Python 包版本
bash -c 'source $CONDA_ROOT/etc/profile.d/conda.sh && conda activate mj311 && python -c "import <pkg>; print(<pkg>.__version__)"'

# 安装依赖
bash -c 'source $CONDA_ROOT/etc/profile.d/conda.sh && conda activate mj311 && pip install <pkg>'

# 运行可视化脚本（前台，timeout 超时自动退出）
bash -c 'source $CONDA_ROOT/etc/profile.d/conda.sh && conda activate mj311 && timeout 10 python visualize_urdf.py --robot gen3_lite'

# 离屏渲染测试（无 GUI，用 EGL）
bash -c 'source $CONDA_ROOT/etc/profile.d/conda.sh && conda activate mj311 && export PYOPENGL_PLATFORM=egl && python -c "..."'

# 截图（PIL ImageGrab）
bash -c '... && python -c "from PIL import ImageGrab; im=ImageGrab.grab(); im.save(\"x.png\")"'

# 语法检查
bash -c '... && python -c "import ast; ast.parse(open(\"visualize_urdf.py\").read()); print(\"OK\")"'
```

#### ⚠️ 危险/需注意命令

| 命令 | 风险 | 说明 |
|------|------|------|
| `pkill -9 -f visualize_urdf.py` | ⚠️ 中 | 可能误杀同名进程；曾因 `pkill -f` 匹配到自身命令导致 SIGKILL |
| `pkill -f pyrender` | ⚠️ 中 | 同上，`-f` 会匹配命令行全文 |
| `rm -f iiwa_top.urdf.xacro` | ⚠️ 低 | 删除临时文件，确认路径正确 |
| `pip install pyglet` (无版本约束) | ⚠️ 高 |  |
| `pip install pyrender` | ⚠️ 中 |  |
| `xwd -root` | ⚠️ 低 | 在此 X11 环境报 `BadColor` 错误，无法使用 |
| `convert` (ImageMagick) | ⚠️ 低 | 未安装，不可用 |

---

### 会话 2: 窗口内 HUD + 悬浮关节输入面板 (2026-07-13)

#### 实现要点

- **窗口内 HUD/面板必须用 `self._renderer.render_text` (pyrender immediate-mode)**，
  不能用 `set_caption` (标题栏在 GNOME/Wayland 下被截断且不实时)。
- **pyglet.gui / pyglet.shapes / batch 绘制不可用**：pyrender 用 OpenGL 4.1/3.3
  **core profile**，pyglet 1.5 控件走 legacy 顶点数组 (`glPushClientAttrib`)，
  core profile 下报 `GLException: invalid operation`。→ 悬浮输入框只能用文字自绘
  (immediate-mode)，自接管 `on_text`/`on_mouse_press`/`on_mouse_drag`。
- **字体表仅 ASCII 0-127**：面板文字禁用中文/`▶`，选中标记用 `>`。
- **编辑缓冲首次键入清空预填**：`edit_fresh` 标志，否则 `0.0000`+`0.500`→`0.00000.500` 解析失败。

#### 安全命令（可重复使用）

```bash
# 语法/编译检查
bash -c 'source $CONDA_ROOT/etc/profile.d/conda.sh && conda activate mj311 && python -m py_compile visualize_urdf.py && echo OK'

# 无头驱动 GUI 事件做端到端测试 (注入 on_mouse_press/on_text/on_key_press)
# 通过 monkeypatch pyrender.Viewer._init_and_start_app + pyglet.clock.schedule_once(driver)

# 截图 pyrender framebuffer (可用!): self._renderer.read_color_buf() -> imageio.imwrite
bash -c '... python -c "import imageio; imageio.imwrite(\"/tmp/x.png\", self._renderer.read_color_buf())"'
```

#### ⚠️ 危险/需注意命令

| 命令 | 风险 | 说明 |
|------|------|------|
| `on_draw` 内调用 `self.close()` | ⚠️ 中 | 触发 pyglet `Set changed size during iteration`；应改用 `schedule_once` 或标志位延迟关闭 |
| `/private/tmp/...` (macOS 路径) | ⚠️ 低 | 本机是 Linux，临时文件用 `/tmp` |
| 重写 `on_mouse_press` 吞事件后仍调 `super().on_mouse_drag` | ⚠️ 中 | pyrender `trackball.down()` 只在 `on_mouse_press` 初始化 `_pdown`；press 被吞则 drag 调 trackball 崩溃 `AttributeError: _pdown`。需用手势归属标志 (`panel`/`view`) 控制是否委托 super |
| `pyglet.image.get_buffer_manager().get_color_buffer().save(...)` | ⚠️ 低 | 在 pyrender core-profile 上下文不稳定；改用 `self._renderer.read_color_buf()` |

#### 已知问题与规避

1. **HUD/面板不显示** → 用 `render_text` 画进视口，勿用 `set_caption`。
2. **pyglet 控件崩溃 (invalid operation)** → core profile 不兼容 legacy 管线，改文字自绘。
3. **编辑输入拼接错误** → `edit_fresh` 首键清空预填值。
4. **截图抓到旧帧** → 手动 `on_draw` 后立即 `read_color_buf`，中间勿夹事件分发。
5. **trackball `_pdown` AttributeError** → 面板吞掉 press 后，drag/release 需按手势归属决定是否调 super，未初始化 trackball 时勿委托。

---

### 会话 3: 右侧可展开设置面板 (2026-07-13)

新增右侧设置面板（坐标轴大小 / 预设视角+重置 / 每 joint 坐标系 / 每 link 可见度），
同样 immediate-mode 文字自绘。详细踩坑见 [PITFALLS.md](PITFALLS.md)。

#### 实现要点

- **link 可见度**：每 link = 一个 geom node（geom 名 `<link>.STL`），
  `node.mesh.is_visible = False` 即隐藏。
- **joint 坐标系**：`robot.scene.graph.get(child_link)[0]` 取 link 世界变换，
  在该 pose `scene.add(trimesh.creation.axis(...))`；关节角变化后在 `apply_joint` /
  `reset_joints` 末尾 `update_joint_frames()` 刷新 pose。
- **预设视角**：`self._trackball = Trackball(pose, viewport_size, scene.scale,
  centroid)` 同步重建（只设 camera.matrix 会被 trackball 缓存覆盖）；重置用
  `self._reset_view()`。
- **多面板命中顺序**：`on_mouse_press` 右侧面板 → 左侧面板 → super，手势标志
  扩展 `panel`/`view`/`rpanel`。

#### ⚠️ 危险/需注意命令

| 命令 | 风险 | 说明 |
|------|------|------|
| `trimesh.creation.axis(axis_length=0)` | ⚠️ 中 | 退化 mesh 污染 scene.bounds 为 NaN，切视角时 `quaternion_from_matrix` 崩 `LinAlgError`。轴长须钳到正最小值 (AXIS_MIN=0.01) |
| 只设 `_camera_node.matrix` 不重建 trackball | ⚠️ 低 | 用户一拖拽视角就跳回旧位；须同步重建 Trackball |

#### 已知问题与规避

1. **坐标轴滑条拖到 0 → 相机崩溃** → 轴长钳制到 AXIS_MIN；设相机 pose 前
   `np.all(np.isfinite(pose))` 兜底。
2. **预设视角拖拽跳回** → 重建 Trackball 同步 pose。
3. **自管世界轴与内置 show_world_axis 重叠** → `viewer_flags["show_world_axis"]=False`。
4. **截图截到旧帧（前/后缓冲交换）** → 提前改状态让事件循环自然渲染交换，稍后再截，
   不要"改完立即截"。
5. **无头测试取闭包变量取不全** → 闭包变量分散在各方法，需遍历多个方法合并
   `co_freevars` → `cell_contents`。

---

### 会话 4: 模块化拆分 (2026-07-13)

把 1050 行的单文件 `visualize_urdf.py` 拆成 `robot_viz/` 包 + `main_ui_app.py` 主入口。
架构：OOP (RobotSceneController 类) + dataclass 状态 (ViewerState)。行为零改动。

#### 模块结构

```
main_ui_app.py         主入口 (argparse -> 加载 -> 组装 controller+viewer -> 启动)
visualize_urdf.py      薄兼容层 (from main_ui_app import main)
robot_viz/
  __init__.py          np.infty 补丁 (须先于 import pyrender) + 导出
  urdf_loader.py       xacro_to_urdf / make_iiwa_top_level_xacro / load_robot
  scene_builder.py     build_pyrender_scene / compute_camera_pose / sync_poses
  joint_utils.py       get_joint_limit / format_joint_angles / print_joint_angles
  state.py             ViewerState dataclass (原 state dict)
  controller.py        RobotSceneController (原 main() 闭包函数 -> 方法)
  viewer.py            JointViewer(pyrender.Viewer), 持有 controller
  help_text.py         print_help
```

#### 已知问题与规避 (拆分陷阱)

1. **repo_root 路径**：loader 移入子包后 `__file__` 深一级，`os.path.dirname` 会指错，
   pkg_map 找不到 mesh/xacro。改用 `Path(__file__).resolve().parents[1]` 上跳到仓库根。
2. **JointViewer 类常量 RP_* 原引用外层 ui_scale 闭包**：拆出后 class-body 访问不到，
   必须挪进 `__init__` 按 `controller.ui_scale` 算成实例属性。
3. **np.infty 补丁**：放 `robot_viz/__init__.py` 顶部，确保先于任何 import pyrender。
4. **闭包 → OOP**：原 state dict + 15 个闭包函数全部搬进 controller/viewer，
   `state[...]`→`self.ctrl.state.xxx`，回调→`self.ctrl.xxx()`。所有 PITFALLS 修复原样保留。

---

## 更新规则

每次会话结束后，在「命令历史总结」下新增子章节，格式：

```markdown
### 会话 N: <简要描述> (YYYY-MM-DD)

#### 安全命令（可重复使用）
<命令列表>

#### ⚠️ 危险/需注意命令
| 命令 | 风险 | 说明 |
|------|------|------|

#### 已知问题与规避
<编号列表>
```
