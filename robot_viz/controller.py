#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RobotSceneController — 机器人 + pyrender 场景 + 交互状态 + 全部业务回调。

由原 visualize_urdf.py main() 内的闭包函数集中而来。JointViewer 持有本类实例，
所有对 robot/scene/state 的读写都经由 controller，避免闭包耦合。
"""

import numpy as np

from .joint_utils import get_joint_limit
from .scene_builder import sync_poses
from .state import ViewerState


class RobotSceneController:
    """封装机器人模型、pyrender 场景与交互状态，暴露业务方法给 viewer。"""

    AXIS_MIN = 0.01   # 坐标轴最小长度 (m)，避免退化 mesh 产生 NaN 包围盒

    def __init__(self, robot, scene_pr, node_list, args, ui_scale):
        self.robot = robot
        self.scene_pr = scene_pr
        self.node_list = node_list
        self.args = args
        self.ui_scale = float(ui_scale)
        self.collision = bool(getattr(args, "collision", False))
        self.robot_name = getattr(args, "robot", "robot")

        self.n_joints = robot.num_actuated_joints

        # ---- 交互状态 (dataclass) ----
        self.state = ViewerState(
            selected=0,
            step=float(getattr(args, "step", 0.05)),
            axis_scale=float(max(robot.scene.scale, 1e-3)) * 0.15,
            joint_frames=[False] * self.n_joints,
            link_visible={nk: True for nk, _ in node_list},
        )

        # ---- joint idx -> 子 link 名 (放置 joint 坐标系) ----
        self._joint_child = {}
        for j in robot.robot.joints:
            if j.name in robot.actuated_joint_names:
                idx = robot.actuated_joint_names.index(j.name)
                self._joint_child[idx] = j.child

        # ---- 坐标轴 node 管理 ----
        self.axis_state = {"world_node": None, "joint_nodes": {}}  # idx -> node

        # ---- geom_name -> pyrender node (切换 link 可见度) ----
        self.link_node_map = dict(node_list)

        # ---- 左侧面板布局常量 (随 ui_scale 缩放) ----
        self.PANEL = {
            "x": int(20 * ui_scale),
            "top_margin": int(20 * ui_scale),
            "font_pt": int(round(18 * ui_scale)),
            "line_h": int(round(18 * 1.6 * ui_scale)),
            "header_lines": 2,     # 顶部 FPS 行 + 空行
            "row_w": int(560 * ui_scale),          # 单行命中宽度 (像素)
        }

    # -----------------------------------------------------------------
    # 关节应用 / 归零
    # -----------------------------------------------------------------
    def apply_joint(self, idx, value):
        """应用关节角并钳制到限位，然后同步 pyrender pose。"""
        name = self.robot.actuated_joint_names[idx]
        lo, hi = get_joint_limit(self.robot, name)
        if lo is not None and hi is not None:
            value = float(np.clip(value, lo, hi))
        cfg = self.robot.cfg.copy()
        cfg[idx] = value
        self.robot.update_cfg(cfg)
        sync_poses(self.robot, self.scene_pr, self.node_list,
                   collision=self.collision)
        self.update_joint_frames()

    def reset_joints(self):
        self.robot.update_cfg(np.zeros(self.n_joints))
        sync_poses(self.robot, self.scene_pr, self.node_list,
                   collision=self.collision)
        self.update_joint_frames()

    # -----------------------------------------------------------------
    # 坐标轴 mesh 管理 (世界轴 + 每 joint 坐标系)
    # -----------------------------------------------------------------
    def make_axis_mesh(self, length):
        """构造一个 xyz 坐标轴 pyrender mesh。"""
        import pyrender
        import trimesh
        length = max(float(length), self.AXIS_MIN)
        ax = trimesh.creation.axis(
            origin_size=length * 0.08, axis_length=length,
            axis_radius=length * 0.02)
        return pyrender.Mesh.from_trimesh(ax, smooth=False)

    def link_world_pose(self, link_name):
        """从 yourdfpy scene graph 取 link 的世界变换 (4x4)。"""
        tri_scene = self.robot.collision_scene if self.collision \
            else self.robot.scene
        try:
            return tri_scene.graph.get(link_name)[0]
        except Exception:
            return np.eye(4)

    def rebuild_world_axis(self, length):
        """按 length 重建世界坐标轴 node。"""
        if self.axis_state["world_node"] is not None:
            try:
                self.scene_pr.remove_node(self.axis_state["world_node"])
            except Exception:
                pass
            self.axis_state["world_node"] = None
        if length > 0:
            self.axis_state["world_node"] = self.scene_pr.add(
                self.make_axis_mesh(length), pose=np.eye(4))

    def set_joint_frame(self, idx, on):
        """开/关某 joint 的坐标系显示。"""
        nodes = self.axis_state["joint_nodes"]
        if on and idx not in nodes:
            length = self.state.axis_scale
            pose = self.link_world_pose(self._joint_child.get(idx, ""))
            nodes[idx] = self.scene_pr.add(self.make_axis_mesh(length), pose=pose)
        elif not on and idx in nodes:
            try:
                self.scene_pr.remove_node(nodes[idx])
            except Exception:
                pass
            del nodes[idx]

    def update_joint_frames(self):
        """关节角变化后刷新各已显示 joint 坐标系的 pose。"""
        for idx, node in self.axis_state["joint_nodes"].items():
            pose = self.link_world_pose(self._joint_child.get(idx, ""))
            try:
                self.scene_pr.set_pose(node, pose)
            except Exception:
                pass

    def rebuild_joint_frames(self):
        """坐标轴大小变化后, 用新 axis_scale 重建所有已开启的 joint 坐标系。"""
        for idx in list(self.axis_state["joint_nodes"].keys()):
            self.set_joint_frame(idx, False)
            self.set_joint_frame(idx, True)

    # -----------------------------------------------------------------
    # link 可见度
    # -----------------------------------------------------------------
    def set_link_visible(self, geom_name, on):
        """开/关某 link 的可见度。"""
        node = self.link_node_map.get(geom_name)
        if node is not None and node.mesh is not None:
            node.mesh.is_visible = bool(on)
            self.state.link_visible[geom_name] = bool(on)

    # -----------------------------------------------------------------
    # 预设视角
    # -----------------------------------------------------------------
    @staticmethod
    def look_at(eye, target, up=(0.0, 0.0, 1.0)):
        """构造相机 pose (相机看向 -Z, pyrender 约定)。"""
        eye = np.asarray(eye, float)
        target = np.asarray(target, float)
        up = np.asarray(up, float)
        fwd = target - eye
        n = np.linalg.norm(fwd)
        if n < 1e-9:
            return np.eye(4)
        fwd /= n
        right = np.cross(fwd, up)
        if np.linalg.norm(right) < 1e-6:
            up = np.array([0.0, 1.0, 0.0])
            right = np.cross(fwd, up)
        right /= np.linalg.norm(right)
        up2 = np.cross(right, fwd)
        M = np.eye(4)
        M[:3, 0] = right
        M[:3, 1] = up2
        M[:3, 2] = -fwd
        M[:3, 3] = eye
        return M

    def view_preset_pose(self, preset):
        """返回预设视角的相机 pose；'reset' 返回 None (由 _reset_view 处理)。"""
        if preset == "reset":
            return None
        centroid = self.scene_pr.centroid
        scale = self.scene_pr.scale or 1.0
        dist = scale * 2.2
        if preset == "front":       # 沿 -Y 看向 +Y
            eye = centroid + np.array([0.0, -dist, 0.25 * dist])
        elif preset == "side":      # 沿 +X 看向 -X
            eye = centroid + np.array([dist, 0.0, 0.25 * dist])
        elif preset == "top":       # 俯视
            return self.look_at(centroid + np.array([0.0, 0.0, dist]),
                                centroid, up=(0.0, 1.0, 0.0))
        else:                        # iso 等距
            eye = centroid + np.array([dist, -dist, dist]) * 0.7
        return self.look_at(eye, centroid)

    # -----------------------------------------------------------------
    # 左侧面板：布局 + ASCII 条 + 编辑缓冲
    # -----------------------------------------------------------------
    def panel_geom(self):
        """返回面板布局常量元组 (x, top_margin, font_pt, line_h, header, row_w)。"""
        return (self.PANEL["x"], self.PANEL["top_margin"], self.PANEL["font_pt"],
                self.PANEL["line_h"], self.PANEL["header_lines"],
                self.PANEL["row_w"])

    @staticmethod
    def fmt_bar(value, lo, hi, width=16):
        """把 value 在 [lo,hi] 的位置画成 ASCII 进度条 [####----]。"""
        if lo is None or hi is None or not np.isfinite(lo) \
                or not np.isfinite(hi) or hi <= lo:
            return "[" + "?" * width + "]"
        frac = float(np.clip((value - lo) / (hi - lo), 0.0, 1.0))
        fill = int(round(frac * width))
        return "[" + "#" * fill + "-" * (width - fill) + "]"

    def apply_edit_buffer(self):
        """把 edit_buf 解析为数值并应用到正在编辑的关节。返回是否成功。"""
        idx = self.state.editing
        if idx is None:
            return False
        buf = self.state.edit_buf.strip()
        try:
            val = float(buf)
        except ValueError:
            print("[edit] 无法解析输入 %r，取消" % buf)
            return False
        if self.state.edit_unit == "deg":
            val = float(np.radians(val))
        self.apply_joint(idx, val)
        print("[edit] 关节 %d 设为 %.4f rad (%.2f deg)"
              % (idx + 1, self.robot.cfg[idx], np.degrees(self.robot.cfg[idx])))
        return True

    def begin_edit(self, idx, unit=None):
        """进入某关节编辑态，缓冲预填当前值 (首次键入会清空替换)。"""
        self.state.editing = idx
        self.state.selected = idx
        self.state.edit_fresh = True
        if unit is not None:
            self.state.edit_unit = unit
        if self.state.edit_unit == "deg":
            self.state.edit_buf = "%.2f" % np.degrees(self.robot.cfg[idx])
        else:
            self.state.edit_buf = "%.4f" % self.robot.cfg[idx]

    def cancel_edit(self):
        self.state.editing = None
        self.state.edit_buf = ""
        self.state.edit_fresh = True
