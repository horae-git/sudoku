"""棋盤畫面（票券 07：由 GameSession 驅動的完整遊戲流程）。

``BoardView``：左側 9×9 Canvas 棋盤（3×3 宮以粗線分隔，暫停時覆半透明遮罩）
+ 右側數字鍵盤、資訊面板（計時 mm:ss / 錯誤次數 / 剩餘提示）與按鈕列
（📝 筆記 / 💡 提示 / ↩ 返回上一步 / ⏸ 暫停 / 🏠 放棄回首頁）。

- 資料面完全交給 ``sudoku.session.GameSession``（BoardView 只讀狀態、呼叫動作）；
  自動存檔 / 勝利結算由 ``sudoku.ui.flow.GameFlow`` 包辦（每次動作與每秒 tick 存檔）；
- 點選格子選取；同行/列/宮與相同數字自動高亮（不同底色）；
- 滑鼠點右側 1–9 九宮格按鈕填入；填錯立即紅色顯示並計次；提示填入綠色鎖定；
- 筆記模式（📝 按鈕或 N 鍵）下數字鍵記 3×3 候選小字，填對自動清同單元筆記；
- 鍵盤：方向鍵移動、1–9 填入/筆記、Delete/Backspace 清除、Ctrl+Z 復原、Esc 暫停；
- 計時器每秒 ``flow.tick()``（暫停與完成時停止），完成即停止並寫入歷史。

純邏輯（格子外觀決策、高亮集合、筆記排版、時間格式化、遮罩旗標、模式標籤）
抽成 module-level 函式，供 pytest 在 headless 測試。
"""

import customtkinter as ctk

from sudoku.session import GameSession
from sudoku.themes import Theme, get_current_theme
from sudoku.ui.flow import GameFlow

CELL = 56  # 每格邊長（px）
BOARD = CELL * 9  # 棋盤總邊長
THIN = 1  # 一般格線寬（宮粗線寬讀色票 宮粗線寬）
NOTE_CELL = CELL / 3  # 筆記 3×3 小格邊長

# 暫停遮罩（深色 + gray50 網點 ≈ 半透明）
遮罩顏色 = "#101418"
遮罩網點 = "gray50"


def grid_line_spec(theme: Theme, index: int) -> tuple[str, int]:
    """第 ``index`` 條格線（0–10）的 (顏色, 線寬)：每 3 格的宮線用宮粗線色與宮粗線寬。

    深色主題的 ``宮粗線寬`` 較大、顏色較亮，宮分隔在深色下特別明顯（票券 09）。
    """
    if index % 3 == 0:
        return theme.宮粗線, theme.宮粗線寬
    return theme.格線, THIN


