#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JointViewer — pyrender.Viewer 子类，窗口内左/右悬浮面板 + 键鼠交互。

面板通过每帧 self._renderer.render_text 直接绘制到 OpenGL 视口 (immediate-mode)，
而非 pyglet.gui 控件——后者走 legacy 顶点数组，与 pyrender 的 OpenGL core profile
不兼容 (glPushClientAttrib 报错, 见 PITFALLS 1.2)。字体表仅 ASCII 0-127。

所有对 robot/scene/state 的访问都经由 self.ctrl (RobotSceneController)。
"""

import time as _time

import numpy as np
import pyrender
import pyglet.window.key as pkey
from pyrender.constants import TextAlign

from .joint_utils import get_joint_limit, print_joint_angles
from .help_text import print_help


class JointViewer(pyrender.Viewer):
    """键盘交互 + 左侧关节输入面板 + 右侧设置面板。"""

    def __init__(self, controller, *a, **kw):
        self.ctrl = controller
        us = controller.ui_scale
        # 右侧面板布局常量 (实例属性，因 class-body 无法访问 controller.ui_scale)
        self.RP_W = int(300 * us)            # 面板宽度 (px)
        self.RP_TOP = int(20 * us)           # 顶部边距
        self.RP_LINE_H = int(round(26 * us))  # 行高
        self.RP_TAB_H = int(120 * us)        # 收起时右缘竖条 tab 高度
        self.RP_FONT_PT = int(round(16 * us))  # 右侧面板字号
        # FPS 统计 (在 super().__init__ 之前初始化, on_resize 可能触发 on_draw)
        self._fps_frames = 0
        self._fps_last_t = _time.time()
        self._fps_value = 0.0
        super(JointViewer, self).__init__(*a, **kw)

    # ------------------------------------------------------------------
    # 左侧面板：关节行像素矩形
    # ------------------------------------------------------------------
    def _row_rect(self, row_idx):
        """第 row_idx 个关节行的像素矩形 (x0, y0, x1, y1)，原点左下。"""
        x, top_margin, _fp, line_h, header, row_w = self.ctrl.panel_geom()
        y_top = self.viewport_size[1] - top_margin
        line_top = y_top - (header + row_idx) * line_h
        return (x, line_top - line_h, x + row_w, line_top)

    def _panel_row_at(self, px, py):
        """返回鼠标 (px,py) 命中的关节行 idx，未命中返回 None。"""
        for i in range(self.ctrl.n_joints):
            x0, y0, x1, y1 = self._row_rect(i)
            if x0 <= px <= x1 and y0 <= py <= y1:
                return i
        return None

    # ------------------------------------------------------------------
    # 右侧设置面板：行模型 (绘制与命中共用)
    # ------------------------------------------------------------------
    def _rpanel_rows(self):
        """构造右侧面板行模型。返回 [(text, kind, action), ...]。

        kind:  'title' | 'toggle' | 'slider' | 'button'
        action: ('link', geom) / ('jframe', idx) / ('view', 'front') /
                ('axis',) / ('panel','close') / (None,)
        """
        ctrl = self.ctrl
        st = ctrl.state
        rows = [("== SETTINGS ==  [>] hide", "title", ("panel", "close"))]
        # AXIS 组
        rows.append(("- AXIS SIZE -", "title", (None,)))
        lo, hi = 0.0, float(max(ctrl.scene_pr.scale, 1e-3)) * 0.6
        bar = ctrl.fmt_bar(st.axis_scale, lo, hi, width=12)
        rows.append(("world axis %s %.3f" % (bar, st.axis_scale),
                     "slider", ("axis",)))
        # VIEW 组
        rows.append(("- VIEW -", "title", (None,)))
        for label, key in [("Front", "front"), ("Side", "side"),
                           ("Top", "top"), ("Iso", "iso"),
                           ("Reset view", "reset")]:
            rows.append(("  [ %s ]" % label, "button", ("view", key)))
        # JOINT FRAMES 组
        rows.append(("- JOINT FRAMES -", "title", (None,)))
        for i in range(ctrl.n_joints):
            mark = "x" if st.joint_frames[i] else " "
            rows.append(("[%s] %s" % (mark, ctrl.robot.actuated_joint_names[i]),
                         "toggle", ("jframe", i)))
        # LINKS 组
        rows.append(("- LINKS -", "title", (None,)))
        for geom in [nk for nk, _ in ctrl.node_list]:
            mark = "x" if st.link_visible.get(geom, True) else " "
            name = geom[:-4] if geom.lower().endswith(".stl") else geom
            rows.append(("[%s] %s" % (mark, name), "toggle", ("link", geom)))
        return rows

    def _rpanel_row_rect(self, row_idx):
        """右侧面板第 row_idx 行的像素矩形 (x0,y0,x1,y1)。"""
        x1 = self.viewport_size[0] - int(12 * self.ctrl.ui_scale)
        x0 = x1 - self.RP_W
        y_top = self.viewport_size[1] - self.RP_TOP
        line_top = y_top - row_idx * self.RP_LINE_H
        return (x0, line_top - self.RP_LINE_H, x1, line_top)

    def _rpanel_tab_rect(self):
        """收起态右缘竖条 tab 的像素矩形。"""
        x1 = self.viewport_size[0]
        x0 = x1 - int(34 * self.ctrl.ui_scale)
        cy = self.viewport_size[1] - self.RP_TOP
        return (x0, cy - self.RP_TAB_H, x1, cy)

    def _rpanel_hit(self, px, py):
        """右侧面板命中检测。返回 ('tab', None) / ('row', (i, action)) / None。"""
        if not self.ctrl.state.rpanel_open:
            x0, y0, x1, y1 = self._rpanel_tab_rect()
            if x0 <= px <= x1 and y0 <= py <= y1:
                return ("tab", None)
            return None
        for i, (_t, _k, action) in enumerate(self._rpanel_rows()):
            x0, y0, x1, y1 = self._rpanel_row_rect(i)
            if x0 <= px <= x1 and y0 <= py <= y1:
                return ("row", (i, action))
        return None

    def _apply_rpanel_action(self, action):
        """执行右侧面板某行的点击动作 (toggle/button)。滑条行由拖拽处理。"""
        ctrl = self.ctrl
        kind = action[0]
        if kind == "jframe":
            idx = action[1]
            ctrl.state.joint_frames[idx] = not ctrl.state.joint_frames[idx]
            ctrl.set_joint_frame(idx, ctrl.state.joint_frames[idx])
        elif kind == "link":
            geom = action[1]
            cur = ctrl.state.link_visible.get(geom, True)
            ctrl.set_link_visible(geom, not cur)
        elif kind == "view":
            self._apply_view(action[1])
        elif kind == "panel" and action[1] == "close":
            ctrl.state.rpanel_open = False

    def _apply_view(self, preset):
        """切换预设视角 / 重置视角。"""
        from pyrender.trackball import Trackball
        if preset == "reset":
            self._reset_view()
            return
        pose = self.ctrl.view_preset_pose(preset)
        if pose is None or not np.all(np.isfinite(pose)):
            return
        self._camera_node.matrix = pose
        self._trackball = Trackball(
            pose, self.viewport_size, self.ctrl.scene_pr.scale or 1.0,
            self.ctrl.scene_pr.centroid)

    # ------------------------------------------------------------------
    # 键盘
    # ------------------------------------------------------------------
    def on_text(self, text):
        """编辑态下累积输入字符 (数字/./-)。首次键入清空预填值。"""
        st = self.ctrl.state
        if st.editing is None:
            return
        for ch in text:
            if ch.isdigit() or ch in ".-+eE":
                if st.edit_fresh:
                    st.edit_buf = ""
                    st.edit_fresh = False
                st.edit_buf += ch

    def on_key_press(self, symbol, modifiers):
        ctrl = self.ctrl
        st = ctrl.state
        robot = ctrl.robot
        n_joints = ctrl.n_joints

        # ---- 编辑态：键盘被面板独占 ----
        if st.editing is not None:
            if symbol in (pkey.RETURN, pkey.ENTER):
                if ctrl.apply_edit_buffer():
                    ctrl.cancel_edit()
            elif symbol == pkey.ESCAPE:
                print("[edit] 取消编辑")
                ctrl.cancel_edit()
            elif symbol == pkey.BACKSPACE:
                st.edit_fresh = False
                st.edit_buf = st.edit_buf[:-1]
            elif symbol == pkey.TAB:
                unit = "deg" if st.edit_unit == "rad" else "rad"
                ctrl.begin_edit(st.editing, unit=unit)
            return

        sel = st.selected
        step = st.step

        if pkey._1 <= symbol <= pkey._9:
            idx = symbol - pkey._1
            if idx < n_joints:
                st.selected = idx
        elif symbol == pkey.LEFT:
            ctrl.apply_joint(sel, robot.cfg[sel] - step)
        elif symbol == pkey.RIGHT:
            ctrl.apply_joint(sel, robot.cfg[sel] + step)
        elif symbol == pkey.UP:
            ctrl.apply_joint(sel, robot.cfg[sel] + step * 5)
        elif symbol == pkey.DOWN:
            ctrl.apply_joint(sel, robot.cfg[sel] - step * 5)
        elif symbol == ord("["):
            st.selected = (sel - 1) % n_joints
        elif symbol == ord("]"):
            st.selected = (sel + 1) % n_joints
        elif symbol == ord("e"):
            ctrl.begin_edit(sel)
        elif symbol == ord("g"):
            st.rpanel_open = not st.rpanel_open
            print("[panel] 右侧设置面板 %s"
                  % ("展开" if st.rpanel_open else "收起"))
        elif symbol == ord("r"):
            ctrl.reset_joints()
            print("[reset] 所有关节归零")
        elif symbol == ord("p"):
            st.show_link_poses = not st.show_link_poses
            print("[hud] link 位姿显示 %s"
                  % ("开" if st.show_link_poses else "关"))
        elif symbol == ord("c"):
            print_joint_angles(robot, st.selected)
        elif symbol == ord("h"):
            print_help(n_joints)
        elif symbol == ord("q") or symbol == pkey.ESCAPE:
            print("[quit] 退出")
            self.close()
            return
        else:
            super(JointViewer, self).on_key_press(symbol, modifiers)
            return

        print_joint_angles(robot, st.selected)

    # ------------------------------------------------------------------
    # 鼠标
    # ------------------------------------------------------------------
    def on_mouse_press(self, x, y, buttons, modifiers):
        ctrl = self.ctrl
        st = ctrl.state
        # 先测右侧设置面板 (在最上层)
        hit = self._rpanel_hit(x, y)
        if hit is not None:
            st.gesture = "rpanel"
            st.press = None
            st.rpanel_press = None
            if hit[0] == "tab":
                st.rpanel_open = not st.rpanel_open
            else:
                _row_idx, action = hit[1]
                if action[0] == "axis":
                    st.rpanel_press = {
                        "kind": "axis", "x0": x, "v0": st.axis_scale}
                else:
                    self._apply_rpanel_action(action)
            return  # 吞掉事件
        idx = self._panel_row_at(x, y)
        if idx is not None:
            # 命中左侧面板：进入编辑态，记录用于拖拽
            ctrl.begin_edit(idx)
            st.gesture = "panel"
            st.press = {"idx": idx, "x0": x,
                        "v0": float(ctrl.robot.cfg[idx]), "moved": False}
            return  # 吞掉事件，不传给 trackball (避免转视角)
        # 未命中面板：交回 pyrender (会调用 trackball.down 初始化 _pdown)
        st.gesture = "view"
        st.press = None
        return super(JointViewer, self).on_mouse_press(x, y, buttons, modifiers)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        ctrl = self.ctrl
        st = ctrl.state
        press = st.press
        if st.gesture == "rpanel":
            rp = st.rpanel_press
            if rp is not None and rp["kind"] == "axis":
                # 世界轴大小滑条：横向像素映射
                hi = float(max(ctrl.scene_pr.scale, 1e-3)) * 0.6
                val = rp["v0"] + (x - rp["x0"]) / 300.0 * hi
                val = float(np.clip(val, ctrl.AXIS_MIN, hi))
                st.axis_scale = val
                ctrl.rebuild_world_axis(val)
                ctrl.rebuild_joint_frames()
            return
        if st.gesture == "panel" and press is not None:
            # 面板行拖拽：横向像素映射到关节 limit 范围
            idx = press["idx"]
            name = ctrl.robot.actuated_joint_names[idx]
            lo, hi = get_joint_limit(ctrl.robot, name)
            if lo is not None and hi is not None and hi > lo:
                span = hi - lo
                val = press["v0"] + (x - press["x0"]) / 400.0 * span
                ctrl.apply_joint(idx, val)
                press["moved"] = True
                st.edit_fresh = False
                if st.edit_unit == "deg":
                    st.edit_buf = "%.2f" % np.degrees(ctrl.robot.cfg[idx])
                else:
                    st.edit_buf = "%.4f" % ctrl.robot.cfg[idx]
            return
        if st.gesture != "view":
            # 无有效视角手势 (press 被面板吞掉或已结束)：勿调 trackball，
            # 否则 trackball._pdown 未初始化会 AttributeError 崩溃 (PITFALLS 2.1)。
            return
        return super(JointViewer, self).on_mouse_drag(
            x, y, dx, dy, buttons, modifiers)

    def on_mouse_release(self, x, y, button, modifiers):
        ctrl = self.ctrl
        st = ctrl.state
        press = st.press
        gesture = st.gesture
        st.press = None
        st.gesture = None
        if gesture == "rpanel":
            st.rpanel_press = None
            return
        if gesture == "panel":
            if press is not None and press["moved"]:
                ctrl.cancel_edit()   # 拖拽结束即定稿，退出编辑态
            return
        return super(JointViewer, self).on_mouse_release(
            x, y, button, modifiers)

    # ------------------------------------------------------------------
    # 绘制
    # ------------------------------------------------------------------
    def _panel_lines(self):
        """构造左侧面板每行文本 (纯 ASCII)。返回 [(text, kind), ...]。"""
        ctrl = self.ctrl
        st = ctrl.state
        sel = st.selected
        editing = st.editing
        names = ctrl.robot.actuated_joint_names
        cfg = ctrl.robot.cfg
        out = [
            ("FPS %5.1f  |  %dx%d  |  %s  |  step %.3f rad  |  "
             "click a row to edit, Tab=rad/deg, Enter=apply"
             % (self._fps_value, self.viewport_size[0],
                self.viewport_size[1], ctrl.robot_name, st.step),
             "header"),
            ("STRUCTURE: %s  |  p=toggle link poses" % ctrl.structure,
             "header"),
            ("", "header"),
        ]
        for i, name in enumerate(names):
            lo, hi = get_joint_limit(ctrl.robot, name)
            bar = ctrl.fmt_bar(float(cfg[i]), lo, hi)
            if i == editing:
                field = "[ %s_ ] %s" % (st.edit_buf, st.edit_unit)
                text = "> [%d] %-14s %s   %s" % (i + 1, name, field, bar)
                kind = "edit"
            else:
                marker = ">" if i == sel else " "
                text = ("%s [%d] %-14s %8.3f rad (%7.1f deg) %s"
                        % (marker, i + 1, name, float(cfg[i]),
                           np.degrees(float(cfg[i])), bar))
                kind = "sel" if i == sel else "row"
            out.append((text, kind))

        # ---- 各 link 实时世界位姿 ----
        if st.show_link_poses:
            out.append(("", "header"))
            out.append(("-- LINK POSES (world) --  xyz[m]  rpy[deg]", "header"))
            for link, xyz, rpy in ctrl.link_pose_rows():
                text = ("  %-18s % .3f % .3f % .3f  |  "
                        "% 6.1f % 6.1f % 6.1f"
                        % (link, xyz[0], xyz[1], xyz[2],
                           rpy[0], rpy[1], rpy[2]))
                out.append((text, "pose"))
        return out

    def _draw_panel(self):
        """逐行绘制左侧悬浮面板到视口左上角。"""
        if self._renderer is None:
            return
        x, top_margin, font_pt, line_h, _hdr, _rw = self.ctrl.panel_geom()
        y_top = self.viewport_size[1] - top_margin
        colors = {
            "header": (0.75, 0.80, 0.90, 1.0),
            "row": (0.92, 0.92, 0.96, 1.0),
            "sel": (0.55, 0.85, 1.00, 1.0),
            "edit": (1.00, 0.85, 0.30, 1.0),
            "pose": (0.65, 0.90, 0.70, 1.0),
        }
        for i, (text, kind) in enumerate(self._panel_lines()):
            if not text:
                continue
            self._renderer.render_text(
                text, x, y_top - i * line_h,
                font_pt=font_pt, color=colors[kind],
                align=TextAlign.TOP_LEFT,
            )

    def _draw_rpanel(self):
        """绘制右侧设置面板 (收起=竖条 tab, 展开=右对齐多行)。"""
        if self._renderer is None:
            return
        us = self.ctrl.ui_scale
        if not self.ctrl.state.rpanel_open:
            _x0, _y0, x1, y1 = self._rpanel_tab_rect()
            self._renderer.render_text(
                "[<] SET", x1 - int(6 * us), y1 - int(8 * us),
                font_pt=self.RP_FONT_PT,
                color=(0.75, 0.80, 0.90, 1.0), align=TextAlign.TOP_RIGHT)
            return
        x_right = self.viewport_size[0] - int(12 * us)
        y_top = self.viewport_size[1] - self.RP_TOP
        colors = {
            "title": (0.70, 0.78, 0.92, 1.0),
            "toggle": (0.92, 0.92, 0.96, 1.0),
            "slider": (0.55, 0.85, 1.00, 1.0),
            "button": (1.00, 0.85, 0.30, 1.0),
        }
        for i, (text, kind, _a) in enumerate(self._rpanel_rows()):
            self._renderer.render_text(
                text, x_right, y_top - i * self.RP_LINE_H,
                font_pt=self.RP_FONT_PT,
                color=colors.get(kind, (1, 1, 1, 1)),
                align=TextAlign.TOP_RIGHT)

    def _tick_fps(self):
        self._fps_frames += 1
        now = _time.time()
        dt = now - self._fps_last_t
        if dt >= 0.5:
            self._fps_value = self._fps_frames / dt
            self._fps_frames = 0
            self._fps_last_t = now

    def on_draw(self):
        super(JointViewer, self).on_draw()
        self._tick_fps()
        try:
            self._draw_panel()
            self._draw_rpanel()
        except Exception:
            pass
