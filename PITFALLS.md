# PITFALLS — visualize_urdf.py 踩坑记录

> 本文档汇总在 `visualize_urdf.py`（yourdfpy + pyrender + pyglet URDF 可视化）
> 开发过程中踩过的坑与规避方案。环境：Ubuntu 24.04 / conda `mj311` / Python 3.11 /
> pyrender 0.1.45 / pyglet 1.5.31 / numpy 2.x / RTX 5080 / X11 (DISPLAY=:1)。

---

## 1. 渲染 / OpenGL

### 1.1 窗口内 HUD/面板不显示 —— `set_caption` 只改标题栏
- **现象**：以为把信息拼进字符串就能"显示在窗口里"，实际只调了 `set_caption`，
  文字进了 OS 标题栏。Ubuntu 24.04 GNOME/Wayland 下超长标题被大幅截断，且只在
  按键时刷新，根本不是实时状态栏。
- **规避**：窗口内叠加文字必须用 `self._renderer.render_text(...)` 每帧画进视口
  （immediate-mode），不要用 `set_caption`。

### 1.2 pyglet.gui / pyglet.shapes / batch 全部不可用 —— core profile 冲突 ⭐
- **现象**：想用 `pyglet.gui.TextEntry` / `Slider` / `shapes.Rectangle` 做控件，
  运行即崩：`pyglet.gl.lib.GLException: b'invalid operation'`（发生在
  `glPushClientAttrib(GL_CLIENT_VERTEX_ARRAY_BIT)`）。
- **根因**：pyrender 请求 **OpenGL 4.1 / 最低 3.3 core profile**
  （`TARGET_OPEN_GL_MAJOR=4`），而 pyglet 1.5 的控件/batch 绘制走 **legacy 客户端
  顶点数组**（`glPushClientAttrib`），core profile 下该调用非法。
- **规避**：所有窗口内 UI 只能用 `render_text` 文字自绘（immediate-mode），
  自己接管 `on_text` / `on_mouse_press` / `on_mouse_drag` 做交互。
  **升级 pyglet 到 2.x 也不行**（见 4.1，会导致 pyrender 黑屏）。

### 1.3 字体表仅 ASCII 0-127 —— 中文/符号 KeyError
- **现象**：HUD 里用 `▶` 或中文，`render_string` 遍历字符查 `_character_map`
  时 `KeyError`。
- **根因**：`pyrender/font.py` 的 `Font.__init__` 只 `for i in range(0, 128)`
  构建字形。
- **规避**：面板文字全部纯 ASCII，选中标记用 `>` 代替 `▶`。

### 1.4 render_text 不支持多行 `\n`
- **现象**：单次 `render_text("a\nb")` 崩溃（`\n` 不在字形表）。
- **规避**：多行需自己按 `line_h = font_pt * 1.6` 逐行递减 y 坐标分多次绘制。

### 1.5 FPS 恒为 0.0
- **现象**：初始化了 `_fps_value=0.0` 却没有任何地方累加/计算，显示恒为 0。
- **规避**：重写 `on_draw`，每帧 `_fps_frames += 1`，每 0.5s 算一次 FPS。

---

## 2. 事件 / 交互

### 2.1 trackball `_pdown` AttributeError —— 吞掉 press 后仍委托 drag ⭐
- **现象**：`AttributeError: 'Trackball' object has no attribute '_pdown'`，
  发生在拖拽时 `super().on_mouse_drag() -> trackball.drag()`。
- **根因**：pyrender 的 `trackball.down()`（初始化 `_pdown`）**只在
  `on_mouse_press` 里调用**。若重写的 `on_mouse_press` 命中自绘面板、吞掉事件
  不调 super，trackball 从未初始化；之后落到 `super().on_mouse_drag()` 就崩。
  触发场景：首次点击即在面板上、或松开后的残留 motion 事件。
- **规避**：用手势归属标志 `_gesture`（`"panel"` / `"view"` / `None`）：
  press 命中面板→`panel` 吞事件；press 在面板外→`view` 委托 super；
  **drag/release 只在 `_gesture=="view"` 时才委托 super**，否则安全忽略。

### 2.2 编辑输入首键拼接 bug
- **现象**：点关节行进入编辑，缓冲预填 `0.0000`，再键入 `0.500` 得到
  `0.00000.500`，`float()` 解析失败。
- **规避**：加 `edit_fresh` 标志，首次键入时清空预填值再累积；退格/拖拽也清 fresh。

