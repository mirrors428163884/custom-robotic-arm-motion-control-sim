#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""关节 limit 读取与角度格式化/打印。"""

import numpy as np


def get_joint_limit(robot, joint_name):
    """从 yourdfpy robot 读取关节 limit (lower, upper)。"""
    try:
        for j in robot.robot.joints:
            if j.name == joint_name and j.limit is not None:
                return (j.limit.lower, j.limit.upper)
    except Exception:
        pass
    return (None, None)


def format_joint_angles(robot, selected=None):
    """格式化关节角字符串。"""
    names = robot.actuated_joint_names
    cfg = robot.cfg
    lines = []
    for i, name in enumerate(names):
        lim = get_joint_limit(robot, name)
        marker = "▶" if (selected is not None and i == selected) else " "
        lo = lim[0] if lim[0] is not None else -np.inf
        hi = lim[1] if lim[1] is not None else np.inf
        lines.append(
            "  %s [%d] %-16s %8.3f rad (%6.1f deg)  [%8.3f, %8.3f]"
            % (marker, i + 1, name, float(cfg[i]), np.degrees(float(cfg[i])),
               lo, hi)
        )
    return "\n".join(lines)


def print_joint_angles(robot, selected=None):
    """打印关节角到终端。"""
    print("\n" + "=" * 66)
    print("  关节角 (selected = %s)" % (
        robot.actuated_joint_names[selected] if selected is not None else "None"
    ))
    print("=" * 66)
    print(format_joint_angles(robot, selected))
    print("=" * 66)
