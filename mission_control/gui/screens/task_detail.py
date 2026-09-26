"""Task detail: full mission briefing (overview, procedure, scoring notes), plus actions."""
from __future__ import annotations

from typing import Any, Dict, List

import customtkinter as ctk

_WRAP = 620


class TaskDetailScreen(ctk.CTkFrame):
    """
    Displays one task in full: group/venue/points, overview, step-by-step
    procedure, scoring notes, and required images — then a fixed action menu.

    Task 1.1 also gets a selectable reconstruction action.
    """

    def __init__(
        self,
        master: ctk.CTk | ctk.CTkFrame,
        task: Dict[str, Any],
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._task = task
        self._selected = 0
        self._action_labels: list[ctk.CTkLabel] = []

        tid = task.get("id", "")
        self._actions = ["Upload images", "Send run_task command"]
        if tid == "1.1":
            self._actions.append("Run reconstruction")
        self._actions.append("Back")

        # --- fixed header -----------------------------------------------------
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(14, 4))

        group = task.get("group", "")
        if group:
            ctk.CTkLabel(
                header,
                text=group,
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color=("#1f538d", "#5dade2"),
                anchor="w",
                justify="left",
                wraplength=_WRAP,
            ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text=f"Task {tid} — {task.get('title', '')}",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
            justify="left",
            wraplength=_WRAP,
        ).pack(anchor="w", pady=(2, 0))

        badge_row = ctk.CTkFrame(header, fg_color="transparent")
        badge_row.pack(anchor="w", pady=(4, 0))
        points = task.get("points", "")
        venue = task.get("venue", "")
        if points:
            self._badge(badge_row, points, "#2ecc71")
        if venue:
            self._badge(badge_row, venue, "#7f8c8d")

        # --- scrollable body ----------------------------------------------------
        body = ctk.CTkScrollableFrame(self, width=640, height=340)
        body.pack(fill="both", expand=True, padx=16, pady=(8, 4))

        overview = task.get("overview", "")
        if overview:
            self._section_title(body, "Overview")
            ctk.CTkLabel(
                body,
                text=overview,
                font=ctk.CTkFont(size=13),
                wraplength=_WRAP,
                justify="left",
                anchor="w",
            ).pack(anchor="w", pady=(0, 10))

        procedure: List[str] = list(task.get("procedure") or task.get("instructions") or [])
        if procedure:
            self._section_title(body, "Task Logic")
            step_no = 0
            for line in procedure:
                # Lines ending in ":" are sub-headers (e.g. "PATH A — ...:")
                # rather than numbered steps, so they render without a number.
                if line.rstrip().endswith(":"):
                    ctk.CTkLabel(
                        body,
                        text=line,
                        font=ctk.CTkFont(size=13, weight="bold"),
                        wraplength=_WRAP,
                        justify="left",
                        anchor="w",
                    ).pack(anchor="w", pady=(8, 2))
                    continue
                step_no += 1
                ctk.CTkLabel(
                    body,
                    text=f"{step_no}.  {line}",
                    font=ctk.CTkFont(size=13),
                    wraplength=_WRAP,
                    justify="left",
                    anchor="w",
                ).pack(anchor="w", pady=2)

        scoring_notes: List[str] = list(task.get("scoring_notes") or [])
        if scoring_notes:
            self._section_title(body, "Scoring notes", top_pad=14)
            for line in scoring_notes:
                ctk.CTkLabel(
                    body,
                    text=f"•  {line}",
                    font=ctk.CTkFont(size=12),
                    wraplength=_WRAP,
                    justify="left",
                    anchor="w",
                ).pack(anchor="w", pady=2)

        req: List[str] = list(task.get("required_images") or [])
        if req:
            self._section_title(body, "Required images", top_pad=14)
            ctk.CTkLabel(
                body,
                text=", ".join(req),
                font=ctk.CTkFont(size=12),
                wraplength=_WRAP,
                justify="left",
                anchor="w",
            ).pack(anchor="w", pady=(0, 12))

        # --- fixed action menu ---------------------------------------------------
        ctk.CTkLabel(
            self,
            text="Actions",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(6, 2))

        action_row = ctk.CTkFrame(self, fg_color="transparent")
        action_row.pack(pady=(0, 10))
        for text in self._actions:
            lb = ctk.CTkLabel(action_row, text=text, font=ctk.CTkFont(size=15))
            lb.pack(side="left", padx=10)
            self._action_labels.append(lb)

        self._apply_highlight()

    @staticmethod
    def _section_title(parent, text: str, *, top_pad: int = 4) -> None:
        ctk.CTkLabel(
            parent,
            text=text,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", pady=(top_pad, 4))

    @staticmethod
    def _badge(parent, text: str, color: str) -> None:
        ctk.CTkLabel(
            parent,
            text=f"  {text}  ",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color=color,
            text_color="white",
            corner_radius=6,
        ).pack(side="left", padx=(0, 6))

    @property
    def option_count(self) -> int:
        return len(self._actions)

    def set_selection(self, index: int) -> None:
        self._selected = max(0, min(self.option_count - 1, index))
        self._apply_highlight()

    def move(self, delta: int) -> None:
        self.set_selection(self._selected + delta)

    def selected_action(self) -> str:
        return self._actions[self._selected]

    def task_id(self) -> str:
        return str(self._task.get("id", ""))

    def _apply_highlight(self) -> None:
        for i, lb in enumerate(self._action_labels):
            if i == self._selected:
                lb.configure(text_color=("#1f538d", "#5dade2"))
            else:
                lb.configure(text_color=("gray20", "gray80"))