def format_mmss(seconds: int) -> str:
    """秒數格式化為 mm:ss（超過 60 分鐘時分鐘可超過 59）。"""
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def related_cells(selected: tuple[int, int] | None) -> set[tuple[int, int]]:
    """與選取格同行 / 同列 / 同宮的格子集合（含選取格本身）；未選取回傳空集合。"""
    if selected is None:
        return set()
    r, c = selected
    cells: set[tuple[int, int]] = {(r, cc) for cc in range(9)}
    cells.update((rr, c) for rr in range(9))
    br, bc = (r // 3) * 3, (c // 3) * 3
    for dr in range(3):
        for dc in range(3):
            cells.add((br + dr, bc + dc))
    return cells


def same_value_cells(session: GameSession) -> set[tuple[int, int]]:
    """盤面上與選取格數字相同的格子集合（選取格為空則回傳空集合）。"""
    sel = session.selected
    if sel is None:
        return set()
    r, c = sel
    value = session.board[r * 9 + c].value
    if value is None:
        return set()
    return {
        (i // 9, i % 9) for i in range(81) if session.board[i].value == value
    }


def cell_style(
    session: GameSession, theme: Theme, row: int, col: int
) -> tuple[str, str, bool]:
    """決定格子的 (底色, 文字色, 是否粗體)。

    底色優先序：選取 > 錯誤 > 提示 > 相同數字 > 同行列宮高亮 > 題示 > 普通。
    文字色優先序：錯誤紅 > 提示綠 > 選取文字 > 題示 > 填入 > 一般。
    粗體：題示或提示格（被選取時不粗體）。
    """
    cell = session.board[row * 9 + col]
    sel = session.selected == (row, col)
    error = cell.is_error
    hint = cell.is_hint
    given = cell.is_given
    if sel:
        bg = theme.格子選取底
    elif error:
        bg = theme.格子錯誤底
    elif hint:
        bg = theme.格子提示底
    elif (row, col) in same_value_cells(session):
        bg = theme.格子同數底
    elif (row, col) in related_cells(session.selected):
        bg = theme.格子高亮底
    elif given:
        bg = theme.格子題示底
    else:
        bg = theme.格子底
    if error:
        fg = theme.文字錯誤
    elif hint:
        fg = theme.文字提示
    elif sel:
        fg = theme.格子選取文字
    elif given:
        fg = theme.文字題示
    elif cell.value is not None:
        fg = theme.文字填入
    else:
        fg = theme.文字
    return bg, fg, (given or hint) and not sel


def notes_layout(notes: frozenset[int]) -> list[list[bool]]:
    """把一格的筆記候選數字排成 3×3 的布林表（r, c 位置是否有數字 r*3+c+1）。"""
    return [[(r * 3 + c + 1) in notes for c in range(3)] for r in range(3)]


def pause_overlay_visible(session: GameSession) -> bool:
    """暫停中時棋盤要畫遮罩（計時停止、動作被 session 擋）。"""
    return session.is_paused


def mode_display_label(mode: str, date: str | None = None) -> str:
    """模式轉畫面標籤；每日挑戰局顯示「📅 本日題目（日期）」。"""
    labels = {"easy": "簡單", "medium": "中等", "hard": "困難", "expert": "專家"}
    if mode == "daily":
        return f"📅 本日題目（{date}）" if date else "📅 每日挑戰"
    return labels.get(mode, mode)


class BoardView(ctk.CTkFrame):
    """棋盤畫面：Canvas 棋盤（+暫停遮罩）+ 數字鍵盤 + 資訊面板 + 按鈕列。

    由 ``GameSession`` 驅動資料面、``GameFlow`` 處理自動存檔與勝利 / 放棄結算。
    """

    def __init__(
        self,
        master: ctk.CTk,
        session: GameSession,
        mode_label: str = "",
        on_home=None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.theme: Theme = get_current_theme()  # 目前主題（storage 持久化）
        self.session = session
        self.flow = GameFlow(session)  # 建構即自動存檔
        self._on_home = on_home
        self._timer_id: str | None = None

        # ---------- 左側：棋盤 ----------
        board_wrap = ctk.CTkFrame(self, fg_color=self.theme.格線, corner_radius=self.theme.圓角)
        board_wrap.grid(row=0, column=0, padx=28, pady=24, sticky="n")
        self.canvas = ctk.CTkCanvas(
            board_wrap,
            width=BOARD,
            height=BOARD,
            bg=self.theme.格子底,
            highlightthickness=0,
        )
        self.canvas.pack(padx=self.theme.宮粗線寬, pady=self.theme.宮粗線寬)
        self.canvas.bind("<Button-1>", self._on_click)

        self._text_ids: list[list[int]] = [[0] * 9 for _ in range(9)]
        self._note_ids: list[list[list[int]]] = [
            [[0] * 9 for _ in range(9)] for _ in range(9)
        ]
        self._draw_grid()
        self._draw_pause_overlay()
        self._redraw_cells()

        # ---------- 右側：數字鍵盤 + 資訊面板 + 按鈕列 ----------
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, padx=(0, 28), pady=24, sticky="n")

        if mode_label:
            ctk.CTkLabel(
                right, text=mode_label, font=ctk.CTkFont(size=16, weight="bold"),
                text_color=self.theme.標題文字,
            ).pack(pady=(0, 10))

        # 數字鍵盤 3×3
        pad = ctk.CTkFrame(right, fg_color="transparent")
        pad.pack(pady=(0, 12))
        self._num_buttons: dict[int, ctk.CTkButton] = {}
        for n in range(1, 10):
            r, c = divmod(n - 1, 3)
            btn = ctk.CTkButton(
                pad, text=str(n), width=64, height=52, corner_radius=self.theme.圓角,
                font=ctk.CTkFont(size=22, weight="bold"),
                fg_color=self.theme.按鈕, hover_color=self.theme.按鈕懸停,
                text_color=self.theme.按鈕文字,
                command=lambda v=n: self._on_number(v),
            )
            btn.grid(row=r, column=c, padx=4, pady=4)
            self._num_buttons[n] = btn

        # 資訊面板：計時 / 錯誤次數 / 剩餘提示
        panel = ctk.CTkFrame(right, fg_color=self.theme.面板, corner_radius=self.theme.圓角)
        panel.pack(fill="x")
        self.time_var = ctk.StringVar(value=format_mmss(session.elapsed_sec))
        self.error_var = ctk.StringVar(value=str(session.mistakes))
        self.hints_var = ctk.StringVar(value=str(session.hints_left))
        ctk.CTkLabel(panel, text="計時", font=ctk.CTkFont(size=14),
                     text_color=self.theme.文字).pack(pady=(14, 0))
        ctk.CTkLabel(panel, textvariable=self.time_var,
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=self.theme.標題文字).pack(pady=(0, 8))
        ctk.CTkLabel(panel, text="錯誤次數", font=ctk.CTkFont(size=14),
                     text_color=self.theme.文字).pack()
        ctk.CTkLabel(panel, textvariable=self.error_var,
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=self.theme.文字錯誤).pack(pady=(0, 8))
        ctk.CTkLabel(panel, text="剩餘提示", font=ctk.CTkFont(size=14),
                     text_color=self.theme.文字).pack()
        ctk.CTkLabel(panel, textvariable=self.hints_var,
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=self.theme.文字提示).pack(pady=(0, 14))

        # 按鈕列：筆記 / 提示 / 返回上一步 / 暫停 / 放棄回首頁
        btns = ctk.CTkFrame(right, fg_color="transparent")
        btns.pack(pady=(14, 0))

        def 操作按鈕(text: str, command) -> ctk.CTkButton:
            return ctk.CTkButton(
                btns, text=text, width=180, height=40, corner_radius=self.theme.圓角,
                font=ctk.CTkFont(size=15, weight="bold"),
                fg_color=self.theme.按鈕, hover_color=self.theme.按鈕懸停,
                text_color=self.theme.按鈕文字,
                command=command,
            )

        self.note_btn = 操作按鈕("📝 筆記", self._on_toggle_note_mode)
        self.note_btn.pack(pady=4)
        操作按鈕("💡 提示", self._on_hint).pack(pady=4)
        操作按鈕("↩ 返回上一步", self._on_undo).pack(pady=4)
        self.pause_btn = 操作按鈕("⏸ 暫停", self._on_toggle_pause)
        self.pause_btn.pack(pady=4)
        操作按鈕("🏠 放棄回首頁", self._go_home).pack(pady=4)

        self._refresh_panel()

        # ---------- 鍵盤綁定（綁在根視窗，customtkinter 禁止對子 widget 用 bind_all） ----------
        root = self.winfo_toplevel()
        root.bind_all("<Up>", lambda e: self._on_arrow(-1, 0))
        root.bind_all("<Down>", lambda e: self._on_arrow(1, 0))
        root.bind_all("<Left>", lambda e: self._on_arrow(0, -1))
        root.bind_all("<Right>", lambda e: self._on_arrow(0, 1))
        for n in range(1, 10):
            root.bind_all(str(n), lambda e, v=n: self._on_number(v))
        root.bind_all("<Delete>", lambda e: self._on_clear())
        root.bind_all("<BackSpace>", lambda e: self._on_clear())
        root.bind_all("n", lambda e: self._on_toggle_note_mode())
        root.bind_all("N", lambda e: self._on_toggle_note_mode())
        root.bind_all("<Control-z>", lambda e: self._on_undo())
        root.bind_all("<Control-Z>", lambda e: self._on_undo())
        root.bind_all("<Escape>", lambda e: self._on_toggle_pause())

        self._start_timer()

    # ---------- 繪製 ----------

    def _draw_grid(self) -> None:
        """畫格線：一般細線 + 每 3 格的宮粗線（顏色與線寬讀自色票 grid_line_spec）。"""
        t = self.theme
        for i in range(10):
            color, w = grid_line_spec(t, i)
            x = i * CELL
            self.canvas.create_line(x, 0, x, BOARD, fill=color, width=w)
            self.canvas.create_line(0, x, BOARD, x, fill=color, width=w)
        # 格子主文字 + 筆記 3×3 小字（建立一次，之後只改內容與顏色 / 隱藏）
        for r in range(9):
            for c in range(9):
                x, y = c * CELL + CELL / 2, r * CELL + CELL / 2
                self._text_ids[r][c] = self.canvas.create_text(
                    x, y, text="", font=("Helvetica", 24, "bold"), fill=t.文字
                )
                for k in range(9):
                    nx = c * CELL + NOTE_CELL * (k % 3) + NOTE_CELL / 2
                    ny = r * CELL + NOTE_CELL * (k // 3) + NOTE_CELL / 2
                    self._note_ids[r][c][k] = self.canvas.create_text(
                        nx, ny, text="", font=("Helvetica", 10), fill=t.文字
                    )

    def _draw_pause_overlay(self) -> None:
        """暫停遮罩：覆蓋整個棋盤的半透明深色遮罩 + 置中大字「⏸ 已暫停」（預設隱藏）。"""
        self.canvas.create_rectangle(
            0, 0, BOARD, BOARD,
            fill=遮罩顏色, stipple=遮罩網點, outline="",
            tags="pause_overlay",
        )
        self.canvas.create_text(
            BOARD / 2, BOARD / 2, text="⏸ 已暫停",
            font=("Helvetica", 40, "bold"), fill="#FFFFFF",
            tags="pause_overlay",
        )
        self.canvas.itemconfigure("pause_overlay", state="hidden")

    def _redraw_cells(self) -> None:
        """依 session 目前狀態重繪所有格子底色、主文字與筆記小字。"""
        t = self.theme
        for r in range(9):
            for c in range(9):
                cell = self.session.board[r * 9 + c]
                bg, fg, bold = cell_style(self.session, t, r, c)
                # 底色：以格大小矩形鋪底（文字建立在其上）
                self.canvas.create_rectangle(
                    c * CELL + 1, r * CELL + 1, (c + 1) * CELL - 1, (r + 1) * CELL - 1,
                    fill=bg, outline="", tags=f"cell_{r}_{c}",
                )
                font = ("Helvetica", 24, "bold") if bold else ("Helvetica", 24)
                self.canvas.itemconfigure(
                    self._text_ids[r][c],
                    text=str(cell.value) if cell.value is not None else "",
                    fill=fg, font=font,
                )
                # 空格顯示 3×3 筆記小字；有值的格子清空筆記
                layout = notes_layout(cell.notes) if cell.value is None else notes_layout(frozenset())
                for k in range(9):
                    show = layout[k // 3][k % 3]
                    self.canvas.itemconfigure(
                        self._note_ids[r][c][k],
                        text=str(k + 1) if show else "",
                        fill=t.文字,
                    )
        # 把文字拉到最上層（遮罩層除外）
        for r in range(9):
            for c in range(9):
                self.canvas.tag_raise(self._text_ids[r][c])
                for k in range(9):
                    self.canvas.tag_raise(self._note_ids[r][c][k])
        # 暫停遮罩永遠在最上層
        self.canvas.tag_raise("pause_overlay")
        if pause_overlay_visible(self.session):
            self.canvas.itemconfigure("pause_overlay", state="normal")
        else:
            self.canvas.itemconfigure("pause_overlay", state="hidden")

    def _cell_at(self, x: int, y: int) -> tuple[int, int] | None:
        if not (0 <= x <= BOARD and 0 <= y <= BOARD):
            return None
        return y // CELL, x // CELL

    # ---------- 事件 ----------

    def _on_click(self, event) -> None:
        cell = self._cell_at(event.x, event.y)
        if cell is None:
            return
        self.session.select(*cell)
        self._redraw_cells()

    def _on_arrow(self, drow: int, dcol: int) -> str:
        r, c = self.session.selected if self.session.selected is not None else (0, 0)
        self.session.select(min(8, max(0, r + drow)), min(8, max(0, c + dcol)))
        self._redraw_cells()
        return "break"

    def _on_number(self, value: int) -> None:
        if self.session.note_mode:
            self.flow.toggle_note(value)
        else:
            self.flow.place(value)
        self._after_action()

    def _on_clear(self) -> str:
        self.flow.clear()
        self._after_action()
        return "break"

    def _on_toggle_note_mode(self) -> None:
        self.flow.toggle_note_mode()
        self._after_action()

    def _on_hint(self) -> None:
        self.flow.hint()
        self._after_action()

    def _on_undo(self) -> str | None:
        self.flow.undo()
        self._after_action()
        return "break"

    def _on_toggle_pause(self) -> str:
        self.flow.toggle_pause()
        self._redraw_cells()
        self._refresh_panel()
        return "break"

    def _after_action(self) -> None:
        """動作後：重繪棋盤、更新面板（計時/錯誤/提示/筆記按鈕狀態）。"""
        if self.session.is_won():
            self._stop_timer()
        self._redraw_cells()
        self._refresh_panel()

    def _refresh_panel(self) -> None:
        """依 session 狀態更新資訊面板與按鈕文字（計時 mm:ss / 錯誤 / 剩餘提示 / 筆記模式 / 暫停）。"""
        self.time_var.set(format_mmss(self.session.elapsed_sec))
        self.error_var.set(str(self.session.mistakes))
        self.hints_var.set(str(self.session.hints_left))
        if self.session.note_mode:
            self.note_btn.configure(text="📝 筆記中…", fg_color=self.theme.按鈕懸停)
        else:
            self.note_btn.configure(text="📝 筆記", fg_color=self.theme.按鈕)
        self.pause_btn.configure(text="▶ 繼續" if self.session.is_paused else "⏸ 暫停")

    def _go_home(self) -> None:
        """放棄本局（寫歷史為放棄、刪存檔）後回主選單。"""
        self._stop_timer()
        if not self.session.is_won():
            self.flow.abandon()
        root = self.winfo_toplevel()
        for seq in (
            ("<Up>", "<Down>", "<Left>", "<Right>", "<Delete>", "<BackSpace>",
             "n", "N", "<Control-z>", "<Control-Z>", "<Escape>")
            + tuple(str(n) for n in range(1, 10))
        ):
            root.unbind_all(seq)
        if self._on_home is not None:
            self._on_home()

    # ---------- 計時 ----------

    def _start_timer(self) -> None:
        self._timer_id = self.after(1000, self._tick)

    def _stop_timer(self) -> None:
        if self._timer_id is not None:
            self.after_cancel(self._timer_id)
            self._timer_id = None

    def _tick(self) -> None:
        """每秒：flow.tick() 计時並自動存檔（暫停時不計）；完成後停止計時器。"""
        if self.session.is_won():
            self._refresh_panel()
            self._stop_timer()
            return
        self.flow.tick()  # 暫停中時為 no-op（不計時、不寫檔）
        self._refresh_panel()
        self._timer_id = self.after(1000, self._tick)
