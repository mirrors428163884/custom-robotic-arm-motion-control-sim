#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""xacro -> URDF 转换与 yourdfpy 加载。"""

import os
from pathlib import Path


# 仓库根目录：本模块位于 <repo>/robot_viz/urdf_loader.py，上跳两级到 <repo>。
# 注意 (PITFALLS 拆分陷阱)：拆入子包后 __file__ 变深，不能再用
# os.path.dirname(__file__) 当 repo_root，否则 pkg_map 指错目录、mesh/xacro 找不到。
REPO_ROOT = str(Path(__file__).resolve().parents[1])


def xacro_to_urdf(xacro_path, mappings=None, repo_root=None):
    """将 xacro 文件展开为 URDF XML 字符串。

    通过 monkey-patch xacro.substitution_args._eval_find，
    把 $(find pkg) 映射到本地仓库目录，绕过 ROS ament_index。
    """
    import xacro
    from xacro import substitution_args as sa

    repo_root = repo_root or REPO_ROOT
    pkg_map = {
        "gen3_lite_description": os.path.join(repo_root, "gen3_lite_description"),
        "iiwa_description": os.path.join(repo_root, "iiwa_description"),
    }

    def _my_eval_find(pkg):
        if pkg in pkg_map:
            return pkg_map[pkg]
        guess = os.path.join(repo_root, pkg)
        if os.path.isdir(guess):
            return guess
        raise RuntimeError(
            "无法解析 $(find %s)，请在 pkg_map 中添加映射。" % pkg
        )

    sa._eval_find = _my_eval_find

    doc = xacro.process_file(xacro_path, mappings=mappings or {})
    return doc.toxml(), pkg_map


def make_iiwa_top_level_xacro(repo_root=None):
    """iiwa.urdf.xacro 只定义宏，需生成一个顶层文件实例化它。

    生成临时 xacro，include 宏文件并调用 <xacro:iiwa>。
    """
    repo_root = repo_root or REPO_ROOT
    tmp_path = os.path.join(repo_root, "iiwa_description/urdf/iiwa_top.urdf.xacro")
    content = """<?xml version="1.0"?>
<robot name="iiwa" xmlns:xacro="http://www.ros.org/wiki/xacro">
  <xacro:include filename="iiwa.urdf.xacro" />
  <link name="world"/>
  <xacro:iiwa parent="world" prefix="">
    <origin rpy="0 0 0" xyz="0 0 0"/>
  </xacro:iiwa>
</robot>
"""
    with open(tmp_path, "w") as f:
        f.write(content)
    return tmp_path


def load_robot(urdf_xml, pkg_map):
    """用 yourdfpy 加载 URDF XML，返回 URDF 对象。

    yourdfpy.URDF.load 把 str 当文件路径，故用 io.StringIO 包装为
    file-like 对象；mesh_dir 设为空（mesh 路径由 filename_handler 解析）。
    """
    import io
    import yourdfpy

    def filename_handler(fname=None, **kwargs):
        if fname is None:
            return fname
        if fname.startswith("package://"):
            rest = fname[len("package://"):]
            parts = rest.split("/", 1)
            pkg = parts[0]
            rel = parts[1] if len(parts) > 1 else ""
            base = pkg_map.get(pkg, pkg)
            return os.path.join(base, rel)
        if fname.startswith("file://"):
            return _fix_mesh_path(fname[len("file://"):])
        return _fix_mesh_path(fname)

    def _fix_mesh_path(path):
        """修正损坏的 mesh 路径。

        iiwa 的 base_link.dae 文件损坏（含两个 COLLADA 根），
        回退到对应的 collision stl。
        """
        if path.endswith("/visual/base_link.dae") and "lbr_iiwa_14_r820" in path:
            stl = path.replace("/visual/base_link.dae",
                               "/collision/base_link.stl")
            if os.path.isfile(stl):
                return stl
        return path

    robot = yourdfpy.URDF.load(
        io.StringIO(urdf_xml),
        filename_handler=filename_handler,
        mesh_dir="",
        build_scene_graph=True,
        load_meshes=True,
        build_collision_scene_graph=True,
        load_collision_meshes=True,
    )
    return robot
