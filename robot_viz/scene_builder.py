#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 yourdfpy 的 trimesh scene 构建 pyrender scene，并同步关节 pose。"""

import numpy as np


def build_pyrender_scene(robot, collision=False):
    """把 yourdfpy 的 trimesh scene 转为 pyrender scene。

    返回 (pyrender_scene, node_list)，node_list: [(node_key, pr_node), ...]。
    """
    import pyrender

    tri_scene = robot.collision_scene if collision else robot.scene

    geometries = {}
    for name, geom in tri_scene.geometry.items():
        if hasattr(geom, "vertices") and len(geom.vertices) == 0:
            continue
        try:
            m = pyrender.Mesh.from_trimesh(geom, smooth=False)
            geometries[name] = m
        except Exception:
            continue

    scene_pr = pyrender.Scene(
        bg_color=np.array([0.12, 0.13, 0.16, 1.0]),
        ambient_light=np.array([0.35, 0.35, 0.38]),
    )

    node_list = []
    for node_key in tri_scene.graph.nodes_geometry:
        pose, geom_name = tri_scene.graph[node_key]
        if geom_name not in geometries:
            continue
        pr_node = scene_pr.add(geometries[geom_name], pose=pose)
        node_list.append((node_key, pr_node))

    # 灯光
    dir_light = pyrender.DirectionalLight(color=np.ones(3), intensity=3.0)
    scene_pr.add(dir_light, pose=np.eye(4))

    # 相机：使用 pyrender 标准等距视角（与 Viewer 默认一致）
    cam = pyrender.PerspectiveCamera(yfov=np.pi / 3.0)
    cam_pose = compute_camera_pose(tri_scene)
    scene_pr.add(cam, pose=cam_pose)

    return scene_pr, node_list


def compute_camera_pose(tri_scene):
    """根据 scene 包围盒计算相机位姿（pyrender 标准等距视角）。"""
    try:
        bounds = tri_scene.bounds
        if bounds is None or len(bounds) == 0:
            return np.eye(4)
        mins = np.asarray(bounds[0], dtype=float)
        maxs = np.asarray(bounds[1], dtype=float)
    except Exception:
        return np.eye(4)

    centroid = (mins + maxs) / 2.0
    size = maxs - mins
    scale = float(np.linalg.norm(size))

    # pyrender 标准等距视角旋转矩阵
    s2 = 1.0 / np.sqrt(2.0)
    cp = np.eye(4)
    cp[:3, :3] = np.array([
        [0.0, -s2, s2],
        [1.0, 0.0, 0.0],
        [0.0, s2, s2],
    ])
    # 距离：保证整个物体在视野内
    hfov = np.pi / 6.0
    dist = scale / (2.0 * np.tan(hfov))
    cp[:3, 3] = dist * np.array([1.0, 0.0, 1.0]) + centroid
    return cp


def sync_poses(robot, scene_pr, node_list, collision=False):
    """根据 yourdfpy 当前 cfg 更新 pyrender scene 中各 mesh 节点位姿。"""
    tri_scene = robot.collision_scene if collision else robot.scene
    for node_key, pr_node in node_list:
        try:
            pose, geom_name = tri_scene.graph[node_key]
            scene_pr.set_pose(pr_node, pose)
        except Exception:
            continue
