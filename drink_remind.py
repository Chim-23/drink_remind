# -*- coding: utf-8 -*-
"""喝水提醒 — 工作日定时霸屏提醒，支持自定义与开机自启。"""

from __future__ import annotations

import json
import os
import sys
import threading
import winsound
from datetime import datetime, timedelta
from pathlib import Path
from collections.abc import Callable
from typing import Any

import tkinter as tk
from tkinter import messagebox, ttk

APP_NAME = "DrinkRemind"
APP_TITLE = "喝水提醒"
DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": True,
    "weekdays_only": True,
    "reminders": [
        {"time": "10:00", "title": "喝水提醒", "message": "半杯，约 275 毫升", "enabled": True},
        {"time": "11:30", "title": "喝水提醒", "message": "喝完剩下半杯，约 275 毫升", "enabled": True},
        {"time": "14:30", "title": "喝水提醒", "message": "重新装一杯，喝半杯，约 275 毫升", "enabled": True},
        {"time": "16:30", "title": "喝水提醒", "message": "喝完剩下半杯，约 275 毫升", "enabled": True},
    ],
    "auto_start": True,
    "sound": True,
    "snooze_minutes": 5,
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def config_path() -> Path:
    return app_dir() / "config.json"


def load_config() -> dict[str, Any]:
    path = config_path()
    if not path.exists():
        save_config(DEFAULT_CONFIG)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    merged.update({k: v for k, v in data.items() if k != "reminders"})
    if isinstance(data.get("reminders"), list) and data["reminders"]:
        merged["reminders"] = data["reminders"]
    return merged


def save_config(cfg: dict[str, Any]) -> None:
    path = config_path()
    with path.open("w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def exe_path_for_autostart() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    script = Path(__file__).resolve()
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    runner = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{runner}" "{script}"'


def set_auto_start(enabled: bool) -> None:
    try:
        import winreg
    except ImportError:
        return
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path_for_autostart())
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def is_auto_start_enabled() -> bool:
    try:
        import winreg
    except ImportError:
        return False
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False


def play_alert() -> None:
    try:
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        for _ in range(2):
            winsound.Beep(880, 180)
            winsound.Beep(1175, 180)
    except RuntimeError:
        pass


