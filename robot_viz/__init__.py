#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""robot_viz — 机械臂 URDF 可视化与交互式关节角控制 (模块化包)。

由原单文件 visualize_urdf.py 拆分而来。主入口见仓库根目录 main_ui_app.py。

模块划分:
    urdf_loader   xacro -> URDF 转换 + yourdfpy 加载
    scene_builder trimesh scene -> pyrender scene, 相机位姿, pose 同步
    joint_utils   关节 limit / 角度格式化与打印
    state         ViewerState dataclass (交互状态)
    controller    RobotSceneController (机器人+场景+状态+回调)
    viewer        JointViewer (pyrender.Viewer 子类, 面板绘制与交互)
    help_text     终端帮助打印
"""

import numpy as _np

# pyrender 0.1.45 使用 np.infty，但 numpy 2.0 已移除，补回别名。
# 必须在任何 import pyrender 之前执行 (见 PITFALLS.md 5.2)。
if not hasattr(_np, "infty"):
    _np.infty = _np.inf

from .urdf_loader import xacro_to_urdf, make_iiwa_top_level_xacro, load_robot
from .scene_builder import build_pyrender_scene, compute_camera_pose, sync_poses
from .joint_utils import get_joint_limit, format_joint_angles, print_joint_angles
from .kinematics_analysis import (
    matrix_to_rpy, classify_structure, extract_dh, print_dh_table,
)
from .state import ViewerState
from .controller import RobotSceneController
from .viewer import JointViewer
from .help_text import print_help

__all__ = [
    "xacro_to_urdf", "make_iiwa_top_level_xacro", "load_robot",
    "build_pyrender_scene", "compute_camera_pose", "sync_poses",
    "get_joint_limit", "format_joint_angles", "print_joint_angles",
    "matrix_to_rpy", "classify_structure", "extract_dh", "print_dh_table",
    "ViewerState", "RobotSceneController", "JointViewer", "print_help",
]
