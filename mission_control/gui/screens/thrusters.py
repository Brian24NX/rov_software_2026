"""Thruster control: arm / disarm gamepad control of the ROV."""
from __future__ import annotations

import customtkinter as ctk


class ThrusterScreen(ctk.CTkFrame):
    ACTIONS = ("Stop thrusters", "Arm thrusters", "Back")

    def __init__(self, master: ctk.CTk | ctk.CTkFrame, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self._selected = 0
        self._labels: list[ctk.CTkLabel] = []

        ctk.CTkLabel(
            self,
            text="Thruster Control",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(16, 4))

        ctk.CTkLabel(
            self,
            text=(
                "The thrusters ignore the gamepad until you run them here.\n"
                "Release all driving controls before arming.\n"
                "While armed, use keyboard Esc or View/Back to stop."
            ),
            font=ctk.CTkFont(size=13),
            text_color="gray",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 12))

        self._status = ctk.CTkLabel(
            self,
            text="Vehicle state: waiting for acknowledgment",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self._status.pack(anchor="w", padx=16, pady=(0, 16))

        ctk.CTkLabel(
            self,
            text=(
                "⚠  Running the thrusters moves the ROV. Check the props are "
                "clear before arming."
            ),
            font=ctk.CTkFont(size=12),
            text_color=("#b9770e", "#f0b27a"),
            wraplength=520,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 16))

        for text in self.ACTIONS:
            lb = ctk.CTkLabel(self, text=text, font=ctk.CTkFont(size=17))
            lb.pack(pady=8)
            self._labels.append(lb)

        self._apply_highlight()

    @property
    def option_count(self) -> int:
        return len(self.ACTIONS)

    def set_selection(self, index: int) -> None:
        self._selected = max(0, min(self.option_count - 1, index))
        self._apply_highlight()

    def move(self, delta: int) -> None:
        self.set_selection(self._selected + delta)

    def selected_action(self) -> str:
        return self.ACTIONS[self._selected]

    def set_status(self, running: bool | None, detail: str = "") -> None:
        if running is None:
            self._status.configure(
                text=f"Vehicle state unknown: {detail}",
                text_color=("#c0392b", "#e74c3c"),
            )
            return
        state = "ARMED" if running else "DISARMED"
        colour = ("#b9770e", "#f5b041") if running else ("#1e8449", "#2ecc71")
        self._status.configure(text=f"Vehicle: {state} — {detail}", text_color=colour)

    def _apply_highlight(self) -> None:
        for i, lb in enumerate(self._labels):
            if i == self._selected:
                lb.configure(text_color=("#1f538d", "#5dade2"))
            else:
                lb.configure(text_color=("gray20", "gray80"))
