from __future__ import annotations


def apply_theme(dpg) -> None:
    with dpg.theme(tag="editor_theme"):
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (18, 21, 26))
            dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (24, 28, 34))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (34, 39, 48))
            dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (45, 52, 64))
            dpg.add_theme_color(dpg.mvThemeCol_Button, (43, 50, 61))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (60, 71, 86))
            dpg.add_theme_color(dpg.mvThemeCol_Header, (52, 95, 130))
            dpg.add_theme_color(dpg.mvThemeCol_Text, (225, 230, 238))
            dpg.add_theme_style(dpg.mvStyleVar_WindowPadding, 10, 10)
            dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 8, 5)
            dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 8, 6)
            dpg.add_theme_style(dpg.mvStyleVar_WindowRounding, 4)
            dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 4)
    dpg.bind_theme("editor_theme")
