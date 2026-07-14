#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交互状态容器 (原 main() 内的 state dict)。"""

from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List


@dataclass
class ViewerState:
    """可视化器交互状态。

    由原 visualize_urdf.py main() 内的 state dict 转为强类型 dataclass。
    """

    # ---- 关节选择/步进 ----
    selected: int = 0
    step: float = 0.05
    dirty: bool = True

    # ---- 左侧悬浮输入面板 (immediate-mode) ----
    editing: Optional[int] = None     # 正在编辑的关节 idx, None=未编辑
    edit_buf: str = ""                # 编辑缓冲字符串
    edit_fresh: bool = True           # True=缓冲为预填值, 首次键入将清空替换
    edit_unit: str = "rad"            # 编辑单位: "rad" | "deg"

    # ---- 鼠标手势 ----
    press: Optional[dict] = None      # 鼠标按下命中的面板行 {idx, moved}
    gesture: Optional[str] = None     # "panel" | "view" | "rpanel" | None

    # ---- 右侧设置面板 ----
    rpanel_open: bool = False         # 右侧面板是否展开
    axis_scale: float = 0.15          # 世界轴长 (m), 由 controller 按 scene.scale 初始化
    joint_frames: List[bool] = field(default_factory=list)  # 每 joint 坐标系开关
    link_visible: Dict[str, bool] = field(default_factory=dict)  # geom_name -> 可见
    rpanel_press: Optional[dict] = None  # 右侧面板拖拽状态 {kind, x0, v0}
