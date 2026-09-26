"""Task list loaded from the backend GET /tasks, grouped by mission task."""
from __future__ import annotations

from typing import Any, Dict, List

import customtkinter as ctk

# One accent color per top-level mission task (1-4), cycled by group order.
_GROUP_COLORS = (
    "#9b59b6",  # Task 1 — purple
    "#1abc9c",  # Task 2 — teal
    "#e67e22",  # Task 3 — orange
    "#e84393",  # Task 4 — pink
)


class TaskMenuScreen(ctk.CTkFrame):
    """Shows tasks grouped under mission headers; app maps selection to task id."""

    def __init__(
        self,
        master: ctk.CTk | ctk.CTkFrame,
        tasks: List[Dict[str, Any]],
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self._tasks = tasks
        self._selected = 0
        self._labels: list[ctk.CTkLabel] = []

        ctk.CTkLabel(
            self,
            text="Select a task",
            font=ctk.CTkFont(size=20, weight="bold"),
        ).pack(pady=(16, 4))
        ctk.CTkLabel(
            self,
            text="Grouped by mission — pulled from the 2026 Explorer Class manual",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        ).pack(pady=(0, 8))

        body = ctk.CTkScrollableFrame(self, width=680, height=420)
        body.pack(fill="both", expand=True, padx=12, pady=8)

        last_group: str | None = None
        group_index = -1

        for t in tasks:
            group = t.get("group", "")
            if group != last_group:
                group_index += 1
                last_group = group
                color = _GROUP_COLORS[group_index % len(_GROUP_COLORS)]
                ctk.CTkLabel(
                    body,
                    text=group,
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color=color,
                    anchor="w",
                    justify="left",
                    wraplength=640,
                ).pack(fill="x", pady=(14, 4), padx=4)

            tid = t.get("id", "?")
            ttitle = t.get("title", "")
            points = t.get("points", "")
            venue = t.get("venue", "")
            line = f"  {tid}   {ttitle}"
            sub = f"        {points}" + (f"  ·  {venue}" if venue else "")

            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=2, padx=4)

            lb = ctk.CTkLabel(
                row,
                text=line,
                font=ctk.CTkFont(size=15),
                anchor="w",
                justify="left",
            )
            lb.pack(fill="x")
            sub_lb = ctk.CTkLabel(
                row,
                text=sub,
                font=ctk.CTkFont(size=11),
                text_color="gray",
                anchor="w",
                justify="left",
            )
            sub_lb.pack(fill="x")

            # Both the title and the subline highlight together as one entry.
            self._labels.append(lb)
            lb._sub_ref = sub_lb  # type: ignore[attr-defined]

        self._apply_highlight()

    @property
    def option_count(self) -> int:
        return max(1, len(self._tasks))

    def selection(self) -> int:
        return self._selected

    def set_selection(self, index: int) -> None:
        self._selected = max(0, min(self.option_count - 1, index))
        self._apply_highlight()

    def move(self, delta: int) -> None:
        self.set_selection(self._selected + delta)

    def selected_task_id(self) -> str:
        if not self._tasks:
            return ""
        return str(self._tasks[self._selected].get("id", ""))

    def _apply_highlight(self) -> None:
        for i, lb in enumerate(self._labels):
            sub_lb = getattr(lb, "_sub_ref", None)
            if i == self._selected:
                lb.configure(text_color=("#1f538d", "#5dade2"))
                if sub_lb is not None:
                    sub_lb.configure(text_color=("#1f538d", "#8fc4ea"))
            else:
                lb.configure(text_color=("gray20", "gray90"))
                if sub_lb is not None:
                    sub_lb.configure(text_color="gray")
