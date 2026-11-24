"""棋盤畫面（票券 06）。

``BoardView``：左側 9×9 Canvas 棋盤（3×3 宮以粗線分隔）+ 右側數字鍵盤與資訊面板。

- 點選格子選取；同行/列/宮與相同數字自動高亮（不同底色）；
- 滑鼠點右側 1–9 九宮格按鈕填入；填錯立即紅色顯示並計次；
- 鍵盤：方向鍵移動、1–9 填入、Delete/Backspace 清除；
- 右側資訊面板：計時（mm:ss）、錯誤次數、返回首頁按鈕。

純邏輯（格子外觀決策、時間格式化）抽成 module-level 函式，供 pytest 在 headless 測試；
對局資料面暫用 BoardState（票券 07 會改接 sudoku.session）。
"""

import customtkinter as ctk

from sudoku.generator import Difficulty
from sudoku.model import Puzzle, Solution
from sudoku.themes import Theme, get_theme
from sudoku.ui.board_state import BoardState

CELL = 56  # 每格邊長（px）
BOARD = CELL * 9  # 棋盤總邊長
THIN = 1  # 一般格線寬
THICK = 3  # 宮粗線寬


def format_mmss(seconds: int) -> str:
    """秒數格式化為 mm:ss（超過 60 分鐘時分鐘可超過 59）。"""
    seconds = max(0, int(seconds))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def cell_style(
    state: BoardState, theme: Theme, row: int, col: int
) -> tuple[str, str, bool]:
    """決定格子的 (底色, 文字色, 是否粗體)。

    底色優先序：選取 > 錯誤 > 相同數字 > 同行列宮高亮 > 題示 > 普通。
    文字色優先序：錯誤紅 > 選取文字 > 題示 > 填入 > 一般。
    """
    sel = state.selected == (row, col)
    error = state.is_error(row, col)
    given = state.is_given(row, col)
    if sel:
        bg = theme.格子選取底
    elif error:
        bg = theme.格子錯誤底
    elif (row, col) in state.same_value_cells():
        bg = theme.格子同數底
    elif (row, col) in state.related_cells():
        bg = theme.格子高亮底
    elif given:
        bg = theme.格子題示底
    else:
        bg = theme.格子底
    if error:
        fg = theme.文字錯誤
    elif sel:
        fg = theme.格子選取文字
    elif given:
        fg = theme.文字題示
    elif state.board[row][col] is not None:
        fg = theme.文字填入
    else:
        fg = theme.文字
    return bg, fg, given and not sel


