#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""手眼标定（Hand-Eye Calibration）纯数值仿真示范。

标定类型: eye-in-hand（相机固定安装在机械臂末端法兰上）。
目标: 求解相机坐标系相对末端法兰坐标系的固定变换 X (cam2gripper)。

本示范不做真实渲染/图像检测，而是:
  1) 复用本项目正运动学 (yourdfpy) 生成 N 组末端法兰世界位姿;
  2) 设定一个已知真值外参 X_true 与固定标定板位姿, 反算每组相机对标定板的观测;
  3) 调用 cv2.calibrateHandEye() 从这些位姿对中解出 X_est;
  4) 与真值对比, 打印平移/旋转误差。

无噪声时误差应接近机器精度 (~1e-10), 用于验证整条数学链路正确。

依赖: opencv-python (cv2), numpy, 以及本项目 robot_viz 加载链。
运行 (无需显示环境, 纯数值):
    python handeye_calibration_demo.py --robot gen3_lite --samples 12 --seed 0
    python handeye_calibration_demo.py --robot iiwa --samples 15 --noise 0.002
"""

import argparse

import numpy as np

# robot_viz/__init__.py 顶部已打 np.infty 兼容补丁; 复用现有加载链。
from robot_viz import xacro_to_urdf, load_robot, get_joint_limit
from main_ui_app import select_robot_source


# 各机器人的末端法兰 link 名 (已实测确认)。
END_EFFECTOR_LINK = {
    "gen3_lite": "tool_frame",
    "iiwa": "tool0",
}


# ----------------------------------------------------------------------
# 齐次变换工具
# ----------------------------------------------------------------------
def rotvec_to_matrix(rotvec):
    """旋转向量 (轴*角) -> 3x3 旋转矩阵 (Rodrigues)。"""
    theta = float(np.linalg.norm(rotvec))
    if theta < 1e-12:
        return np.eye(3)
    k = np.asarray(rotvec, dtype=float) / theta
    K = np.array([[0, -k[2], k[1]],
                  [k[2], 0, -k[0]],
                  [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(theta) * K + (1 - np.cos(theta)) * (K @ K)


def make_transform(rotvec, translation):
    """由旋转向量 + 平移组装 4x4 齐次变换。"""
    T = np.eye(4)
    T[:3, :3] = rotvec_to_matrix(rotvec)
    T[:3, 3] = np.asarray(translation, dtype=float)
    return T


def rotation_angle_deg(R):
    """旋转矩阵对应的旋转角 (度)。"""
    cos_t = (np.trace(R) - 1.0) / 2.0
    cos_t = float(np.clip(cos_t, -1.0, 1.0))
    return np.degrees(np.arccos(cos_t))


# ----------------------------------------------------------------------
# 机器人加载与位姿采样
# ----------------------------------------------------------------------
def load_arm(robot_name):
    """复用现有加载链, 返回 yourdfpy robot。"""
    xacro_path, mappings = select_robot_source(robot_name)
    urdf_xml, pkg_map = xacro_to_urdf(xacro_path, mappings)
    return load_robot(urdf_xml, pkg_map)


def link_world_pose(robot, link_name):
    """取 link 世界 4x4 位姿 (与 controller.link_world_pose 同法)。"""
    return np.asarray(robot.scene.graph.get(link_name)[0], dtype=float)


def sample_joint_config(robot, rng):
    """在各关节限位内均匀随机采样一组关节角; 连续关节回退到 [-pi, pi]。"""
    cfg = np.zeros(robot.num_actuated_joints)
    for i, name in enumerate(robot.actuated_joint_names):
        lo, hi = get_joint_limit(robot, name)
        if lo is None or hi is None or not np.isfinite(lo) or not np.isfinite(hi):
            lo, hi = -np.pi, np.pi
        cfg[i] = rng.uniform(lo, hi)
    return cfg


# ----------------------------------------------------------------------
# 主标定流程
# ----------------------------------------------------------------------
def run_calibration(robot_name, n_samples, noise, seed):
    import cv2

    rng = np.random.default_rng(seed)
    robot = load_arm(robot_name)
    ee_link = END_EFFECTOR_LINK[robot_name]

    print("=" * 68)
    print("  手眼标定示范 (eye-in-hand) — 机器人: %s" % robot_name)
    print("  末端法兰 link: %s | 关节数: %d | 采样数: %d | 噪声: %g"
          % (ee_link, robot.num_actuated_joints, n_samples, noise))
    print("=" * 68)

    # ---- 真值: 相机->末端法兰的固定外参 X_true (cam2gripper) ----
    # 一个有代表性的旋转 (约 15/-20/30 度组合) + 平移 (5cm,-3cm,8cm)。
    X_true = make_transform(
        rotvec=np.deg2rad([15.0, -20.0, 30.0]),
        translation=[0.05, -0.03, 0.08],
    )

    # ---- 标定板在基座系下的固定位姿 T_base_target ----
    T_base_target = make_transform(
        rotvec=np.deg2rad([180.0, 0.0, 0.0]),   # 标定板朝上
        translation=[0.4, 0.0, 0.2],
    )

    X_inv = np.linalg.inv(X_true)

    R_g2b, t_g2b = [], []   # gripper -> base
    R_t2c, t_t2c = [], []   # target  -> cam

    for _ in range(n_samples):
        cfg = sample_joint_config(robot, rng)
        robot.update_cfg(cfg)

        T_base_gripper = link_world_pose(robot, ee_link)     # gripper->base
        T_base_cam = T_base_gripper @ X_true                 # cam->base
        T_cam_target = np.linalg.inv(T_base_cam) @ T_base_target  # target->cam

        if noise > 0:
            # 平移加高斯噪声; 旋转加小角度扰动 (旋转向量)。
            T_cam_target = T_cam_target.copy()
            T_cam_target[:3, 3] += rng.normal(0.0, noise, size=3)
            dR = rotvec_to_matrix(rng.normal(0.0, noise, size=3))
            T_cam_target[:3, :3] = dR @ T_cam_target[:3, :3]

        R_g2b.append(T_base_gripper[:3, :3])
        t_g2b.append(T_base_gripper[:3, 3])
        R_t2c.append(T_cam_target[:3, :3])
        t_t2c.append(T_cam_target[:3, 3])

    # ---- OpenCV 手眼标定 (eye-in-hand) ----
    R_cam2gripper, t_cam2gripper = cv2.calibrateHandEye(
        R_gripper2base=R_g2b, t_gripper2base=t_g2b,
        R_target2cam=R_t2c, t_target2cam=t_t2c,
        method=cv2.CALIB_HAND_EYE_TSAI,
    )
    X_est = np.eye(4)
    X_est[:3, :3] = R_cam2gripper
    X_est[:3, 3] = t_cam2gripper.reshape(3)

    # ---- 评估 ----
    t_err_mm = np.linalg.norm(X_est[:3, 3] - X_true[:3, 3]) * 1000.0
    R_rel = X_est[:3, :3].T @ X_true[:3, :3]
    r_err_deg = rotation_angle_deg(R_rel)

    np.set_printoptions(precision=5, suppress=True)
    print("\n真值 X_true (cam->gripper):\n%s" % X_true)
    print("\n估计 X_est  (cam->gripper):\n%s" % X_est)
    print("\n" + "-" * 68)
    print("  平移误差: %.6f mm" % t_err_mm)
    print("  旋转误差: %.6f deg" % r_err_deg)
    print("-" * 68)
    if noise == 0:
        ok = (t_err_mm < 1e-3) and (r_err_deg < 1e-3)
        print("  [自检] 无噪声闭合精度: %s" % ("通过 ✓" if ok else "未通过 ✗"))
    return X_est, t_err_mm, r_err_deg


def build_arg_parser():
    p = argparse.ArgumentParser(description="手眼标定 (eye-in-hand) 纯数值仿真示范")
    p.add_argument("--robot", choices=["gen3_lite", "iiwa"], default="gen3_lite",
                   help="选择机器人 (默认 gen3_lite)")
    p.add_argument("--samples", type=int, default=12,
                   help="采样位姿组数 (默认 12, 建议 >= 8)")
    p.add_argument("--noise", type=float, default=0.0,
                   help="相机观测高斯噪声标准差 (米/弧度, 默认 0=无噪声)")
    p.add_argument("--seed", type=int, default=0,
                   help="随机种子 (默认 0, 保证可复现)")
    return p


def main():
    args = build_arg_parser().parse_args()
    if args.samples < 3:
        raise SystemExit("采样数过少, 手眼标定至少需要 3 组 (建议 >= 8)。")
    run_calibration(args.robot, args.samples, args.noise, args.seed)


if __name__ == "__main__":
    main()
