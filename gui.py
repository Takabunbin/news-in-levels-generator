import ctypes
import os
import threading
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from cache_manager import load_articles_cache, save_articles_cache
from config_manager import (
    DEFAULT_OUTPUT_DIR,
    load_fetch_pages,
    load_language,
    load_output_dir,
    load_window_size,
    save_fetch_pages,
    save_language,
    save_output_dir,
    save_window_size,
)
from scraper import get_recent_articles
from translations import LANGUAGES, TRANSLATIONS
from word_generator import generate_articles, get_article_preview, is_article_generated

UI_FONT = "Microsoft YaHei"
FONT_TITLE = (UI_FONT, 24, "bold")
FONT_SECTION = (UI_FONT, 13, "bold")
FONT_NORMAL = (UI_FONT, 12)
FONT_SMALL = (UI_FONT, 11)
FONT_TINY = (UI_FONT, 10)
FONT_HEADER = (UI_FONT, 12, "bold")
WINDOW_SIZE_PRESETS = {
    "Compact": (1100, 750),
    "Standard": (1280, 850),
    "Large": (1440, 900),
    "Wide": (1600, 900),
    "Maximized": (1280, 850),
    "Custom": (1280, 850),
}


class NewsGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        self.root.minsize(1000, 700)
        self.root.maxsize(self.screen_width, self.screen_height)
        mode, width, height = load_window_size()
        width, height = self.clamp_window_size(width, height)
        if mode == "Maximized":
            self.root.state("zoomed")
        else:
            self.root.geometry(f"{width}x{height}")

        self.articles = []
        self.visible_articles = []
        self.row_vars = []
        self.status_labels = []
        self.only_show_ungenerated = ctk.BooleanVar(value=False)
        self.fetch_pages = ctk.StringVar(value=str(load_fetch_pages()))
        self.language = ctk.StringVar(value=load_language())
        self.output_dir = ctk.StringVar(value=str(load_output_dir()))
        self.status_text = ctk.StringVar(value=self.tr("ready"))
        self.ui_text = {}
        self.settings_window = None

        self.configure_style()
        self.build_layout()
        self.root.title(self.tr("app_title"))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        cached_articles = load_articles_cache()
        if cached_articles:
            self.show_articles(cached_articles)

    def clamp_window_size(self, width, height):
        width = min(max(1000, int(width)), self.screen_width)
        height = min(max(700, int(height)), self.screen_height)
        return width, height

    def tr(self, key, **kwargs):
        text = TRANSLATIONS[self.language.get()].get(key, key)
        return text.format(**kwargs) if kwargs else text

    def configure_style(self):
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        ctk.set_widget_scaling(1.0)
        ctk.set_window_scaling(1.0)

    def build_layout(self):
        self.root.configure(fg_color="#f4f6f8")

        root_frame = ctk.CTkFrame(self.root, fg_color="#f4f6f8", corner_radius=0)
        root_frame.pack(fill="both", expand=True, padx=22, pady=(20, 0))
        root_frame.grid_columnconfigure(0, weight=1)
        root_frame.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(root_frame, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 16))
        self.ui_text["app_title"] = ctk.CTkLabel(
            header,
            text=self.tr("app_title"),
            font=FONT_TITLE,
            text_color="#1f2937",
        )
        self.ui_text["app_title"].pack(anchor="w")
        self.ui_text["app_subtitle"] = ctk.CTkLabel(
            header,
            text=self.tr("app_subtitle"),
            font=FONT_SECTION,
            text_color="#667085",
        )
        self.ui_text["app_subtitle"].pack(anchor="w", pady=(4, 0))

        content = ctk.CTkFrame(root_frame, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)

        list_card = self.section_card(content, "articles")
        list_card.grid(row=0, column=0, sticky="nsew", pady=(0, 14))
        list_card.grid_columnconfigure(0, weight=1)
        list_card.grid_rowconfigure(1, weight=1)

        header_row = ctk.CTkFrame(list_card, fg_color="#eef2f6", corner_radius=8, height=34)
        header_row.grid(row=0, column=0, sticky="ew", padx=14, pady=(0, 8))
        header_row.grid_columnconfigure(0, minsize=70)
        header_row.grid_columnconfigure(1, minsize=108)
        header_row.grid_columnconfigure(2, weight=2)
        header_row.grid_columnconfigure(3, weight=3)
        header_row.grid_columnconfigure(4, minsize=120)

        for column, key in enumerate(["select", "date", "title", "url", "status"]):
            label = ctk.CTkLabel(
                header_row,
                text=self.tr(key),
                font=FONT_HEADER,
                text_color="#344054",
                anchor="w",
            )
            label.grid(row=0, column=column, sticky="ew", padx=(12 if column == 0 else 8, 8), pady=7)
            self.ui_text[f"header_{key}"] = label

        self.article_list = ctk.CTkScrollableFrame(
            list_card,
            fg_color="#ffffff",
            border_width=1,
            border_color="#e5e7eb",
            corner_radius=10,
        )
        self.article_list.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 2))
        self.article_list.grid_columnconfigure(0, minsize=70)
        self.article_list.grid_columnconfigure(1, minsize=108)
        self.article_list.grid_columnconfigure(2, weight=2)
        self.article_list.grid_columnconfigure(3, weight=3)
        self.article_list.grid_columnconfigure(4, minsize=120)

        preview_card = self.section_card(content, "preview")
        preview_card.grid(row=1, column=0, sticky="ew", pady=(0, 14))
        preview_card.grid_columnconfigure(0, weight=1)

        self.preview_text = ctk.CTkTextbox(
            preview_card,
            height=110,
            font=FONT_SMALL,
            fg_color="#ffffff",
            border_width=1,
            border_color="#e5e7eb",
            text_color="#1f2937",
            wrap="word",
        )
        self.preview_text.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 2))
        self.preview_text.insert("1.0", self.tr("preview_empty"))
        self.preview_text.configure(state="disabled")

        path_card = self.section_card(content, "save_location")
        path_card.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        path_card.grid_columnconfigure(0, weight=1)

        self.path_entry = ctk.CTkEntry(
            path_card,
            textvariable=self.output_dir,
            state="readonly",
            font=FONT_NORMAL,
            height=38,
            fg_color="#ffffff",
            border_color="#d0d5dd",
            text_color="#344054",
        )
        self.path_entry.grid(row=0, column=0, sticky="ew", padx=(14, 10), pady=(0, 2))
        self.ui_text["choose_folder_top"] = ctk.CTkButton(
            path_card,
            text=self.tr("choose_folder"),
            command=self.choose_output_dir,
            height=38,
            font=FONT_NORMAL,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
        )
        self.ui_text["choose_folder_top"].grid(row=0, column=1, padx=(0, 14), pady=(0, 2))
        path_card.grid_remove()

        action_card = self.section_card(content, "actions")
        action_card.grid(row=3, column=0, sticky="ew", pady=(0, 12))
        for column in range(6):
            action_card.grid_columnconfigure(column, weight=1)

        fetch_frame = ctk.CTkFrame(action_card, fg_color="transparent")
        fetch_frame.grid(row=0, column=0, columnspan=6, sticky="w", padx=14, pady=(0, 10))
        self.ui_text["fetch_pages"] = ctk.CTkLabel(
            fetch_frame,
            text=self.tr("fetch_pages"),
            font=FONT_NORMAL,
            text_color="#344054",
        )
        self.ui_text["fetch_pages"].pack(side="left", padx=(0, 8))
        ctk.CTkEntry(
            fetch_frame,
            textvariable=self.fetch_pages,
            width=70,
            height=34,
            font=FONT_NORMAL,
            fg_color="#ffffff",
            border_color="#d0d5dd",
        ).pack(side="left")
        self.ui_text["language_label"] = ctk.CTkLabel(
            fetch_frame,
            text=self.tr("language"),
            font=FONT_NORMAL,
            text_color="#344054",
        )
        self.ui_text["language_label"].pack(side="left", padx=(18, 8))
        self.language_menu = ctk.CTkOptionMenu(
            fetch_frame,
            values=["English", "涓枃"],
            variable=self.language,
            command=self.change_language,
            width=110,
            height=34,
            font=FONT_NORMAL,
            dropdown_font=FONT_NORMAL,
        )
        self.language_menu.pack(side="left")
        fetch_frame.grid_remove()

        buttons = [
            ("refresh_list", self.refresh_articles, "#2563eb", "#1d4ed8"),
            ("select_all", self.select_all, "#475467", "#344054"),
            ("clear_selection", self.clear_all, "#475467", "#344054"),
            ("generate_selected", self.generate_selected, "#0f766e", "#115e59"),
            ("generate_today", self.generate_today, "#0f766e", "#115e59"),
            ("open_folder", self.open_output_dir, "#475467", "#344054"),
            ("settings", self.open_settings, "#475467", "#344054"),
        ]
        for index, (key, command, color, hover) in enumerate(buttons):
            button = ctk.CTkButton(
                action_card,
                text=self.tr(key),
                command=command,
                height=40,
                font=FONT_NORMAL,
                fg_color=color,
                hover_color=hover,
            )
            button.grid(row=1, column=index, sticky="ew", padx=(14 if index == 0 else 5, 14 if index == 5 else 5), pady=(0, 2))
            self.ui_text[key] = button

        self.only_ungenerated_checkbox = ctk.CTkCheckBox(
            action_card,
            text=self.tr("only_show_ungenerated"),
            variable=self.only_show_ungenerated,
            command=self.render_article_rows,
            font=FONT_NORMAL,
        )
        self.only_ungenerated_checkbox.grid(row=2, column=0, columnspan=2, sticky="w", padx=14, pady=(10, 0))
        self.ui_text["only_show_ungenerated"] = self.only_ungenerated_checkbox

        status_bar = ctk.CTkFrame(self.root, fg_color="#e9edf2", corner_radius=0, height=34)
        status_bar.pack(fill="x", side="bottom")
        ctk.CTkLabel(
            status_bar,
            textvariable=self.status_text,
            font=FONT_SMALL,
            text_color="#475467",
            anchor="w",
        ).pack(fill="x", padx=16, pady=7)

    def section_card(self, parent, title):
        card = ctk.CTkFrame(parent, fg_color="#ffffff", corner_radius=14, border_width=1, border_color="#e5e7eb")
        label = ctk.CTkLabel(
            card,
            text=self.tr(title),
            font=FONT_SECTION,
            text_color="#1f2937",
            anchor="w",
        )
        label.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 10))
        self.ui_text[f"section_{title}"] = label
        return card

    def open_settings(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.focus()
            return

        self.settings_window = ctk.CTkToplevel(self.root)
        self.settings_window.title(self.tr("settings_title"))
        self.settings_window.geometry("520x360")
        self.settings_window.resizable(False, False)
        self.settings_window.transient(self.root)

        frame = ctk.CTkFrame(self.settings_window, fg_color="#f4f6f8", corner_radius=0)
        frame.pack(fill="both", expand=True, padx=18, pady=18)
        frame.grid_columnconfigure(1, weight=1)

        folder_var = ctk.StringVar(value=self.output_dir.get())
        pages_var = ctk.StringVar(value=self.fetch_pages.get())
        language_var = ctk.StringVar(value=self.language.get())
        mode, width, height = load_window_size()
        width, height = self.clamp_window_size(width, height)
        mode_var = ctk.StringVar(value=mode if mode in WINDOW_SIZE_PRESETS else "Standard")
        width_var = ctk.StringVar(value=str(width))
        height_var = ctk.StringVar(value=str(height))

        ctk.CTkLabel(frame, text=self.tr("default_save_folder"), font=FONT_NORMAL, anchor="w").grid(row=0, column=0, sticky="w", pady=(0, 10), padx=(0, 10))
        folder_entry = ctk.CTkEntry(frame, textvariable=folder_var, font=FONT_NORMAL, height=36)
        folder_entry.grid(row=0, column=1, sticky="ew", pady=(0, 10), padx=(0, 8))
        ctk.CTkButton(
            frame,
            text=self.tr("choose_folder"),
            font=FONT_NORMAL,
            height=36,
            command=lambda: self.choose_settings_folder(folder_var),
        ).grid(row=0, column=2, sticky="ew", pady=(0, 10))

        ctk.CTkLabel(frame, text=self.tr("fetch_pages"), font=FONT_NORMAL, anchor="w").grid(row=1, column=0, sticky="w", pady=(0, 10), padx=(0, 10))
        ctk.CTkEntry(frame, textvariable=pages_var, font=FONT_NORMAL, height=36, width=100).grid(row=1, column=1, sticky="w", pady=(0, 10))

        ctk.CTkLabel(frame, text=self.tr("language"), font=FONT_NORMAL, anchor="w").grid(row=2, column=0, sticky="w", pady=(0, 10), padx=(0, 10))
        ctk.CTkOptionMenu(
            frame,
            values=["English", "\u4e2d\u6587"],
            variable=language_var,
            font=FONT_NORMAL,
            dropdown_font=FONT_NORMAL,
            height=36,
            width=140,
        ).grid(row=2, column=1, sticky="w", pady=(0, 10))

        ctk.CTkLabel(frame, text=self.tr("window_size"), font=FONT_NORMAL, anchor="w").grid(row=3, column=0, sticky="w", pady=(0, 10), padx=(0, 10))
        size_frame = ctk.CTkFrame(frame, fg_color="transparent")
        size_frame.grid(row=3, column=1, sticky="w", pady=(0, 10))
        ctk.CTkOptionMenu(
            size_frame,
            values=list(WINDOW_SIZE_PRESETS),
            variable=mode_var,
            command=lambda value: self.apply_window_size_preset(value, width_var, height_var),
            font=FONT_NORMAL,
            dropdown_font=FONT_NORMAL,
            width=120,
            height=36,
        ).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(size_frame, text=self.tr("width"), font=FONT_SMALL).pack(side="left", padx=(0, 6))
        ctk.CTkEntry(size_frame, textvariable=width_var, font=FONT_NORMAL, width=80, height=36).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(size_frame, text=self.tr("height"), font=FONT_SMALL).pack(side="left", padx=(0, 6))
        ctk.CTkEntry(size_frame, textvariable=height_var, font=FONT_NORMAL, width=80, height=36).pack(side="left")

        button_frame = ctk.CTkFrame(frame, fg_color="transparent")
        button_frame.grid(row=4, column=0, columnspan=3, sticky="e", pady=(18, 0))
        ctk.CTkButton(
            button_frame,
            text=self.tr("cancel"),
            font=FONT_NORMAL,
            fg_color="#475467",
            hover_color="#344054",
            command=self.settings_window.destroy,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            button_frame,
            text=self.tr("save_settings"),
            font=FONT_NORMAL,
            command=lambda: self.save_settings(folder_var, pages_var, language_var, mode_var, width_var, height_var),
        ).pack(side="left")

    def choose_settings_folder(self, folder_var):
        folder = filedialog.askdirectory(initialdir=folder_var.get() or str(DEFAULT_OUTPUT_DIR))
        if folder:
            folder_var.set(folder)

    def apply_window_size_preset(self, value, width_var, height_var):
        if value == "Custom":
            return
        width, height = self.clamp_window_size(*WINDOW_SIZE_PRESETS[value])
        width_var.set(width)
        height_var.set(height)

    def save_settings(self, folder_var, pages_var, language_var, mode_var, width_var, height_var):
        try:
            pages = int(pages_var.get())
            width = int(width_var.get())
            height = int(height_var.get())
        except ValueError:
            messagebox.showinfo(self.tr("notice"), self.tr("invalid_window_size"))
            return

        if pages < 1:
            messagebox.showinfo(self.tr("notice"), self.tr("fetch_min"))
            return
        mode = mode_var.get()
        width, height = self.clamp_window_size(width, height)

        output_dir = Path(folder_var.get())
        output_dir.mkdir(exist_ok=True)

        save_output_dir(output_dir)
        save_fetch_pages(pages)
        save_language(language_var.get())
        save_window_size(mode, width, height)

        self.output_dir.set(str(output_dir))
        self.fetch_pages.set(str(pages))
        self.language.set(language_var.get())
        if mode == "Maximized":
            self.root.state("zoomed")
        else:
            self.root.state("normal")
            self.root.geometry(f"{width}x{height}")
        self.update_texts()
        self.update_generated_statuses()
        self.set_status(self.tr("settings_saved"))

        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.destroy()

    def change_language(self, language):
        save_language(language)
        self.update_texts()
        self.set_status(self.tr("ready"))

    def update_texts(self):
        direct_keys = [
            "app_title",
            "app_subtitle",
            "fetch_pages",
            "refresh_list",
            "select_all",
            "clear_selection",
            "choose_folder",
            "generate_selected",
            "generate_today",
            "open_folder",
            "settings",
            "only_show_ungenerated",
        ]
        for key in direct_keys:
            if key in self.ui_text:
                self.ui_text[key].configure(text=self.tr(key))

        self.root.title(self.tr("app_title"))
        self.ui_text["language_label"].configure(text=self.tr("language"))
        self.ui_text["choose_folder_top"].configure(text=self.tr("choose_folder"))

        for key in ["articles", "preview", "save_location", "actions"]:
            widget_key = f"section_{key}"
            if widget_key in self.ui_text:
                self.ui_text[widget_key].configure(text=self.tr(key))

        for key in ["select", "date", "title", "url", "status"]:
            widget_key = f"header_{key}"
            if widget_key in self.ui_text:
                self.ui_text[widget_key].configure(text=self.tr(key))

        if self.preview_text.get("1.0", "end").strip() in [
            TRANSLATIONS["English"]["preview_empty"],
            TRANSLATIONS["涓枃"]["preview_empty"],
        ]:
            self.set_preview_text(self.tr("preview_empty"))

        self.update_generated_statuses()

    def set_status(self, text):
        self.status_text.set(text)

    def set_busy(self, busy):
        cursor = "watch" if busy else ""
        self.root.configure(cursor=cursor)

    def on_close(self):
        self.root.destroy()

    def refresh_articles(self):
        try:
            page_count = int(self.fetch_pages.get())
        except ValueError:
            messagebox.showinfo(self.tr("notice"), self.tr("fetch_number"))
            return

        if page_count < 1:
            messagebox.showinfo(self.tr("notice"), self.tr("fetch_min"))
            return

        self.run_background(lambda: self.refresh_worker(page_count))

    def refresh_worker(self, page_count):
        self.root.after(0, lambda: self.set_status(self.tr("refreshing")))
        try:
            articles = get_recent_articles(page_count)
        except Exception:
            cached_articles = load_articles_cache()
            if cached_articles:
                self.root.after(0, lambda: self.show_articles(cached_articles))
                self.root.after(0, lambda: self.set_status("Failed to refresh. Loaded articles from cache."))
            else:
                self.root.after(0, lambda: self.set_status("Failed to load articles."))
            return

        save_articles_cache(articles)
        self.root.after(0, lambda: self.show_articles(articles))
        self.root.after(0, lambda: self.set_status(self.tr("loaded", count=len(articles), pages=page_count)))

    def show_articles(self, articles):
        self.articles = articles
        self.render_article_rows()

    def render_article_rows(self):
        self.row_vars = []
        self.status_labels = []
        for widget in self.article_list.winfo_children():
            widget.destroy()

        output_dir = Path(self.output_dir.get())
        if self.only_show_ungenerated.get():
            self.visible_articles = [
                article for article in self.articles
                if not is_article_generated(article, output_dir)
            ]
        else:
            self.visible_articles = list(self.articles)

        for index, article in enumerate(self.visible_articles):
            selected = False
            date_text = article["publish_dt"].date().isoformat()
            status_text = self.tr("generated") if is_article_generated(article, output_dir) else ""
            var = ctk.BooleanVar(value=selected)
            self.row_vars.append(var)

            row_bg = "#ffffff" if index % 2 == 0 else "#f9fafb"
            row = ctk.CTkFrame(self.article_list, fg_color=row_bg, corner_radius=6)
            row.grid(row=index, column=0, columnspan=5, sticky="ew", padx=4, pady=2)
            row.grid_columnconfigure(0, minsize=62)
            row.grid_columnconfigure(1, minsize=104)
            row.grid_columnconfigure(2, weight=2)
            row.grid_columnconfigure(3, weight=3)
            row.grid_columnconfigure(4, minsize=120)

            ctk.CTkCheckBox(row, text="", variable=var, width=24).grid(row=0, column=0, sticky="w", padx=12, pady=8)
            date_label = ctk.CTkLabel(row, text=date_text, font=FONT_SMALL, text_color="#344054", anchor="w")
            date_label.grid(row=0, column=1, sticky="ew", padx=8)
            title_label = ctk.CTkLabel(row, text=article["title"], font=FONT_SMALL, text_color="#111827", anchor="w")
            title_label.grid(row=0, column=2, sticky="ew", padx=8)
            url_label = ctk.CTkLabel(row, text=article["url"], font=FONT_TINY, text_color="#667085", anchor="w")
            url_label.grid(row=0, column=3, sticky="ew", padx=8)
            status_label = ctk.CTkLabel(row, text=status_text, font=FONT_SMALL, text_color="#0f766e", anchor="w")
            status_label.grid(row=0, column=4, sticky="ew", padx=8)
            self.status_labels.append(status_label)

            for widget in (row, date_label, title_label, url_label, status_label):
                widget.bind("<Button-1>", lambda event, row_index=index: self.load_preview(row_index))

    def set_preview_text(self, text):
        self.preview_text.configure(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.insert("1.0", text)
        self.preview_text.configure(state="disabled")

    def load_preview(self, row_index):
        if row_index < 0 or row_index >= len(self.visible_articles):
            return

        article = self.visible_articles[row_index]
        self.run_background(lambda: self.preview_worker(article))

    def preview_worker(self, article):
        self.root.after(0, lambda: self.set_status(self.tr("loading_preview")))
        try:
            preview_text = get_article_preview(article, self.language.get())
        except Exception:
            self.root.after(0, lambda: self.set_status(self.tr("preview_failed")))
            return

        self.root.after(0, lambda: self.set_preview_text(preview_text))
        self.root.after(0, lambda: self.set_status(self.tr("preview_loaded")))

    def update_generated_statuses(self):
        if self.only_show_ungenerated.get():
            self.render_article_rows()
            return

        output_dir = Path(self.output_dir.get())
        for article, status_label in zip(self.visible_articles, self.status_labels):
            status_text = self.tr("generated") if is_article_generated(article, output_dir) else ""
            status_label.configure(text=status_text)

    def select_all(self):
        for var in self.row_vars:
            var.set(True)
        self.set_status(self.tr("all_selected"))

    def clear_all(self):
        for var in self.row_vars:
            var.set(False)
        self.set_status(self.tr("selection_cleared"))

    def choose_output_dir(self):
        folder = filedialog.askdirectory(initialdir=self.output_dir.get() or str(DEFAULT_OUTPUT_DIR))
        if folder:
            output_dir = Path(folder)
            output_dir.mkdir(exist_ok=True)
            save_output_dir(output_dir)
            self.output_dir.set(str(output_dir))
            self.update_generated_statuses()
            self.set_status(self.tr("save_folder_selected"))

    def selected_articles(self):
        selected = []
        for index, var in enumerate(self.row_vars):
            if var.get():
                selected.append(self.visible_articles[index])
        return selected

    def generate_selected(self):
        articles = self.selected_articles()
        if not articles:
            messagebox.showinfo(self.tr("notice"), self.tr("select_article"))
            return

        output_dir = Path(self.output_dir.get())
        self.run_background(lambda: self.generate_worker(articles, output_dir))

    def generate_today(self):
        try:
            page_count = int(self.fetch_pages.get())
        except ValueError:
            messagebox.showinfo(self.tr("notice"), self.tr("fetch_number"))
            return

        if page_count < 1:
            messagebox.showinfo(self.tr("notice"), self.tr("fetch_min"))
            return

        output_dir = Path(self.output_dir.get())
        self.run_background(lambda: self.generate_today_worker(page_count, output_dir))

    def generate_today_worker(self, page_count, output_dir):
        self.root.after(0, lambda: self.set_status(self.tr("refreshing")))
        articles = get_recent_articles(page_count)
        save_articles_cache(articles)
        self.root.after(0, lambda: self.show_articles(articles))

        today = date.today()
        ungenerated_articles = [
            article for article in articles
            if not is_article_generated(article, output_dir)
        ]
        articles_to_generate = [
            article for article in ungenerated_articles
            if article["publish_dt"].date() == today
        ]

        if not articles_to_generate:
            if not ungenerated_articles:
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(self.tr("notice"), self.tr("no_ungenerated_articles")),
                )
                return

            latest_date = max(article["publish_dt"].date() for article in ungenerated_articles)
            latest_articles = [
                article for article in ungenerated_articles
                if article["publish_dt"].date() == latest_date
            ]
            if not self.ask_generate_latest_articles():
                return
            articles_to_generate = latest_articles

        self.generate_worker(articles_to_generate, output_dir)

    def ask_generate_latest_articles(self):
        result = {"yes": False}
        finished = threading.Event()

        def ask():
            result["yes"] = messagebox.askyesno(
                self.tr("notice"),
                self.tr("no_today_generate_latest"),
            )
            finished.set()

        self.root.after(0, ask)
        finished.wait()
        return result["yes"]

    def generate_worker(self, articles, output_dir):
        files = []
        total = len(articles)
        for index, article in enumerate(articles, start=1):
            self.root.after(
                0,
                lambda current=index, count=total: self.set_status(
                    self.tr("generation_progress", current=current, total=count)
                ),
            )
            files.extend(generate_articles([article], output_dir))

        self.root.after(0, self.update_generated_statuses)
        self.root.after(0, lambda: self.set_status(self.tr("generation_complete")))
        self.root.after(0, lambda: messagebox.showinfo(self.tr("complete_title"), self.tr("complete_message", count=len(files))))

    def open_output_dir(self):
        output_dir = Path(self.output_dir.get())
        output_dir.mkdir(exist_ok=True)
        os.startfile(output_dir)
        self.set_status(self.tr("output_opened"))

    def run_background(self, target):
        def wrapped():
            try:
                self.root.after(0, lambda: self.set_busy(True))
                target()
            except Exception as exc:
                self.root.after(0, lambda: self.set_status(self.tr("operation_failed")))
                self.root.after(0, lambda: messagebox.showerror(self.tr("error"), str(exc)))
            finally:
                self.root.after(0, lambda: self.set_busy(False))

        threading.Thread(target=wrapped, daemon=True).start()