class BoardView(ctk.CTkFrame):
    """棋盤畫面：Canvas 棋盤 + 數字鍵盤 + 資訊面板（計時/錯誤/返回首頁）。"""

    def __init__(
        self,
        master: ctk.CTk,
        puzzle: Puzzle,
        solution: Solution,
        mode_label: str = "",
        on_home=None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.theme: Theme = get_theme()
        self.state = BoardState(puzzle, solution)
        self._on_home = on_home
        self._elapsed = 0  # 秒
        self._timer_id: str | None = None

        # ---------- 左側：棋盤 ----------
        board_wrap = ctk.CTkFrame(self, fg_color=self.theme.格線, corner_radius=12)
        board_wrap.grid(row=0, column=0, padx=28, pady=24, sticky="n")
        self.canvas = ctk.CTkCanvas(
            board_wrap,
            width=BOARD,
            height=BOARD,
            bg=self.theme.格子底,
            highlightthickness=0,
        )
        self.canvas.pack(padx=THICK, pady=THICK)
        self.canvas.bind("<Button-1>", self._on_click)

        self._text_ids: list[list[int]] = [[0] * 9 for _ in range(9)]
        self._draw_grid()
        self._redraw_cells()

        # ---------- 右側：數字鍵盤 + 資訊面板 ----------
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, padx=(0, 28), pady=24, sticky="n")

        self.mode_var = ctk.StringVar(value=mode_label)
        if mode_label:
            ctk.CTkLabel(
                right, textvariable=self.mode_var, font=ctk.CTkFont(size=16, weight="bold"),
                text_color=self.theme.標題文字,
            ).pack(pady=(0, 10))

        # 數字鍵盤 3×3
        pad = ctk.CTkFrame(right, fg_color="transparent")
        pad.pack(pady=(0, 16))
        self._num_buttons: dict[int, ctk.CTkButton] = {}
        for n in range(1, 10):
            r, c = divmod(n - 1, 3)
            btn = ctk.CTkButton(
                pad, text=str(n), width=64, height=56, corner_radius=12,
                font=ctk.CTkFont(size=22, weight="bold"),
                fg_color=self.theme.按鈕, hover_color=self.theme.按鈕懸停,
                text_color=self.theme.按鈕文字,
                command=lambda v=n: self._on_number(v),
            )
            btn.grid(row=r, column=c, padx=4, pady=4)
            self._num_buttons[n] = btn

        # 資訊面板
        panel = ctk.CTkFrame(right, fg_color=self.theme.面板, corner_radius=12)
        panel.pack(fill="x")
        self.time_var = ctk.StringVar(value=format_mmss(0))
        self.error_var = ctk.StringVar(value="0")
        ctk.CTkLabel(panel, text="計時", font=ctk.CTkFont(size=14),
                     text_color=self.theme.文字).pack(pady=(14, 0))
        ctk.CTkLabel(panel, textvariable=self.time_var,
                     font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=self.theme.標題文字).pack(pady=(0, 8))
        ctk.CTkLabel(panel, text="錯誤次數", font=ctk.CTkFont(size=14),
                     text_color=self.theme.文字).pack()
        ctk.CTkLabel(panel, textvariable=self.error_var,
                     font=ctk.CTkFont(size=20, weight="bold"),
                     text_color=self.theme.文字錯誤).pack(pady=(0, 14))

        home_btn = ctk.CTkButton(
            right, text="🏠 返回首頁", width=180, height=44, corner_radius=12,
            font=ctk.CTkFont(size=16, weight="bold"),
            fg_color=self.theme.按鈕, hover_color=self.theme.按鈕懸停,
            text_color=self.theme.按鈕文字,
            command=self._go_home,
        )
        home_btn.pack(pady=(16, 0))

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

        self._start_timer()

    # ---------- 繪製 ----------

    def _draw_grid(self) -> None:
        """畫格線：一般細線 + 每 3 格的宮粗線（顏色讀自色票宮粗線）。"""
        t = self.theme
        for i in range(10):
            w = THICK if i % 3 == 0 else THIN
            color = t.宮粗線 if i % 3 == 0 else t.格線
            x = i * CELL
            self.canvas.create_line(x, 0, x, BOARD, fill=color, width=w)
            self.canvas.create_line(0, x, BOARD, x, fill=color, width=w)
        # 格子文字（建立一次，之後只改內容與顏色）
        for r in range(9):
            for c in range(9):
                x, y = c * CELL + CELL / 2, r * CELL + CELL / 2
                self._text_ids[r][c] = self.canvas.create_text(
                    x, y, text="", font=("Helvetica", 24, "bold"), fill=t.文字
                )

    def _redraw_cells(self) -> None:
        """依目前狀態重繪所有格子底色與文字（選取/高亮/錯誤/題示）。"""
        t = self.theme
        for r in range(9):
            for c in range(9):
                bg, fg, bold = cell_style(self.state, t, r, c)
                # 底色：以格大小矩形鋪底（文字建立在其上）
                self.canvas.create_rectangle(
                    c * CELL + 1, r * CELL + 1, (c + 1) * CELL - 1, (r + 1) * CELL - 1,
                    fill=bg, outline="", tags=f"cell_{r}_{c}",
                )
                value = self.state.board[r][c]
                font = ("Helvetica", 24, "bold") if bold else ("Helvetica", 24)
                self.canvas.itemconfigure(self._text_ids[r][c], text=str(value) if value else "", fill=fg, font=font)
        # 把文字拉到最上層
        for r in range(9):
            for c in range(9):
                self.canvas.tag_raise(self._text_ids[r][c])

    def _cell_at(self, x: int, y: int) -> tuple[int, int] | None:
        if not (0 <= x <= BOARD and 0 <= y <= BOARD):
            return None
        return y // CELL, x // CELL

    # ---------- 事件 ----------

    def _on_click(self, event) -> None:
        cell = self._cell_at(event.x, event.y)
        if cell is None:
            return
        self.state.select(*cell)
        self._redraw_cells()

    def _on_arrow(self, drow: int, dcol: int) -> str:
        self.state.move(drow, dcol)
        self._redraw_cells()
        return "break"

    def _on_number(self, value: int) -> None:
        if self.state.place(value):
            self.error_var.set(str(self.state.mistakes))
            self._redraw_cells()

    def _on_clear(self) -> str:
        if self.state.clear():
            self._redraw_cells()
        return "break"

    def _go_home(self) -> None:
        self._stop_timer()
        root = self.winfo_toplevel()
        for seq in ("<Up>", "<Down>", "<Left>", "<Right>", "<Delete>", "<BackSpace>") + tuple(str(n) for n in range(1, 10)):
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
        if self.state.completed:
            self._stop_timer()
            return
        self._elapsed += 1
        self.time_var.set(format_mmss(self._elapsed))
        self._timer_id = self.after(1000, self._tick)


def difficulty_mode_label(difficulty: Difficulty) -> str:
    """難度轉畫面標籤（本日題目等模式標示用）。"""
    return {
        Difficulty.EASY: "簡單",
        Difficulty.MEDIUM: "中等",
        Difficulty.HARD: "困難",
        Difficulty.EXPERT: "專家",
    }[difficulty]
