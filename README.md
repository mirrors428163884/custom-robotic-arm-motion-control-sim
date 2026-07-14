# Custom Robotic Arm Motion Control Sim

> Interactive URDF visualizer and joint-space controller for robotic arms —
> built on [yourdfpy](https://github.com/clemense/yourdfpy) +
> [pyrender](https://github.com/mmatl/pyrender) (pyglet window).
>
> 机械臂 URDF 可视化与关节空间交互控制器 —— 基于 yourdfpy + pyrender（pyglet 窗口）。

Load a robot from URDF/xacro, render its meshes, and interactively drive every
joint with an in-window control panel: type exact angles, drag sliders, toggle
per-link visibility, show per-joint coordinate frames, and switch camera presets.

从 URDF/xacro 加载机器人，渲染网格，并通过**窗口内控制面板**实时驱动每个关节：
键入精确角度、拖动滑条、切换连杆可见度、显示关节坐标系、切换预设视角。

---

## Table of Contents / 目录

- [Supported Robots / 支持的机器人](#supported-robots--支持的机器人)
- [Installation / 安装](#installation--安装)
- [Quick Start / 快速开始](#quick-start--快速开始)
- [Command-line Options / 命令行参数](#command-line-options--命令行参数)
- [Controls / 操作说明](#controls--操作说明)
- [Project Structure / 项目结构](#project-structure--项目结构)
- [Troubleshooting / 常见问题](#troubleshooting--常见问题)
- [License / 许可证](#license--许可证)

---

## Supported Robots / 支持的机器人

| Robot | Joints | Description |
|-------|--------|-------------|
| `gen3_lite` | 6 | Kinova Gen3 Lite (default / 默认) |
| `iiwa` | 7 | KUKA LBR iiwa 14 R820 |

---

## Installation / 安装

**Requirements / 环境要求**

- Python 3.11 (tested in a conda env named `mj311` / 在名为 `mj311` 的 conda 环境中测试)
- A working OpenGL + display environment (X11). Linux / X11 is the primary target.
  可用的 OpenGL 与显示环境（X11）。主要面向 Linux / X11。
- ~500 MB free disk for meshes and dependencies / 约 500 MB 磁盘空间（网格 + 依赖）

### System-level dependencies (Linux) / 系统级依赖（Linux）

pyrender needs a native OpenGL / GLFW runtime. On a fresh Debian/Ubuntu machine
install these **before** the Python packages:

pyrender 需要系统级的 OpenGL / GLFW 运行时。在全新的 Debian/Ubuntu 机器上，请**先**装好
这些系统包，再装 Python 依赖：

```bash
sudo apt-get update
sudo apt-get install -y \
  libgl1-mesa-glx libgl1-mesa-dri \
  libglfw3 libglew-dev \
  freeglut3-dev
```

> On a headless server (no monitor) you have two options: run under a virtual
> display (`sudo apt-get install -y xvfb`, then `xvfb-run -a python main_ui_app.py`),
> or use EGL offscreen rendering (`export PYOPENGL_PLATFORM=egl`) for screenshot-only
> workflows. Interactive control still needs a real X11 display.
>
> 无显示器的服务器上有两条路：用虚拟显示（装 `xvfb`，再 `xvfb-run -a python main_ui_app.py`），
> 或用 EGL 离屏渲染（`export PYOPENGL_PLATFORM=egl`）仅做截图。交互式控制仍需真实 X11 显示。

### Option A — conda (recommended / 推荐)

**English**

```bash
# 1. Create and activate an environment
conda create -n mj311 python=3.11 -y
conda activate mj311

# 2. Install Python dependencies
pip install -r requirements.txt
```

**中文**

```bash
# 1. 创建并激活环境
conda create -n mj311 python=3.11 -y
conda activate mj311

# 2. 安装 Python 依赖
pip install -r requirements.txt
```

### Option B — venv / pip

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### ⚠️ Critical dependency note / 关键依赖说明

`pyglet` **must be `< 2.0`**. pyrender 0.1.45 is incompatible with pyglet 2.x
and the window renders black. `requirements.txt` already pins this — do not
upgrade pyglet manually. Also note `pip install pyrender` may pull pyglet 2.x
as a side effect; re-run `pip install "pyglet<2.0"` if that happens.

`pyglet` **必须 `< 2.0`**。pyrender 0.1.45 与 pyglet 2.x 不兼容，会导致窗口黑屏。
`requirements.txt` 已锁定版本，请勿手动升级。注意 `pip install pyrender` 可能顺带把
pyglet 升到 2.x，若发生请重新执行 `pip install "pyglet<2.0"`。

> numpy 2.x removed `np.infty`; the package restores the alias at import time
> for pyrender 0.1.45 compatibility (see `robot_viz/__init__.py`).
> numpy 2.x 移除了 `np.infty`，本包在导入时补回别名以兼容 pyrender 0.1.45。

### Verify the installation / 验证安装

Confirm every dependency imports at the pinned version before launching a window:

启动窗口前，先确认所有依赖以锁定版本正确导入：

```bash
python - <<'PY'
import yourdfpy, pyrender, pyglet, trimesh, xacro, numpy, OpenGL
assert pyglet.version.startswith("1."), f"pyglet must be <2.0, got {pyglet.version}"
print("yourdfpy", yourdfpy.__version__)
print("pyrender", pyrender.__version__)
print("pyglet  ", pyglet.version)
print("trimesh ", trimesh.__version__)
print("numpy   ", numpy.__version__)
print("OK — all imports succeeded / 全部导入成功")
PY
```

A quick offscreen render (no window needed) sanity-checks the GL stack:

一次离屏渲染即可验证 GL 栈是否可用（无需窗口）：

```bash
PYOPENGL_PLATFORM=egl python -c "import robot_viz; print('robot_viz import OK')"
```

---

## Quick Start / 快速开始

```bash
conda activate mj311

# Default: gen3_lite / 默认可视化 gen3_lite
python main_ui_app.py

# Pick a robot / 指定机器人
python main_ui_app.py --robot gen3_lite
python main_ui_app.py --robot iiwa

# Show collision geometry instead of visual meshes / 显示碰撞体
python main_ui_app.py --robot gen3_lite --collision

# Larger UI on a 4K display (auto-detected, or force a factor)
# 4K 屏放大 UI（自动检测，也可手动指定倍数）
python main_ui_app.py --width 3840 --height 2160          # auto ~2x
python main_ui_app.py --ui-scale 2.0
```

> The legacy entry point `python visualize_urdf.py ...` still works — it is now a
> thin shim that calls `main_ui_app.main()`.
> 旧入口 `python visualize_urdf.py ...` 仍可用——它现在是调用 `main_ui_app.main()`
> 的薄兼容层。

### Typical workflow / 典型使用流程

1. **Launch** a robot: `python main_ui_app.py --robot iiwa`.
   启动机器人。
2. **Select a joint** with `1`–`9` or `[` / `]`; the active joint shows in the HUD.
   用 `1`–`9` 或 `[` / `]` 选择关节，当前关节显示在 HUD 上。
3. **Pose it** — nudge with `←` / `→` (fine) and `↑` / `↓` (coarse), or press `e`
   to type an exact angle, or drag the joint's row in the left panel like a slider.
   调姿——用方向键微调/粗调，按 `e` 键入精确角度，或在左侧面板拖拽关节行当滑条用。
4. **Inspect** — press `g` for the right panel to toggle per-joint frames, per-link
   visibility, and camera presets (`Front` / `Side` / `Top` / `Iso`).
   检查——按 `g` 打开右侧面板，切换关节坐标系、连杆可见度、预设视角。
5. **Read back** the full joint vector to the terminal with `c`; `r` resets to zero.
   按 `c` 把完整关节向量打印到终端；`r` 归零。

See [Controls / 操作说明](#controls--操作说明) below for the full key/mouse map.
完整按键与鼠标映射见下方[操作说明](#controls--操作说明)。

---

## Command-line Options / 命令行参数

| Flag | Default | Description / 说明 |
|------|---------|--------------------|
| `--robot {gen3_lite,iiwa}` | `gen3_lite` | Which robot to load / 加载哪个机器人 |
| `--collision` | off | Show collision geometry / 显示碰撞体而非视觉网格 |
| `--step FLOAT` | `0.05` | Joint step per keypress (rad) / 单步关节增量（弧度） |
| `--width INT` | `1920` | Window width in px / 窗口宽度（像素） |
| `--height INT` | `1080` | Window height in px / 窗口高度（像素） |
| `--ui-scale FLOAT` | `0` (auto) | UI font/panel scale; `0` auto-scales by height (4K ≈ 2×) / UI 缩放，`0` 按窗口高度自动（4K 约 2×） |

---

## Controls / 操作说明

### Keyboard / 键盘

| Key | Action / 功能 |
|-----|---------------|
| `1`–`9` | Select joint / 选择关节 |
| `←` / `→` | Decrease / increase current joint (one step) / 减小 / 增大当前关节角（单步） |
| `↑` / `↓` | Big step (5×) / 大步（5 倍） |
| `[` / `]` | Previous / next joint / 上一个 / 下一个关节 |
| `e` | Edit current joint (type a value) / 编辑当前关节（键入数值） |
| `g` | Toggle right settings panel / 展开·收起右侧设置面板 |
| `r` | Reset all joints to zero / 所有关节归零 |
| `c` | Print all joint angles to terminal / 打印关节角到终端 |
| `h` | Print help / 打印帮助 |
| `q` / `Esc` | Quit / 退出 |

### Left panel — joint input (in-window) / 左侧关节输入面板（窗口内）

| Action | Effect / 效果 |
|--------|---------------|
| Click a joint row / 点击关节行 | Enter edit mode / 进入编辑态 |
| Type digits, then `Enter` / 键入数字后回车 | Apply, clamped to joint limits / 应用并钳制到关节限位 |
| `Tab` (while editing) | Switch rad ⇄ deg / 切换弧度·角度 |
| `Esc` (while editing) | Cancel / 取消 |
| Drag a joint row / 拖拽关节行 | Slider-style continuous adjust / 像滑条一样连续调节 |

### Right panel — settings (`g` or click the `[<] SET` tab) / 右侧设置面板（`g` 或点击 `[<] SET` 竖条）

| Group | Action / 功能 |
|-------|---------------|
| `== SETTINGS ==` header | Click `[>] hide` to collapse / 点 `[>] hide` 收起 |
| **AXIS SIZE** | Drag the row to resize the world coordinate axes / 拖拽调世界坐标轴大小 |
| **VIEW** | Click `Front` / `Side` / `Top` / `Iso` presets, or `Reset view` / 切换预设视角，或重置 |
| **JOINT FRAMES** | Toggle a coordinate frame at each joint / 逐关节开关坐标系 |
| **LINKS** | Toggle visibility of each link mesh / 逐连杆开关可见度 |

### Mouse — camera (outside the panels) / 鼠标视角（面板区域之外）

| Action | Effect / 功能 |
|--------|---------------|
| Left drag / 左键拖拽 | Rotate / 旋转 |
| Middle drag / 中键拖拽 | Pan / 平移 |
| Right drag / 右键拖拽 | Zoom / 缩放 |
| Scroll / 滚轮 | Zoom / 缩放 |
| `Shift`+Left | Pan / 平移 |
| `Ctrl`+Left | Roll / 翻滚 |
| `Ctrl`+`Shift`+Left | Zoom / 缩放 |

> The in-window panels are drawn every frame via pyrender's `render_text`
> (immediate-mode), because pyrender uses an OpenGL **core profile** that is
> incompatible with pyglet's legacy widget/batch pipeline. Panel text is ASCII-only.
>
> 窗口内面板每帧用 pyrender 的 `render_text` 绘制（immediate-mode），因为 pyrender 使用
> OpenGL **core profile**，与 pyglet 的传统控件/batch 管线不兼容。面板文字仅限 ASCII。

---

## Project Structure / 项目结构

```
main_ui_app.py            Entry point: argparse -> load -> assemble -> run
                          主入口：解析参数 -> 加载 -> 组装 -> 启动
visualize_urdf.py         Backward-compat shim (from main_ui_app import main)
                          薄兼容层
requirements.txt          Python dependencies / Python 依赖
robot_viz/                Implementation package / 实现包
  __init__.py             np.infty patch + public exports
  urdf_loader.py          xacro -> URDF, yourdfpy loading
  scene_builder.py        trimesh scene -> pyrender scene, camera, pose sync
  joint_utils.py          joint limits, angle formatting/printing
  state.py                ViewerState dataclass
  controller.py           RobotSceneController (robot + scene + state + callbacks)
  viewer.py               JointViewer (pyrender.Viewer subclass, panels + input)
  help_text.py            terminal help
gen3_lite_description/    Kinova Gen3 Lite URDF/xacro + meshes (BSD-3-Clause)
iiwa_description/         KUKA iiwa URDF/xacro + meshes (Apache-2.0)
```

**Where to make changes / 改哪里**

- Rendering & interaction / 渲染与交互 → `robot_viz/viewer.py`
- Business logic (FK, axis frames, presets) / 业务逻辑 → `robot_viz/controller.py`
- New state fields / 新状态字段 → `robot_viz/state.py`

---

## Troubleshooting / 常见问题

| Symptom / 现象 | Fix / 解决 |
|----------------|-----------|
| Black window / 窗口黑屏 | pyglet is 2.x — run `pip install "pyglet<2.0"` / pyglet 是 2.x，执行降级 |
| `AttributeError: np.infty` | Old import order; ensure `robot_viz` is imported before pyrender / 确保先导入 `robot_viz` |
| Fonts too small on 4K / 4K 字太小 | Pass `--ui-scale 2` or a larger `--height` / 传 `--ui-scale 2` 或更大 `--height` |
| No window appears / 无窗口 | No display; ensure `$DISPLAY` is set (X11) / 无显示环境，确认已设置 `$DISPLAY` |
| `libGL.so` / GLFW not found / 找不到 GL 库 | Install system deps (see Installation) / 安装系统级依赖（见「安装」） |
| Running headless / 无显示器服务器 | Wrap with `xvfb-run -a python main_ui_app.py`, or `PYOPENGL_PLATFORM=egl` for offscreen / 用 `xvfb-run` 包裹，或 EGL 离屏 |

---

## License / 许可证

This repository is a mix of first-party code and vendored robot description
packages. Each retains its own license.

本仓库混合了自研代码与内置（vendored）的机器人描述包，各自保留其原始许可证。

| Path / 路径 | License / 许可证 |
|-------------|------------------|
| Repository root (this project's code) / 仓库根（本项目代码） | **MIT** — see [`LICENSE`](LICENSE) |
| `gen3_lite_description/` | **BSD-3-Clause** — see [`gen3_lite_description/LICENSE`](gen3_lite_description/LICENSE) |
| `iiwa_description/` | **Apache-2.0** |
| Camera xacro under `gen3_lite_description/urdf/camera/` | **Apache-2.0** (upstream © retained under a generic notice) / 上游版权以通用声明保留 |

MIT, BSD-3-Clause, and Apache-2.0 are all permissive and mutually compatible, so
the root project stays **MIT** while the vendored packages keep their upstream
licenses. Redistribution must retain the upstream copyright notices required by
BSD-3-Clause and Apache-2.0.

MIT、BSD-3-Clause、Apache-2.0 均为宽松许可且互相兼容，因此根项目保持 **MIT**，内置描述包
沿用其上游许可。再分发时必须保留 BSD-3-Clause 与 Apache-2.0 要求的上游版权声明。
</content>