### 2.3 `on_draw` 内调用 `self.close()` —— 迭代中改集合崩溃
- **现象**：`RuntimeError: Set changed size during iteration`（pyglet
  `app.windows` 弱引用集合在遍历中被改）。
- **规避**：不要在 `on_draw` 里 `close()`；用 `pyglet.clock.schedule_once`
  或标志位延迟关闭。

### 2.4 右侧面板需在左侧面板/trackball 之前测命中
- **现象**：多个自绘面板叠加时，若命中判定顺序错，点击右侧面板会穿透到左侧或转视角。
- **规避**：`on_mouse_press` 按 z 序从最上层往下测（右侧面板 → 左侧面板 → 交回
  super）；命中即吞事件 return。手势归属标志扩展为 `panel`/`view`/`rpanel`，
  drag/release 按归属分发，只有 `view` 才委托 super（延续 2.1 的修复）。

### 2.5 展开态面板无收缩入口 —— 收起 tab 只在收起态存在
- **现象**：展开右侧面板后点头部 `[>] hide` 无反应，只能用 `g` 键收起。
- **根因**：收起用的竖条 tab 在 `_rpanel_hit` 里被 `if not rpanel_open` 守着，
  只在收起态命中；而头部行的 action 是占位的 `(None,)`，点击不触发任何逻辑。
- **规避**：给展开态头部行一个真 action（如 `("panel","close")`），在
  `_apply_rpanel_action` 里处理为 `rpanel_open=False`。即"收起入口"和"展开入口"
  必须各自都有可点击目标。

### 2.6 UI 字号/尺寸硬编码 → 4K 屏字太小；render_text 不自动适配 DPI
- **现象**：4K(200 DPI) 屏上面板字号只有 1080p 的物理一半大。
- **根因**：pyrender `Renderer.dpscale` 仅对 macOS 硬编码为 2，Linux 恒为 1，
  `render_text(font_pt=N)` 就是 N 像素，不随屏幕 DPI 放大。
- **规避**：引入统一 `ui_scale`（`--ui-scale`，默认 0=按 `窗口高/1080` 自动），
  所有 font_pt / line_h / 面板宽度 / margin 乘以它。**命中矩形与绘制坐标必须用
  同一 ui_scale**，否则缩放后点击错位（如 `x_right` 和 `_rpanel_row_rect` 的 x1
  都要 `-int(12*ui_scale)`）。

---

## 3. 几何 / 场景

### 3.1 退化坐标轴 mesh → NaN 包围盒 → 相机崩溃 ⭐
- **现象**：坐标轴大小滑条拖到 0，`trimesh.creation.axis(axis_length=0)` 生成退化
  mesh，污染 `scene.bounds` 为 NaN；随后切换预设视角设相机矩阵时
  `quaternion_from_matrix` 里 `np.linalg.eigh` 报
  `LinAlgError: Eigenvalues did not converge`。
- **规避**：坐标轴长度钳制到正的最小值（如 `AXIS_MIN=0.01`）；设相机 pose 前
  用 `np.all(np.isfinite(pose))` 兜底。

### 3.2 切换预设视角需重建 Trackball
- **现象**：只设 `_camera_node.matrix` 后，用户一拖拽视角就跳回旧位。
- **根因**：pyrender 的 trackball 缓存了自己的 pose，与相机 node 不同步。
- **规避**：`self._trackball = Trackball(pose, viewport_size, scene.scale,
  centroid)` 同步重建；重置视角直接调已有的 `self._reset_view()`。

### 3.3 自管世界坐标轴要关掉 viewer 内置的 `show_world_axis`
- **现象**：想让世界轴可缩放，但 viewer 的 `show_world_axis=True` 会额外画一个
  固定大小的轴，两者重叠。
- **规避**：`viewer_flags["show_world_axis"]=False`，自己 add/remove 一个
  world-axis node 管理尺寸。

---

## 4. 测试 / 截图

### 4.1 截图：pyglet buffer 不稳定，用 pyrender readback
- **现象**：`pyglet.image.get_buffer_manager().get_color_buffer().save(...)`
  在 pyrender core-profile 上下文不稳定/报错。
- **规避**：用 `self._renderer.read_color_buf()` 拿 numpy 图像，再
  `imageio.imwrite(path, arr)`。

