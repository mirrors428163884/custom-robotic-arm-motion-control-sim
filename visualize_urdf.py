#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""兼容入口 —— 实现已拆分到 robot_viz 包，主入口为 main_ui_app.py。

保留此文件是为了不破坏既有习惯用法:
    python visualize_urdf.py --robot iiwa

所有逻辑见 main_ui_app.py 与 robot_viz/。
"""

from main_ui_app import main

if __name__ == "__main__":
    main()
