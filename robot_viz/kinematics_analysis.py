#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运动学结构分析：关节轴几何、构型分类 (Pieper/SRS)、标准 DH 参数提取。

纯函数模块，输入 yourdfpy robot，不依赖 pyrender。
- 关节轴几何：零位下各 actuated 关节轴的世界方向与通过点。
- 构型分类：末端三轴是否交于一点 (球腕/Pieper)、7 轴球肩-肘-球腕 (SRS)。
- 标准 DH：逐帧构造法拟合 (a, alpha, d, theta)。
"""

import numpy as np


# ----------------------------------------------------------------------
# 旋转矩阵 -> RPY (XYZ 固定轴欧拉角, 弧度)
# ----------------------------------------------------------------------
def matrix_to_rpy(R):
    """3x3 旋转矩阵 -> (roll, pitch, yaw) 弧度 (绕 X,Y,Z 固定轴)。"""
    R = np.asarray(R, dtype=float)
    sy = float(np.clip(-R[2, 0], -1.0, 1.0))
    pitch = np.arcsin(sy)
    if abs(sy) < 1.0 - 1e-9:
        roll = np.arctan2(R[2, 1], R[2, 2])
        yaw = np.arctan2(R[1, 0], R[0, 0])
    else:  # 万向锁
        roll = np.arctan2(-R[1, 2], R[1, 1])
        yaw = 0.0
    return np.array([roll, pitch, yaw])


# ----------------------------------------------------------------------
# 关节轴世界几何
# ----------------------------------------------------------------------
def joint_axes_world(robot):
    """零位下各 actuated 关节轴的世界方向与通过点。

    返回 [(name, dir(3,), point(3,)), ...]。
    """
    robot.update_cfg(np.zeros(robot.num_actuated_joints))
    scene = robot.scene
    out = []
    for j in robot.robot.joints:
        if j.name not in robot.actuated_joint_names:
            continue
        T_parent = np.asarray(scene.graph.get(j.parent)[0], dtype=float)
        T_joint = T_parent @ np.asarray(j.origin, dtype=float)
        d = T_joint[:3, :3] @ np.asarray(j.axis, dtype=float)
        n = np.linalg.norm(d)
        d = d / n if n > 1e-12 else d
        out.append((j.name, d, T_joint[:3, 3]))
    return out


def axes_intersect(axes, tol=1e-3):
    """最小二乘求多条直线 (name, dir, point) 的公共交点。

    每条线约束点 x 满足 (I - d d^T)(x - p) = 0。返回 (point, residual)，
    residual 为各线到 point 的最大垂距。
    """
    A = np.zeros((3, 3))
    b = np.zeros(3)
    for _n, d, p in axes:
        d = np.asarray(d, float)
        P = np.eye(3) - np.outer(d, d)
        A += P
        b += P @ np.asarray(p, float)
    try:
        x = np.linalg.lstsq(A, b, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None, np.inf
    res = 0.0
    for _n, d, p in axes:
        d = np.asarray(d, float)
        v = np.asarray(p, float) - x
        perp = v - np.dot(v, d) * d
        res = max(res, float(np.linalg.norm(perp)))
    return x, res


def classify_structure(robot):
    """判断机械臂结构构型。返回描述字符串。"""
    axes = joint_axes_world(robot)
    n = len(axes)
    scale = float(max(getattr(robot.scene, "scale", 1.0), 1e-3))
    tol = scale * 0.02   # 交点残差容差 (随模型尺度)

    if n == 6:
        _p, res = axes_intersect(axes[3:6], tol)
        if res < tol:
            return "Pieper (spherical wrist, last 3 axes intersect)"
        return "general 6-DOF (no spherical wrist)"

    if n == 7:
        _ps, res_s = axes_intersect(axes[0:3], tol)   # 肩
        _pw, res_w = axes_intersect(axes[4:7], tol)   # 腕
        if res_s < tol and res_w < tol:
            return "SRS (7-DOF spherical-roll-spherical)"
        if res_w < tol:
            return "7-DOF with spherical wrist"
        return "general 7-DOF (redundant)"

    return "general %d-DOF" % n


# ----------------------------------------------------------------------
# 标准 DH 参数提取 (显式帧构造, Spong 约定)
# ----------------------------------------------------------------------
def _build_dh_frames(axes, tol=1e-4):
    """由关节轴世界几何构造各关节 DH 帧 (4x4 世界位姿) 列表。

    F_i: z 轴 = 关节 i 轴；x 轴 = 公垂线方向 (z_{i-1}->z_i)；原点 = x 与 z_i 交点。
    F_0 原点取世界原点在 z_0 上的垂足 (基座偏移显式保留在 F_0)。
    """
    frames = []
    z0 = np.asarray(axes[0][1], float)
    p0 = np.asarray(axes[0][2], float)
    o0 = p0 - np.dot(p0, z0) * z0            # 世界原点到 z_0 的垂足
    x0 = None
    for ref in (np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])):
        cand = ref - np.dot(ref, z0) * z0
        if np.linalg.norm(cand) > 1e-6:
            x0 = cand / np.linalg.norm(cand)
            break
    y0 = np.cross(z0, x0)
    F0 = np.eye(4)
    F0[:3, 0], F0[:3, 1], F0[:3, 2], F0[:3, 3] = x0, y0, z0, o0
    frames.append(F0)

    for i in range(1, len(axes)):
        z_prev = frames[-1][:3, 2]
        o_prev = frames[-1][:3, 3]
        z_i = np.asarray(axes[i][1], float)
        p_i = np.asarray(axes[i][2], float)
        cross = np.cross(z_prev, z_i)
        ncross = np.linalg.norm(cross)
        if ncross > tol:                     # 一般：公垂线
            x_i = cross / ncross
            M = np.array([z_prev, -z_i, x_i]).T
            _s, t, _a = np.linalg.lstsq(M, p_i - o_prev, rcond=None)[0]
            o_i = p_i + t * z_i
        else:                                # 平行/共线：原点落 z_i 上使 d 规范
            w = p_i - o_prev
            perp = w - np.dot(w, z_i) * z_i
            npd = np.linalg.norm(perp)
            x_i = perp / npd if npd > tol else frames[-1][:3, 0]
            o_i = p_i - np.dot(w, z_i) * z_i
        y_i = np.cross(z_i, x_i)
        Fi = np.eye(4)
        Fi[:3, 0], Fi[:3, 1], Fi[:3, 2], Fi[:3, 3] = x_i, y_i, z_i, o_i
        frames.append(Fi)
    return frames


def _dh_from_relative(T, tol=1e-4):
    """从相邻帧相对变换 T = F_{i-1}^{-1} F_i 反解 (a, alpha, d, theta)。"""
    theta = np.arctan2(T[1, 0], T[0, 0])
    d = T[2, 3]
    a = np.hypot(T[0, 3], T[1, 3])
    alpha = np.arctan2(T[2, 1], T[2, 2])
    return a, alpha, d, theta


def extract_dh(robot, tol=1e-4):
    """从关节轴世界几何拟合标准 DH 参数。

    返回 [dict(joint, a, alpha, d, theta, note), ...] (单位: m / rad)。
    构造各关节帧后, 逐对相对变换反解 DH 四参数。note 标注该相对变换与 DH
    重建的残差 (平行/共线等退化情形残差仍应 ~0, 因帧已按 DH 约定构造)。
    row[0] 为基座帧 (可能含固定偏移, 参数记 0)。
    """
    axes = joint_axes_world(robot)
    frames = _build_dh_frames(axes, tol)
    rows = [{"joint": axes[0][0], "a": 0.0, "alpha": 0.0,
             "d": 0.0, "theta": 0.0, "note": "frame 0 (base)"}]
    for i in range(1, len(axes)):
        T = np.linalg.inv(frames[i - 1]) @ frames[i]
        a, alpha, d, theta = _dh_from_relative(T)
        resid = float(np.linalg.norm(
            _dh_transform(a, alpha, d, theta) - T))
        note = "" if resid < 1e-6 else "resid=%.1e" % resid
        rows.append({"joint": axes[i][0], "a": a, "alpha": alpha,
                     "d": d, "theta": theta, "note": note})
    return rows


def _dh_transform(a, alpha, d, theta):
    ca, sa = np.cos(alpha), np.sin(alpha)
    ct, st = np.cos(theta), np.sin(theta)
    return np.array([[ct, -st * ca, st * sa, a * ct],
                     [st, ct * ca, -ct * sa, a * st],
                     [0.0, sa, ca, d],
                     [0.0, 0.0, 0.0, 1.0]])


def format_dh_table(rows, structure=None):
    """把 DH 行格式化为终端表格字符串。"""
    lines = ["=" * 74, "  标准 DH 参数 (单位: a,d = m; alpha,theta = deg)"]
    if structure:
        lines.append("  结构构型: %s" % structure)
    lines.append("=" * 74)
    lines.append("  %-10s %10s %10s %10s %10s  %s"
                 % ("joint", "a", "alpha", "d", "theta", "note"))
    lines.append("  " + "-" * 70)
    for r in rows:
        lines.append("  %-10s %10.5f %10.3f %10.5f %10.3f  %s"
                     % (r["joint"], r["a"], np.degrees(r["alpha"]),
                        r["d"], np.degrees(r["theta"]), r["note"]))
    lines.append("=" * 74)
    return "\n".join(lines)


def print_dh_table(robot):
    """打印结构构型 + DH 参数表到终端。"""
    structure = classify_structure(robot)
    rows = extract_dh(robot)
    print(format_dh_table(rows, structure))