### 4.2 截图抓到旧帧 —— 前/后缓冲交换时序 ⭐
- **现象**：在 `schedule_once` 回调里改状态后立即 `on_draw()` + `read_color_buf()`，
  截到的仍是改状态之前的画面（如面板明明 open=True，截图却是收起态）。
- **根因**：`read_color_buf()` 读的是最近一次 **swap 到前缓冲** 的帧；手动
  `on_draw()` 只画到后缓冲，没交换。等待期间事件循环渲染并交换的是旧状态帧。
- **规避**：**提前**改状态（如 `schedule_once(early, 0.3)`），让事件循环自然渲染并
  交换出新状态帧，**稍后**再截（`schedule_once(shot, 1.6)`）。不要"改完立即截"。

### 4.3 无头端到端测试驱动 GUI 事件
- **方法**：monkeypatch `pyrender.Viewer._init_and_start_app`，在其中
  `pyglet.clock.schedule_once(driver, delay)` 注册驱动函数，用
  `self.dispatch_event("on_mouse_press"/"on_text"/"on_key_press", ...)`
  注入事件，最后 `self.close()`。可在真实 GL 窗口里验证交互逻辑。
- **取闭包状态**：闭包变量分散在不同方法里——某个 `main()` 内变量只出现在引用它的
  方法的 `__closure__` 中。需遍历多个方法（`on_key_press`/`on_mouse_press`/
  `_rpanel_rows`/`_apply_view` 等）合并 `co_freevars` → `cell_contents` 才能拿全
  `state`/`scene_pr`/`node_list` 等。

### 4.4 临时文件路径
- **现象**：误用 macOS 的 `/private/tmp`。本机是 Linux。
- **规避**：临时文件一律用 `/tmp`。

---

## 5. 环境 / 依赖

### 5.1 pyglet 必须 `<2.0` ⭐
- pyglet 2.x 会导致 pyrender 窗口黑屏。安装务必 `pip install "pyglet<2.0"`。
- `pip install pyrender` 会自动升级 pyglet 到 2.x，装完需手动降级。

### 5.2 numpy 2.x 需补 `np.infty`
- pyrender 0.1.45 用了 `np.infty`，numpy 2.0 已移除。脚本顶部补
  `if not hasattr(np, "infty"): np.infty = np.inf`。

### 5.3 conda 激活需 `bash -c` + source
- 默认 shell 是 `/bin/sh`，`source` 不可用。命令须包成
  `bash -c 'source $CONDA_ROOT/etc/profile.d/conda.sh && conda activate mj311 && <cmd>'`。

### 5.4 pkill -f 误杀
- `pkill -f visualize_urdf.py` 的 `-f` 匹配命令行全文，可能匹配到自身导致 SIGKILL。慎用。

### 5.5 注释里 "glfw" 实为 pyglet
- 源码/文档里多处写 "glfw 窗口" 是口误，`pyrender.Viewer` 实际继承
  `pyglet.window.Window`，全程用 pyglet，未碰 glfw。
  (会话 4 拆分时新模块已统一改为 "pyglet"。)

---

## 6. 模块化拆分 (单文件 -> 包)

### 6.1 子包 `__file__` 推 repo_root 会指错 ⭐
- **现象**：把 `xacro_to_urdf`/`make_iiwa_top_level_xacro` 从根目录单文件移入
  `robot_viz/` 子包后，`os.path.dirname(os.path.abspath(__file__))` 得到的是
  `<repo>/robot_viz` 而非 `<repo>`，pkg_map 指错目录 → mesh/xacro 全找不到。
- **规避**：用 `Path(__file__).resolve().parents[1]` 上跳一级到仓库根；
  并支持显式传 `repo_root` 参数覆盖。

### 6.2 类体常量引用闭包变量, 拆出后失效
- **现象**：`JointViewer` 的 `RP_W = int(300 * ui_scale)` 等类体常量原来能访问
  `main()` 闭包里的 `ui_scale`；拆成独立模块后闭包没了，class-body 无法再引用。
- **规避**：挪进 `__init__`，按 `controller.ui_scale` 算成**实例属性** (self.RP_W)。

### 6.3 np.infty 补丁必须先于 import pyrender
- **现象**：补丁分散在旧单文件顶部；拆包后若某子模块先 import pyrender 再打补丁，
  pyrender 0.1.45 用到 `np.infty` 时已 AttributeError。
- **规避**：补丁集中到包的 `__init__.py` 顶部，且在 `from .xxx import` 之前执行，
  保证任何子模块 import pyrender 前 np.infty 已就绪。
