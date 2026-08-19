"""
Context menu and universal clipboard handlers for Tkinter/CustomTkinter entry fields.
Supports Ctrl+V/C/A/X across all keyboard layouts (Russian/English) and Right-Click menu.
"""
import tkinter as tk
import customtkinter as ctk
from ui.styles import COLORS, FONT_FAMILY


def attach_context_menu(entry_widget: ctk.CTkEntry):
    """
    Attaches right-click context menu and universal clipboard shortcuts
    (works with Russian and English keyboard layouts) to a CTkEntry widget.
    """
    inner_entry = entry_widget._entry

    menu = tk.Menu(inner_entry, tearoff=0, bg="#282834", fg="#FFFFFF", activebackground="#6366F1", activeforeground="#FFFFFF", font=(FONT_FAMILY, 10))
    
    def do_paste():
        try:
            text = inner_entry.clipboard_get()
            # If text is selected, replace it
            try:
                inner_entry.delete("sel.first", "sel.last")
            except Exception:
                pass
            inner_entry.insert("insert", text)
        except Exception:
            pass

    def do_copy():
        try:
            text = inner_entry.selection_get()
            inner_entry.clipboard_clear()
            inner_entry.clipboard_append(text)
        except Exception:
            pass

    def do_cut():
        try:
            do_copy()
            inner_entry.delete("sel.first", "sel.last")
        except Exception:
            pass

    def do_select_all():
        inner_entry.select_range(0, "end")
        inner_entry.icursor("end")

    menu.add_command(label="📋 Вставить", command=do_paste)
    menu.add_command(label="📄 Копировать", command=do_copy)
    menu.add_command(label="✂ Вырезать", command=do_cut)
    menu.add_separator()
    menu.add_command(label="🔲 Выделить всё", command=do_select_all)

    def show_menu(event):
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # Bind right-click
    inner_entry.bind("<Button-3>", show_menu)
    entry_widget.bind("<Button-3>", show_menu)

    # Universal KeyPress bindings for Ctrl+V, Ctrl+C, Ctrl+A, Ctrl+X on ANY keyboard layout
    def on_control_key(event):
        # Check if Ctrl modifier is pressed (state & 4 or state & 0x0004)
        if event.state & 4 or event.state & 0x0004 or event.state & 0x20000:
            keycode = event.keycode
            # Keycodes on Windows:
            # 86 = V / М
            # 67 = C / С
            # 65 = A / Ф
            # 88 = X / Ч
            if keycode == 86:  # Ctrl+V
                do_paste()
                return "break"
            elif keycode == 67:  # Ctrl+C
                do_copy()
                return "break"
            elif keycode == 65:  # Ctrl+A
                do_select_all()
                return "break"
            elif keycode == 88:  # Ctrl+X
                do_cut()
                return "break"

    inner_entry.bind("<KeyPress>", on_control_key)
