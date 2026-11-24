"""共用測試 fixture。

``_tk_常駐根視窗``（session級）：Tk9 在 macOS 上有個怪癖——同一 process 內
只要出現過「建構但從未 map 就被 destroy」的根視窗（test_theme_picker 的 per-test
fixture 就是如此：``ctk.CTk()`` 後直接 ``destroy()``、沒呼叫過 ``update``），
之後任何新建立的根視窗一 map（``update`` / ``update_idletasks``）就會在
Tk 的 ``showRootWindow`` 內 segfault。

解法：本 conftest 在整個測試 session 開頭就建立一個「立刻呼叫 ``update()`` 真正
map 起來」的常駐根視窗並保持存活，之後各測試檔再怎麼建立 / 銷毀根視窗都不會觸發
這個 bug。純邏輯測試不受影響。
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
def _tk_常駐根視窗():
    """建立並 map 一個常駐根視窗（見模組 docstring），session 結束才銷毀。"""
    import customtkinter as ctk

    keeper = ctk.CTk()
    keeper.update()  # 立刻 map，避開 Tk9 showRootWindow segfault
    yield keeper
    keeper.destroy()