class OverlayReminder(tk.Toplevel):
    """霸屏提醒窗口：置顶、全屏、强制确认。"""

    def __init__(
        self,
        master: tk.Tk,
        title: str,
        message: str,
        on_done: Callable[[], None],
        on_snooze: Callable[[int], None] | None = None,
        snooze_minutes: int = 5,
    ) -> None:
        super().__init__(master)
        self.on_done = on_done
        self.on_snooze = on_snooze
        self.snooze_minutes = snooze_minutes
        self._closing = False

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.configure(bg="#0B3D5C")
        self.update_idletasks()

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self.geometry(f"{sw}x{sh}+0+0")
        self.focus_force()
        self.grab_set()
        self.lift()

        # 拦截关闭，必须点按钮
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.bind("<Alt-F4>", lambda e: "break")
        self.bind("<Escape>", lambda e: "break")

        wrap = tk.Frame(self, bg="#0B3D5C")
        wrap.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            wrap,
            text="💧",
            font=("Segoe UI Emoji", 64),
            bg="#0B3D5C",
            fg="#7EC8E3",
        ).pack(pady=(0, 12))

        tk.Label(
            wrap,
            text=title or APP_TITLE,
            font=("Microsoft YaHei UI", 36, "bold"),
            bg="#0B3D5C",
            fg="#FFFFFF",
        ).pack()

        tk.Label(
            wrap,
            text=message,
            font=("Microsoft YaHei UI", 22),
            bg="#0B3D5C",
            fg="#C8E7F5",
            wraplength=min(900, sw - 80),
            justify="center",
        ).pack(pady=(18, 8))

        now = datetime.now().strftime("%H:%M")
        tk.Label(
            wrap,
            text=f"当前时间 {now}  ·  喝完再继续工作",
            font=("Microsoft YaHei UI", 14),
            bg="#0B3D5C",
            fg="#8BB8CC",
        ).pack(pady=(0, 36))

        btn_row = tk.Frame(wrap, bg="#0B3D5C")
        btn_row.pack()

        done_btn = tk.Button(
            btn_row,
            text="我喝了 ✓",
            font=("Microsoft YaHei UI", 18, "bold"),
            bg="#1FA2A6",
            fg="#FFFFFF",
            activebackground="#17878A",
            activeforeground="#FFFFFF",
            relief="flat",
            padx=36,
            pady=14,
            cursor="hand2",
            command=self._finish,
        )
        done_btn.pack(side="left", padx=10)

        if on_snooze is not None and snooze_minutes > 0:
            snooze_btn = tk.Button(
                btn_row,
                text=f"稍后提醒（{snooze_minutes} 分钟）",
                font=("Microsoft YaHei UI", 14),
                bg="#245B78",
                fg="#FFFFFF",
                activebackground="#1C4860",
                activeforeground="#FFFFFF",
                relief="flat",
                padx=20,
                pady=14,
                cursor="hand2",
                command=self._snooze,
            )
            snooze_btn.pack(side="left", padx=10)

        # 持续抢焦点，防止被其他窗口盖住
        self._keep_front()

    def _keep_front(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        try:
            self.lift()
            self.attributes("-topmost", True)
            self.focus_force()
        except tk.TclError:
            return
        self.after(800, self._keep_front)

    def _finish(self) -> None:
        self._closing = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        self.on_done()

    def _snooze(self) -> None:
        self._closing = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        if self.on_snooze:
            self.on_snooze(self.snooze_minutes)


class DrinkRemindApp:
    def __init__(self) -> None:
        self.cfg = load_config()
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("780x720")
        self.root.minsize(720, 640)
        self.root.configure(bg="#F4F8FB")

        self.overlay: OverlayReminder | None = None
        self._fired_keys: set[str] = set()
        self._snooze_until: datetime | None = None
        self._status_var = tk.StringVar(value="正在启动…")
        self._next_var = tk.StringVar(value="")
        self._enabled_var = tk.BooleanVar(value=bool(self.cfg.get("enabled", True)))
        self._weekday_var = tk.BooleanVar(value=bool(self.cfg.get("weekdays_only", True)))
        self._autostart_var = tk.BooleanVar(value=bool(self.cfg.get("auto_start", True)))
        self._sound_var = tk.BooleanVar(value=bool(self.cfg.get("sound", True)))
        self._snooze_var = tk.StringVar(value=str(self.cfg.get("snooze_minutes", 5)))

        self._build_ui()
        self._sync_autostart()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(500, self._tick)
        self._refresh_next()
        self._set_status("运行中 · 后台监听提醒计划")

    def _build_ui(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        header = tk.Frame(self.root, bg="#0B3D5C", height=72)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text="💧 喝水提醒",
            font=("Microsoft YaHei UI", 20, "bold"),
            bg="#0B3D5C",
            fg="#FFFFFF",
        ).pack(side="left", padx=20, pady=18)
        tk.Label(
            header,
            textvariable=self._status_var,
            font=("Microsoft YaHei UI", 11),
            bg="#0B3D5C",
            fg="#A8D4E8",
        ).pack(side="right", padx=20)

        body = tk.Frame(self.root, bg="#F4F8FB")
        body.pack(fill="both", expand=True, padx=18, pady=14)

        # 快捷操作
        actions = tk.LabelFrame(
            body,
            text="立即生效 / 快捷操作",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#F4F8FB",
            fg="#0B3D5C",
            padx=12,
            pady=10,
        )
        actions.pack(fill="x", pady=(0, 12))

        tk.Button(
            actions,
            text="测试霸屏提醒（立即生效）",
            font=("Microsoft YaHei UI", 12, "bold"),
            bg="#1FA2A6",
            fg="#FFFFFF",
            activebackground="#17878A",
            relief="flat",
            padx=16,
            pady=10,
            cursor="hand2",
            command=self.test_overlay,
        ).pack(side="left")

        tk.Button(
            actions,
            text="测试下一条计划内容",
            font=("Microsoft YaHei UI", 11),
            bg="#245B78",
            fg="#FFFFFF",
            activebackground="#1C4860",
            relief="flat",
            padx=12,
            pady=10,
            cursor="hand2",
            command=self.test_next_plan,
        ).pack(side="left", padx=(10, 0))

        tk.Label(
            actions,
            textvariable=self._next_var,
            font=("Microsoft YaHei UI", 10),
            bg="#F4F8FB",
            fg="#3A6B82",
        ).pack(side="right")

        # 开关
        switches = tk.LabelFrame(
            body,
            text="运行设置",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#F4F8FB",
            fg="#0B3D5C",
            padx=12,
            pady=8,
        )
        switches.pack(fill="x", pady=(0, 12))

        tk.Checkbutton(
            switches,
            text="启用定时提醒",
            variable=self._enabled_var,
            font=("Microsoft YaHei UI", 11),
            bg="#F4F8FB",
            activebackground="#F4F8FB",
            command=self._apply_switches,
        ).grid(row=0, column=0, sticky="w", padx=(0, 18), pady=4)

        tk.Checkbutton(
            switches,
            text="仅周一到周五",
            variable=self._weekday_var,
            font=("Microsoft YaHei UI", 11),
            bg="#F4F8FB",
            activebackground="#F4F8FB",
            command=self._apply_switches,
        ).grid(row=0, column=1, sticky="w", padx=(0, 18), pady=4)

        tk.Checkbutton(
            switches,
            text="开机自启动",
            variable=self._autostart_var,
            font=("Microsoft YaHei UI", 11),
            bg="#F4F8FB",
            activebackground="#F4F8FB",
            command=self._apply_switches,
        ).grid(row=0, column=2, sticky="w", padx=(0, 18), pady=4)

        tk.Checkbutton(
            switches,
            text="提醒时播放提示音",
            variable=self._sound_var,
            font=("Microsoft YaHei UI", 11),
            bg="#F4F8FB",
            activebackground="#F4F8FB",
            command=self._apply_switches,
        ).grid(row=1, column=0, sticky="w", pady=4)

        tk.Label(
            switches,
            text="稍后提醒（分钟）",
            font=("Microsoft YaHei UI", 11),
            bg="#F4F8FB",
        ).grid(row=1, column=1, sticky="e", pady=4)
        snooze_entry = ttk.Entry(switches, textvariable=self._snooze_var, width=6)
        snooze_entry.grid(row=1, column=2, sticky="w", pady=4)
        snooze_entry.bind("<FocusOut>", lambda e: self._apply_switches())

        # 底部编辑区先占位，避免被列表挤出屏幕
        tip = tk.Label(
            body,
            text="用法：选中列表一行 → 调「时/分」→「应用时间并保存」；新增请先填时间/内容再点「新增一条」。关闭窗口仅最小化。",
            font=("Microsoft YaHei UI", 9),
            bg="#F4F8FB",
            fg="#6A8796",
            anchor="w",
        )
        tip.pack(side="bottom", fill="x", pady=(6, 0))

        btns = tk.Frame(body, bg="#F4F8FB")
        btns.pack(side="bottom", fill="x", pady=(8, 0))
        for text, cmd, color in [
            ("新增一条", self.add_reminder, "#245B78"),
            ("更新选中内容", self.update_selected, "#245B78"),
            ("删除选中", self.delete_selected, "#245B78"),
            ("恢复默认计划", self.reset_plan, "#245B78"),
            ("保存全部设置", self.save_all, "#1FA2A6"),
            ("完全退出", self.quit_app, "#8B3A3A"),
        ]:
            tk.Button(
                btns,
                text=text,
                font=("Microsoft YaHei UI", 10),
                bg=color,
                fg="#FFFFFF",
                relief="flat",
                padx=12,
                pady=6,
                cursor="hand2",
                command=cmd,
            ).pack(side="left", padx=(0, 8))

        edit_box = tk.LabelFrame(
            body,
            text="▼ 在这里新增 / 编辑提醒（时、分可点箭头调整）",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#F4F8FB",
            fg="#0B3D5C",
            padx=12,
            pady=10,
        )
        edit_box.pack(side="bottom", fill="x", pady=(10, 0))

        self.edit_enabled = tk.BooleanVar(value=True)
        self.edit_hour = tk.StringVar(value="10")
        self.edit_minute = tk.StringVar(value="00")
        self.edit_title = tk.StringVar(value="喝水提醒")
        self.edit_message = tk.StringVar(value="半杯，约 275 毫升")
        self._time_preview = tk.StringVar(value="10:00")

        row1 = tk.Frame(edit_box, bg="#F4F8FB")
        row1.pack(fill="x")

        tk.Checkbutton(
            row1,
            text="启用这条",
            variable=self.edit_enabled,
            bg="#F4F8FB",
            font=("Microsoft YaHei UI", 11),
        ).pack(side="left")

        tk.Label(
            row1,
            text="提醒时间",
            bg="#F4F8FB",
            font=("Microsoft YaHei UI", 11, "bold"),
            fg="#0B3D5C",
        ).pack(side="left", padx=(16, 8))

        hour_spin = ttk.Spinbox(
            row1,
            from_=0,
            to=23,
            width=4,
            textvariable=self.edit_hour,
            format="%02.0f",
            command=self._sync_time_preview,
        )
        hour_spin.pack(side="left")
        hour_spin.bind("<KeyRelease>", lambda e: self._sync_time_preview())
        hour_spin.bind("<<Increment>>", lambda e: self.root.after(10, self._sync_time_preview))
        hour_spin.bind("<<Decrement>>", lambda e: self.root.after(10, self._sync_time_preview))

        tk.Label(row1, text="时", bg="#F4F8FB", font=("Microsoft YaHei UI", 11)).pack(side="left", padx=(4, 10))

        minute_spin = ttk.Spinbox(
            row1,
            from_=0,
            to=59,
            width=4,
            textvariable=self.edit_minute,
            format="%02.0f",
            command=self._sync_time_preview,
        )
        minute_spin.pack(side="left")
        minute_spin.bind("<KeyRelease>", lambda e: self._sync_time_preview())
        minute_spin.bind("<<Increment>>", lambda e: self.root.after(10, self._sync_time_preview))
        minute_spin.bind("<<Decrement>>", lambda e: self.root.after(10, self._sync_time_preview))

        tk.Label(row1, text="分", bg="#F4F8FB", font=("Microsoft YaHei UI", 11)).pack(side="left", padx=(4, 12))

        tk.Label(
            row1,
            textvariable=self._time_preview,
            font=("Microsoft YaHei UI", 16, "bold"),
            bg="#E8F4FA",
            fg="#0B3D5C",
            padx=12,
            pady=2,
        ).pack(side="left")

        tk.Button(
            row1,
            text="应用时间并保存",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#1FA2A6",
            fg="#FFFFFF",
            activebackground="#17878A",
            relief="flat",
            padx=14,
            pady=6,
            cursor="hand2",
            command=self.apply_time_and_save,
        ).pack(side="right")

        row2 = tk.Frame(edit_box, bg="#F4F8FB")
        row2.pack(fill="x", pady=(10, 0))
        tk.Label(row2, text="标题", bg="#F4F8FB", font=("Microsoft YaHei UI", 10)).pack(side="left")
        ttk.Entry(row2, textvariable=self.edit_title, width=14).pack(side="left", padx=(6, 12))
        tk.Label(row2, text="提醒内容", bg="#F4F8FB", font=("Microsoft YaHei UI", 10)).pack(side="left")
        ttk.Entry(row2, textvariable=self.edit_message).pack(side="left", fill="x", expand=True, padx=(6, 0))

        # 计划表占剩余空间
        plan = tk.LabelFrame(
            body,
            text="提醒计划列表（先点选一行，再到下方编辑）",
            font=("Microsoft YaHei UI", 11, "bold"),
            bg="#F4F8FB",
            fg="#0B3D5C",
            padx=8,
            pady=8,
        )
        plan.pack(fill="both", expand=True)

        cols = ("启用", "时间", "标题", "内容")
        self.tree = ttk.Treeview(plan, columns=cols, show="headings", height=5)
        self.tree.heading("启用", text="启用")
        self.tree.heading("时间", text="时间")
        self.tree.heading("标题", text="标题")
        self.tree.heading("内容", text="内容")
        self.tree.column("启用", width=60, anchor="center")
        self.tree.column("时间", width=80, anchor="center")
        self.tree.column("标题", width=120, anchor="w")
        self.tree.column("内容", width=360, anchor="w")
        self.tree.pack(fill="both", expand=True, side="left")

        scroll = ttk.Scrollbar(plan, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Double-1>", self._on_select)
        self._reload_tree()
        if self.tree.get_children():
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self.tree.focus(first)
            self._on_select()

    def _reload_tree(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for rem in self.cfg.get("reminders", []):
            self.tree.insert(
                "",
                "end",
                values=(
                    "是" if rem.get("enabled", True) else "否",
                    rem.get("time", ""),
                    rem.get("title", ""),
                    rem.get("message", ""),
                ),
            )

    def _on_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        self.edit_enabled.set(vals[0] == "是")
        parsed = self._parse_time(str(vals[1]))
        if parsed:
            self.edit_hour.set(f"{parsed[0]:02d}")
            self.edit_minute.set(f"{parsed[1]:02d}")
        self.edit_title.set(vals[2])
        self.edit_message.set(vals[3])
        self._sync_time_preview()

    def _parse_time(self, text: str) -> tuple[int, int] | None:
        text = text.strip()
        try:
            hh, mm = text.split(":")
            h, m = int(hh), int(mm)
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h, m
        except ValueError:
            return None
        return None

    def _read_edit_time(self) -> tuple[int, int] | None:
        try:
            h = int(str(self.edit_hour.get()).strip())
            m = int(str(self.edit_minute.get()).strip())
        except ValueError:
            return None
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
        return None

    def _sync_time_preview(self) -> None:
        t = self._read_edit_time()
        if t:
            self._time_preview.set(f"{t[0]:02d}:{t[1]:02d}")
        else:
            self._time_preview.set("--:--")

    def _current_edit_item(self) -> dict[str, Any] | None:
        t = self._read_edit_time()
        if not t:
            messagebox.showerror(APP_TITLE, "请用「时 / 分」设置有效时间（时 0-23，分 0-59）")
            return None
        return {
            "time": f"{t[0]:02d}:{t[1]:02d}",
            "title": self.edit_title.get().strip() or APP_TITLE,
            "message": self.edit_message.get().strip() or "该喝水了",
            "enabled": bool(self.edit_enabled.get()),
        }

    def add_reminder(self) -> None:
        item = self._current_edit_item()
        if not item:
            return
        self.cfg.setdefault("reminders", []).append(item)
        self._sort_reminders()
        self._reload_tree()
        self._refresh_next()
        self.save_all(quiet=True)

    def update_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(APP_TITLE, "请先选中一条提醒")
            return
        item = self._current_edit_item()
        if not item:
            return
        idx = self.tree.index(sel[0])
        self.cfg["reminders"][idx] = item
        self._sort_reminders()
        self._reload_tree()
        self._refresh_next()
        self.save_all(quiet=True)

    def apply_time_and_save(self) -> None:
        """一键：把时/分应用到选中项并立刻写入配置。"""
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo(APP_TITLE, "请先在上方列表选中一条提醒，再设置时间。")
            return
        item = self._current_edit_item()
        if not item:
            return
        idx = self.tree.index(sel[0])
        # 保持选中项位置：更新后按时间排序，再重新选中同一条内容
        self.cfg["reminders"][idx] = item
        self._sort_reminders()
        self._reload_tree()
        # 重新选中更新后的那条
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            if vals[1] == item["time"] and vals[3] == item["message"]:
                self.tree.selection_set(iid)
                self.tree.focus(iid)
                break
        self._refresh_next()
        self.save_all(quiet=True)
        messagebox.showinfo(APP_TITLE, f"已设置为 {item['time']}，立即生效。")

    def delete_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        del self.cfg["reminders"][idx]
        self._reload_tree()
        self._refresh_next()

    def reset_plan(self) -> None:
        if not messagebox.askyesno(APP_TITLE, "恢复默认周一到周五四次喝水计划？"):
            return
        self.cfg["reminders"] = json.loads(json.dumps(DEFAULT_CONFIG["reminders"]))
        self._reload_tree()
        self._refresh_next()
        self.save_all(quiet=True)
        if self.tree.get_children():
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self._on_select()

    def _sort_reminders(self) -> None:
        def key(r: dict[str, Any]) -> tuple[int, int]:
            parsed = self._parse_time(str(r.get("time", "00:00")))
            return parsed or (0, 0)

        self.cfg["reminders"] = sorted(self.cfg.get("reminders", []), key=key)

    def _apply_switches(self) -> None:
        self.cfg["enabled"] = bool(self._enabled_var.get())
        self.cfg["weekdays_only"] = bool(self._weekday_var.get())
        self.cfg["auto_start"] = bool(self._autostart_var.get())
        self.cfg["sound"] = bool(self._sound_var.get())
        try:
            self.cfg["snooze_minutes"] = max(1, int(self._snooze_var.get().strip() or "5"))
        except ValueError:
            self.cfg["snooze_minutes"] = 5
            self._snooze_var.set("5")
        self._sync_autostart()
        self._refresh_next()

    def _sync_autostart(self) -> None:
        want = bool(self.cfg.get("auto_start", True))
        try:
            set_auto_start(want)
            self._autostart_var.set(want)
        except OSError as exc:
            self._set_status(f"自启动设置失败：{exc}")

    def save_all(self, quiet: bool = False) -> None:
        self._apply_switches()
        save_config(self.cfg)
        self._fired_keys.clear()
        self._set_status("设置已保存 · 立即生效")
        self._refresh_next()
        if not quiet:
            messagebox.showinfo(APP_TITLE, "设置已保存，立即生效。")

    def test_overlay(self) -> None:
        self.show_overlay(
            title="测试提醒",
            message="这是立即生效的霸屏测试。\n确认后可继续使用。",
            is_test=True,
        )

    def test_next_plan(self) -> None:
        rem = self._next_reminder(include_today_past=True)
        if not rem:
            messagebox.showinfo(APP_TITLE, "当前没有可用提醒计划")
            return
        self.show_overlay(
            title=rem.get("title", APP_TITLE),
            message=rem.get("message", "该喝水了"),
            is_test=True,
        )

    def show_overlay(self, title: str, message: str, is_test: bool = False) -> None:
        if self.overlay is not None and self.overlay.winfo_exists():
            return
        if self.cfg.get("sound", True):
            threading.Thread(target=play_alert, daemon=True).start()

        snooze_minutes = int(self.cfg.get("snooze_minutes", 5) or 5)

        def on_done() -> None:
            self.overlay = None
            if not is_test:
                self._set_status("已确认喝水 · 继续监听")
            else:
                self._set_status("测试结束 · 继续监听")

        def on_snooze(minutes: int) -> None:
            self.overlay = None
            self._snooze_until = datetime.now() + timedelta(minutes=minutes)
            self._set_status(f"已延后 {minutes} 分钟再提醒")

        self.root.deiconify()
        self.root.lift()
        self.overlay = OverlayReminder(
            self.root,
            title=title,
            message=message,
            on_done=on_done,
            on_snooze=None if is_test else on_snooze,
            snooze_minutes=snooze_minutes,
        )

    def _set_status(self, text: str) -> None:
        self._status_var.set(text)

    def _is_workday(self, dt: datetime) -> bool:
        if not self.cfg.get("weekdays_only", True):
            return True
        return dt.weekday() < 5  # Mon-Fri

    def _fire_key(self, rem: dict[str, Any], dt: datetime) -> str:
        return f"{dt.date().isoformat()}|{rem.get('time')}|{rem.get('message')}"

    def _next_reminder(self, include_today_past: bool = False) -> dict[str, Any] | None:
        now = datetime.now()
        candidates: list[tuple[datetime, dict[str, Any]]] = []
        for rem in self.cfg.get("reminders", []):
            if not rem.get("enabled", True):
                continue
            parsed = self._parse_time(str(rem.get("time", "")))
            if not parsed:
                continue
            for day_offset in range(0, 8):
                day = now.date() + timedelta(days=day_offset)
                dt = datetime.combine(day, datetime.min.time()).replace(
                    hour=parsed[0], minute=parsed[1], second=0, microsecond=0
                )
                if not self._is_workday(dt):
                    continue
                if day_offset == 0 and dt <= now and not include_today_past:
                    continue
                candidates.append((dt, rem))
                break
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0])
        when, rem = candidates[0]
        self._next_var.set(f"下一次：{when.strftime('%m-%d %H:%M')}  {rem.get('message', '')}")
        return rem if include_today_past else rem

    def _refresh_next(self) -> None:
        rem = None
        now = datetime.now()
        best: datetime | None = None
        best_rem: dict[str, Any] | None = None
        for rem in self.cfg.get("reminders", []):
            if not rem.get("enabled", True):
                continue
            parsed = self._parse_time(str(rem.get("time", "")))
            if not parsed:
                continue
            for day_offset in range(0, 14):
                day = now.date() + timedelta(days=day_offset)
                dt = datetime.combine(day, datetime.min.time()).replace(
                    hour=parsed[0], minute=parsed[1], second=0, microsecond=0
                )
                if not self._is_workday(dt):
                    continue
                if dt <= now:
                    continue
                if best is None or dt < best:
                    best = dt
                    best_rem = rem
                break
        if best and best_rem:
            self._next_var.set(f"下一次：{best.strftime('%m-%d %H:%M')}  {best_rem.get('message', '')}")
        else:
            self._next_var.set("下一次：暂无可用计划")

    def _tick(self) -> None:
        try:
            self._check_schedule()
            self._refresh_next()
        finally:
            self.root.after(1000, self._tick)

    def _check_schedule(self) -> None:
        if not self.cfg.get("enabled", True):
            return
        if self.overlay is not None and self.overlay.winfo_exists():
            return
        now = datetime.now()
        if self._snooze_until and now < self._snooze_until:
            return
        if self._snooze_until and now >= self._snooze_until:
            # 延后到期：弹一次通用提醒
            self._snooze_until = None
            self.show_overlay(APP_TITLE, "延后提醒：该喝水了")
            return
        if not self._is_workday(now):
            return

        # 跨天后清理已触发记录
        today = now.date().isoformat()
        self._fired_keys = {k for k in self._fired_keys if k.startswith(today)}

        for rem in self.cfg.get("reminders", []):
            if not rem.get("enabled", True):
                continue
            parsed = self._parse_time(str(rem.get("time", "")))
            if not parsed:
                continue
            if now.hour == parsed[0] and now.minute == parsed[1]:
                key = self._fire_key(rem, now)
                if key in self._fired_keys:
                    continue
                self._fired_keys.add(key)
                self.show_overlay(
                    title=str(rem.get("title") or APP_TITLE),
                    message=str(rem.get("message") or "该喝水了"),
                )
                break

    def _on_close(self) -> None:
        # 最小化继续后台运行
        self.root.iconify()
        self._set_status("已最小化 · 后台继续提醒")

    def quit_app(self) -> None:
        if not messagebox.askyesno(APP_TITLE, "确定完全退出？退出后将不再提醒。"):
            return
        save_config(self.cfg)
        if self.overlay is not None and self.overlay.winfo_exists():
            try:
                self.overlay.destroy()
            except tk.TclError:
                pass
        self.root.destroy()

    def run(self) -> None:
        # 启动时确保配置落盘 & 自启动
        save_config(self.cfg)
        self._sync_autostart()
        self.root.mainloop()


def main() -> None:
    # 单实例：简单互斥锁文件
    lock = app_dir() / ".drink_remind.lock"
    if lock.exists():
        try:
            pid = int(lock.read_text(encoding="utf-8").strip() or "0")
            # Windows: 粗略检查进程是否存在
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
            if handle:
                kernel32.CloseHandle(handle)
                # 已有实例，尝试唤起较难，直接退出并提示
                root = tk.Tk()
                root.withdraw()
                messagebox.showinfo(APP_TITLE, "喝水提醒已在运行中。")
                root.destroy()
                return
        except (OSError, ValueError):
            pass
    lock.write_text(str(os.getpid()), encoding="utf-8")
    try:
        DrinkRemindApp().run()
    finally:
        try:
            if lock.exists():
                lock.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    main()
