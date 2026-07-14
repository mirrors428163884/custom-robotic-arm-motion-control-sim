#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""机械臂 URDF 可视化与交互式关节角控制 —— 主入口。

- 使用 yourdfpy 加载 URDF（支持 xacro 预处理）
- 使用 pyrender + pyglet 创建三维可视化窗口
- 窗口内左侧关节输入面板 + 右侧设置面板 (坐标轴/视角/坐标系/可见度)

依赖 (conda 环境 mj311): 见 requirements.txt

用法:
    python main_ui_app.py                              # 默认 gen3_lite
    python main_ui_app.py --robot iiwa                 # iiwa 14 R820
    python main_ui_app.py --robot gen3_lite --collision  # 显示碰撞体
    python main_ui_app.py --ui-scale 2                 # 手动放大 UI (4K)

实现拆分为 robot_viz 包，本文件仅负责编排 (argparse -> 加载 -> 组装 -> 启动)。
"""

import argparse

# robot_viz/__init__.py 顶部已打 np.infty 兼容补丁 (须先于 import pyrender)
from robot_viz import (
    xacro_to_urdf, make_iiwa_top_level_xacro, load_robot,
    build_pyrender_scene, print_joint_angles, print_help,
    RobotSceneController, JointViewer,
)


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description="机械臂 URDF 可视化与交互式关节角控制"
    )
    parser.add_argument(
        "--robot", choices=["gen3_lite", "iiwa"], default="gen3_lite",
        help="选择机器人 (默认 gen3_lite)",
    )
    parser.add_argument(
        "--collision", action="store_true",
        help="显示碰撞体而非视觉 mesh",
    )
    parser.add_argument(
        "--step", type=float, default=0.05,
        help="关节角单步增量 (rad, 默认 0.05)",
    )
    parser.add_argument(
        "--width", type=int, default=1920,
        help="窗口宽度 (像素, 默认 1920)",
    )
    parser.add_argument(
        "--height", type=int, default=1080,
        help="窗口高度 (像素, 默认 1080)",
    )
    parser.add_argument(
        "--ui-scale", type=float, default=0.0, dest="ui_scale",
        help="UI 字体/面板缩放系数 (默认 0=按窗口高度自动, 4K 约 2x)",
    )
    return parser


def resolve_ui_scale(args):
    """0 表示自动按窗口高度估算 (以 1080p 为基准)。"""
    if args.ui_scale and args.ui_scale > 0:
        return float(args.ui_scale)
    return max(1.0, args.height / 1080.0)


def select_robot_source(robot):
    """返回 (xacro_path, mappings)。"""
    if robot == "gen3_lite":
        return (
            "gen3_lite_description/urdf/gen3_lite.urdf.xacro",
            {"name": "gen3_lite", "sim_gazebo": "false",
             "use_camera": "false", "gripper": ""},
        )
    return (make_iiwa_top_level_xacro(), {"use_vision": "false"})


def main():
    args = build_arg_parser().parse_args()

    ui_scale = resolve_ui_scale(args)
    print("      UI 缩放系数: %.2f (窗口高 %d)" % (ui_scale, args.height))

    # ---- 1/4 选择 xacro 并转 URDF ----
    xacro_path, mappings = select_robot_source(args.robot)
    print("[1/4] xacro -> URDF 转换: %s" % xacro_path)
    urdf_xml, pkg_map = xacro_to_urdf(xacro_path, mappings)
    print("      URDF 生成成功, 长度 %d 字节" % len(urdf_xml))

    # ---- 2/4 yourdfpy 加载 ----
    print("[2/4] yourdfpy 加载 URDF + mesh ...")
    robot = load_robot(urdf_xml, pkg_map)
    print("      关节数: %d" % robot.num_actuated_joints)
    print("      关节名: %s" % robot.actuated_joint_names)
    print("      链接数: %d" % len(robot.link_map))

    # ---- 3/4 构建 pyrender 场景 ----
    print("[3/4] 构建 pyrender 场景 (pyglet 窗口) ...")
    scene_pr, node_list = build_pyrender_scene(robot, collision=args.collision)
    print("      mesh 节点数: %d" % len(node_list))

    # ---- 组装 controller ----
    ctrl = RobotSceneController(robot, scene_pr, node_list, args, ui_scale)
    ctrl.rebuild_world_axis(ctrl.state.axis_scale)  # 初始化自管世界坐标轴

    # ---- 4/4 启动 Viewer ----
    print("[4/4] 启动 pyglet 可视化窗口 (%dx%d) ..." % (args.width, args.height))
    print_help(ctrl.n_joints)
    print_joint_angles(robot, 0)

    viewer_flags = {
        "use_perspective_cam": True,
        "rotate_center": True,
        "show_world_axis": False,   # 改用自管的可缩放世界坐标轴
    }
    render_flags = {
        "flip_wireframe": False,
        "show_wireframe": False,
    }

    JointViewer(
        ctrl,
        scene_pr,
        viewport_size=(args.width, args.height),
        render_flags=render_flags,
        viewer_flags=viewer_flags,
        run_in_thread=False,
    )

    print("\n窗口已关闭。最终关节角:")
    print_joint_angles(robot, ctrl.state.selected)


if __name__ == "__main__":
    main()
