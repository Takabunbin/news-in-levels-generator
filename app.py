import ctypes

import customtkinter as ctk

from gui import NewsGeneratorApp


def main():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass

    root = ctk.CTk()
    app = NewsGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
