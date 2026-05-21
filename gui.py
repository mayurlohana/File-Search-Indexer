import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import sys
import subprocess
import threading
import queue
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from database import DatabaseManager
from scanner import FileScanner

class FileIndexerApp(tk.Tk):
    """
    Main Tkinter application for the File Search Indexer.
    Implements a responsive, beautifully styled dark theme GUI with multi-threaded
    scanning, searching, sorting, pagination, duplicate finding, and file operations.
    """
    def __init__(self, db_path: str = "index.db"):
        super().__init__()
        self.title("File Search Indexer")
        self.geometry("1100x750")
        self.minimum_size = (900, 600)
        self.minsize(*self.minimum_size)

        self.db = DatabaseManager(db_path)
        self.scanner = FileScanner(self.db)
        
        # Communication queue for background thread
        self.queue = queue.Queue()
        self.scan_thread: Optional[threading.Thread] = None

        # Pagination & Search State
        self.current_page = 1
        self.total_pages = 1
        self.page_limit = 50
        self.current_search_results: List[Dict[str, Any]] = []
        self.total_search_count = 0

        # Selected duplicate group state
        self.duplicate_groups: List[Dict[str, Any]] = []

        # Initialize Modern Style
        self.setup_styles()
        
        # Build UI layout
        self.build_ui()
        
        # Start queue polling
        self.poll_queue()

        # Initial load of recently added files
        self.refresh_recently_added()
        self.refresh_extensions_list()

    def setup_styles(self):
        """Sets up a premium dark theme styling using ttk.Style."""
        self.style = ttk.Style()
        self.style.theme_use("clam")

        # Color Palette
        self.bg_color = "#1e1e24"        # Dark charcoal
        self.panel_bg = "#272935"        # Lighter charcoal for containers
        self.entry_bg = "#303242"        # Slate/blue gray for inputs
        self.fg_color = "#e2e8f0"        # Soft off-white
        self.fg_muted = "#94a3b8"        # Soft muted gray
        self.accent_color = "#3b82f6"     # Vibrant blue
        self.accent_hover = "#2563eb"     # Muted hover blue
        self.success_color = "#10b981"    # Emerald green
        self.danger_color = "#ef4444"     # Soft red for delete
        self.border_color = "#3f3f46"     # Muted border color

        self.configure(bg=self.bg_color)

        # Base Configuration
        self.style.configure(".", 
            background=self.bg_color, 
            foreground=self.fg_color, 
            fieldbackground=self.entry_bg,
            bordercolor=self.border_color,
            font=("Segoe UI", 10)
        )

        # Labels
        self.style.configure("TLabel", background=self.bg_color, foreground=self.fg_color)
        self.style.configure("Panel.TLabel", background=self.panel_bg, foreground=self.fg_color)
        self.style.configure("Muted.TLabel", background=self.bg_color, foreground=self.fg_muted, font=("Segoe UI", 9))
        self.style.configure("PanelMuted.TLabel", background=self.panel_bg, foreground=self.fg_muted, font=("Segoe UI", 9))
        self.style.configure("Title.TLabel", background=self.bg_color, foreground=self.accent_color, font=("Segoe UI", 16, "bold"))
        self.style.configure("PanelTitle.TLabel", background=self.panel_bg, foreground=self.accent_color, font=("Segoe UI", 12, "bold"))

        # Buttons
        self.style.configure("TButton", 
            background=self.accent_color, 
            foreground="#ffffff", 
            borderwidth=0, 
            padding=(10, 5), 
            font=("Segoe UI", 10, "bold")
        )
        self.style.map("TButton", 
            background=[("active", self.accent_hover), ("disabled", "#4b5563")],
            foreground=[("disabled", "#9ca3af")]
        )

        self.style.configure("Secondary.TButton", 
            background="#4b5563", 
            foreground="#ffffff", 
            borderwidth=0, 
            padding=(8, 4), 
            font=("Segoe UI", 9, "bold")
        )
        self.style.map("Secondary.TButton", 
            background=[("active", "#374151")]
        )

        # Entry & Combobox
        self.style.configure("TEntry", 
            fieldbackground=self.entry_bg, 
            foreground=self.fg_color, 
            insertcolor=self.fg_color,
            borderwidth=1
        )
        self.style.configure("TCombobox", 
            fieldbackground=self.entry_bg, 
            foreground=self.fg_color,
            background=self.panel_bg,
            arrowcolor=self.fg_color
        )
        self.style.map("TCombobox", 
            fieldbackground=[("readonly", self.entry_bg)],
            foreground=[("readonly", self.fg_color)]
        )

        # Frame backings
        self.style.configure("TFrame", background=self.bg_color)
        self.style.configure("Panel.TFrame", background=self.panel_bg)

        # Labelframe styling
        self.style.configure("TLabelframe", background=self.panel_bg, foreground=self.accent_color, bordercolor=self.border_color, borderwidth=1)
        self.style.configure("TLabelframe.Label", background=self.panel_bg, foreground=self.accent_color, font=("Segoe UI", 10, "bold"))

        # Notebook (Tabs) styling
        self.style.configure("TNotebook", background=self.bg_color, borderwidth=0, tabmargins=(2, 4, 2, 0))
        self.style.configure("TNotebook.Tab", 
            background="#2e303f", 
            foreground=self.fg_muted, 
            font=("Segoe UI", 10, "bold"), 
            padding=(15, 8),
            borderwidth=1,
            bordercolor=self.border_color
        )
        self.style.map("TNotebook.Tab", 
            background=[("selected", self.panel_bg)], 
            foreground=[("selected", self.fg_color)],
            bordercolor=[("selected", self.border_color)]
        )

        # Treeview (Table) styling
        self.style.configure("Treeview", 
            background=self.panel_bg, 
            foreground=self.fg_color, 
            fieldbackground=self.panel_bg, 
            rowheight=26, 
            font=("Segoe UI", 10),
            borderwidth=0
        )
        self.style.configure("Treeview.Heading", 
            background=self.entry_bg, 
            foreground=self.fg_color, 
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            borderwidth=1
        )
        self.style.map("Treeview.Heading", 
            background=[("active", "#3f3f46")]
        )
        self.style.map("Treeview", 
            background=[("selected", self.accent_color)], 
            foreground=[("selected", "#ffffff")]
        )

        # Progressbar
        self.style.configure("TProgressbar", thickness=8, troughcolor=self.entry_bg, background=self.accent_color)

    def build_ui(self):
        """Constructs the window components."""
        # Main vertical padding
        main_container = ttk.Frame(self, padding=(15, 10, 15, 10))
        main_container.pack(fill=tk.BOTH, expand=True)

        # ----------------- Top Section: Indexing Controls -----------------
        top_frame = ttk.Frame(main_container)
        top_frame.pack(fill=tk.X, pady=(0, 15))

        title_label = ttk.Label(top_frame, text="FILE INDEXER", style="Title.TLabel")
        title_label.pack(anchor=tk.W, pady=(0, 5))

        ctrl_row = ttk.Frame(top_frame)
        ctrl_row.pack(fill=tk.X)

        ttk.Label(ctrl_row, text="Directory to scan:").pack(side=tk.LEFT, padx=(0, 8))
        
        self.dir_path_var = tk.StringVar(value=os.path.abspath("."))
        self.dir_entry = ttk.Entry(ctrl_row, textvariable=self.dir_path_var, font=("Segoe UI", 10))
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        self.browse_btn = ttk.Button(ctrl_row, text="Browse...", style="Secondary.TButton", command=self.browse_directory)
        self.browse_btn.pack(side=tk.LEFT, padx=5)

        self.scan_btn = ttk.Button(ctrl_row, text="Start Scan", command=self.toggle_scan)
        self.scan_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Progress Bar & Scanner Status (Below top row)
        self.status_row = ttk.Frame(top_frame, padding=(0, 5, 0, 0))
        self.status_row.pack(fill=tk.X)
        
        self.progress_bar = ttk.Progressbar(self.status_row, mode="indeterminate")
        self.progress_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        self.progress_bar.pack_forget()  # Hide initially

        self.status_label = ttk.Label(self.status_row, text="Status: Ready", style="Muted.TLabel")
        self.status_label.pack(side=tk.LEFT)

        self.progress_label = ttk.Label(self.status_row, text="", style="Muted.TLabel")
        self.progress_label.pack(side=tk.RIGHT)

        # Separator
        ttk.Separator(main_container, orient="horizontal").pack(fill=tk.X, pady=(0, 10))

        # ----------------- Middle Section: Tabbed Panel -----------------
        self.notebook = ttk.Notebook(main_container)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.setup_search_tab()
        self.setup_duplicates_tab()
        self.setup_recent_tab()

        # ----------------- Context Menus -----------------
        self.context_menu = tk.Menu(self, tearoff=0, bg=self.panel_bg, fg=self.fg_color, activebackground=self.accent_color, activeforeground="#ffffff")
        self.context_menu.add_command(label="Open File / Run", command=self.context_open_file)
        self.context_menu.add_command(label="Reveal in Finder / Explorer", command=self.context_open_folder)
        self.context_menu.add_command(label="Copy Full Path", command=self.context_copy_path)

        # Custom Context Menu for Duplicates List
        self.duplicate_context_menu = tk.Menu(self, tearoff=0, bg=self.panel_bg, fg=self.fg_color, activebackground=self.accent_color, activeforeground="#ffffff")
        self.duplicate_context_menu.add_command(label="Open File / Run", command=self.dup_context_open_file)
        self.duplicate_context_menu.add_command(label="Reveal in Finder / Explorer", command=self.dup_context_open_folder)
        self.duplicate_context_menu.add_command(label="Copy Full Path", command=self.dup_context_copy_path)
        self.duplicate_context_menu.add_separator()
        self.duplicate_context_menu.add_command(label="DELETE File from Disk", command=self.dup_context_delete_file, foreground=self.danger_color)

    # ----------------------------------------------------
    # TAB SETUP: Search & Filter
    # ----------------------------------------------------
    def setup_search_tab(self):
        search_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(search_tab, text="🔍 Search Index")

        # Layout: Left side for Filters (width: 280), Right side for Results
        left_filters = ttk.Frame(search_tab, padding=(10, 10, 5, 10), style="Panel.TFrame", width=280)
        left_filters.pack(side=tk.LEFT, fill=tk.Y)
        left_filters.pack_propagate(False) # Keep width fixed

        right_results = ttk.Frame(search_tab, padding=(5, 10, 10, 10), style="Panel.TFrame")
        right_results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Filters Label
        ttk.Label(left_filters, text="Search & Filter", style="PanelTitle.TLabel").pack(anchor=tk.W, pady=(0, 12))

        # Filter: Search text query
        ttk.Label(left_filters, text="File Name Keyword:", style="Panel.TLabel").pack(anchor=tk.W, pady=(5, 2))
        self.query_var = tk.StringVar()
        self.query_entry = ttk.Entry(left_filters, textvariable=self.query_var)
        self.query_entry.pack(fill=tk.X, pady=(0, 8))
        self.query_entry.bind("<Return>", lambda e: self.trigger_search())

        # Filter: Extension Combobox
        ttk.Label(left_filters, text="Extension:", style="Panel.TLabel").pack(anchor=tk.W, pady=(5, 2))
        self.ext_var = tk.StringVar(value="All Extensions")
        self.ext_combo = ttk.Combobox(left_filters, textvariable=self.ext_var, state="readonly")
        self.ext_combo["values"] = ["All Extensions"]
        self.ext_combo.pack(fill=tk.X, pady=(0, 8))

        # Filter: Size Filter Group
        size_frame = ttk.LabelFrame(left_filters, text="File Size Limits", padding=(8, 8))
        size_frame.pack(fill=tk.X, pady=(5, 8))
        
        ttk.Label(size_frame, text="Min Size:", style="Panel.TLabel").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.min_size_var = tk.StringVar()
        self.min_size_entry = ttk.Entry(size_frame, textvariable=self.min_size_var, width=10)
        self.min_size_entry.grid(row=0, column=1, sticky=tk.EW, padx=(5, 0), pady=2)
        
        ttk.Label(size_frame, text="Max Size:", style="Panel.TLabel").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.max_size_var = tk.StringVar()
        self.max_size_entry = ttk.Entry(size_frame, textvariable=self.max_size_var, width=10)
        self.max_size_entry.grid(row=1, column=1, sticky=tk.EW, padx=(5, 0), pady=2)

        self.size_unit_var = tk.StringVar(value="MB")
        self.size_unit_combo = ttk.Combobox(size_frame, textvariable=self.size_unit_var, values=["B", "KB", "MB", "GB"], state="readonly", width=5)
        self.size_unit_combo.grid(row=0, column=2, rowspan=2, padx=(5, 0), sticky=tk.NS)
        
        size_frame.columnconfigure(1, weight=1)

        # Filter: Date Filter Group
        date_frame = ttk.LabelFrame(left_filters, text="Date Modified Filter", padding=(8, 8))
        date_frame.pack(fill=tk.X, pady=(5, 8))

        self.date_preset_var = tk.StringVar(value="Any Time")
        self.date_preset_combo = ttk.Combobox(
            date_frame, 
            textvariable=self.date_preset_var, 
            values=["Any Time", "Today", "Last 7 Days", "Last 30 Days", "Custom Range"], 
            state="readonly"
        )
        self.date_preset_combo.pack(fill=tk.X, pady=(0, 5))
        self.date_preset_combo.bind("<<ComboboxSelected>>", self.on_date_preset_change)

        # Custom Date sub-frame
        self.custom_date_frame = ttk.Frame(date_frame, style="Panel.TFrame")
        # Hidden initially
        ttk.Label(self.custom_date_frame, text="Start Date (YYYY-MM-DD):", style="Panel.TLabel").pack(anchor=tk.W)
        self.start_date_var = tk.StringVar()
        self.start_date_entry = ttk.Entry(self.custom_date_frame, textvariable=self.start_date_var)
        self.start_date_entry.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(self.custom_date_frame, text="End Date (YYYY-MM-DD):", style="Panel.TLabel").pack(anchor=tk.W)
        self.end_date_var = tk.StringVar()
        self.end_date_entry = ttk.Entry(self.custom_date_frame, textvariable=self.end_date_var)
        self.end_date_entry.pack(fill=tk.X, pady=(0, 2))

        # Filter: Sorting Group
        sort_frame = ttk.LabelFrame(left_filters, text="Sorting Options", padding=(8, 8))
        sort_frame.pack(fill=tk.X, pady=(5, 12))

        ttk.Label(sort_frame, text="Sort By:", style="Panel.TLabel").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.sort_by_var = tk.StringVar(value="Name")
        self.sort_by_combo = ttk.Combobox(sort_frame, textvariable=self.sort_by_var, values=["Name", "Size", "Date Modified", "Date Created"], state="readonly", width=12)
        self.sort_by_combo.grid(row=0, column=1, sticky=tk.EW, padx=(5, 0), pady=2)

        ttk.Label(sort_frame, text="Order:", style="Panel.TLabel").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.sort_order_var = tk.StringVar(value="Ascending")
        self.sort_order_combo = ttk.Combobox(sort_frame, textvariable=self.sort_order_var, values=["Ascending", "Descending"], state="readonly", width=12)
        self.sort_order_combo.grid(row=1, column=1, sticky=tk.EW, padx=(5, 0), pady=2)
        
        sort_frame.columnconfigure(1, weight=1)

        # Action Buttons
        btn_row = ttk.Frame(left_filters, style="Panel.TFrame")
        btn_row.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))

        self.reset_btn = ttk.Button(btn_row, text="Clear", style="Secondary.TButton", command=self.reset_filters)
        self.reset_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))

        self.search_btn = ttk.Button(btn_row, text="Apply Search", command=self.trigger_search)
        self.search_btn.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(4, 0))

        # Results treeview (Right Panel)
        results_header = ttk.Frame(right_results, style="Panel.TFrame")
        results_header.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(results_header, text="Search Results", style="PanelTitle.TLabel").pack(side=tk.LEFT)
        self.results_count_label = ttk.Label(results_header, text="0 files indexed", style="PanelMuted.TLabel")
        self.results_count_label.pack(side=tk.RIGHT)

        # Table container
        table_frame = ttk.Frame(right_results)
        table_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("Name", "Ext", "Size", "Modified", "Path")
        self.search_tree = ttk.Treeview(table_frame, columns=cols, show="headings", selectmode="browse")
        
        self.search_tree.heading("Name", text="Name", command=lambda: self.set_sorting_from_col("Name"))
        self.search_tree.heading("Ext", text="Ext")
        self.search_tree.heading("Size", text="Size", command=lambda: self.set_sorting_from_col("Size"))
        self.search_tree.heading("Modified", text="Date Modified", command=lambda: self.set_sorting_from_col("Date Modified"))
        self.search_tree.heading("Path", text="Path")

        self.search_tree.column("Name", width=200, anchor=tk.W)
        self.search_tree.column("Ext", width=50, anchor=tk.CENTER)
        self.search_tree.column("Size", width=90, anchor=tk.E)
        self.search_tree.column("Modified", width=140, anchor=tk.CENTER)
        self.search_tree.column("Path", width=350, anchor=tk.W)

        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.search_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.search_tree.xview)
        self.search_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.search_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Bindings
        self.search_tree.bind("<Double-1>", self.on_search_double_click)
        self.search_tree.bind("<Button-3>", self.show_context_menu)
        self.search_tree.bind("<Button-2>", self.show_context_menu) # For Mac right-click/two-finger tap

        # Pagination controls at bottom of results
        pager_frame = ttk.Frame(right_results, padding=(0, 8, 0, 0), style="Panel.TFrame")
        pager_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.prev_btn = ttk.Button(pager_frame, text="◀ Prev", style="Secondary.TButton", command=self.prev_page)
        self.prev_btn.pack(side=tk.LEFT)

        self.page_label = ttk.Label(pager_frame, text="Page 1 of 1", style="Panel.TLabel")
        self.page_label.pack(side=tk.LEFT, padx=15)

        self.next_btn = ttk.Button(pager_frame, text="Next ▶", style="Secondary.TButton", command=self.next_page)
        self.next_btn.pack(side=tk.LEFT)

        # Row limit combobox
        ttk.Label(pager_frame, text="Rows per page:", style="Panel.TLabel").pack(side=tk.RIGHT, padx=5)
        self.limit_var = tk.StringVar(value="50")
        self.limit_combo = ttk.Combobox(pager_frame, textvariable=self.limit_var, values=["25", "50", "100", "200"], state="readonly", width=5)
        self.limit_combo.pack(side=tk.RIGHT)
        self.limit_combo.bind("<<ComboboxSelected>>", self.on_limit_change)

    # ----------------------------------------------------
    # TAB SETUP: Duplicate Finder
    # ----------------------------------------------------
    def setup_duplicates_tab(self):
        dup_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(dup_tab, text="👥 Duplicate Finder")

        # Split pane: Left for duplicate groups, Right for files in selected group
        paned = ttk.Panedwindow(dup_tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left: Group Summary List
        left_group_frame = ttk.Frame(paned, padding=5, style="Panel.TFrame")
        paned.add(left_group_frame, weight=2)
        
        ttk.Label(left_group_frame, text="Duplicate Content Groups", style="PanelTitle.TLabel").pack(anchor=tk.W, pady=(0, 5))
        
        g_cols = ("Hash", "Size", "Count")
        self.dup_group_tree = ttk.Treeview(left_group_frame, columns=g_cols, show="headings", selectmode="browse")
        self.dup_group_tree.heading("Hash", text="MD5 Hash Content Signature")
        self.dup_group_tree.heading("Size", text="File Size")
        self.dup_group_tree.heading("Count", text="Count")
        
        self.dup_group_tree.column("Hash", width=220, anchor=tk.W)
        self.dup_group_tree.column("Size", width=90, anchor=tk.E)
        self.dup_group_tree.column("Count", width=60, anchor=tk.CENTER)

        g_vsb = ttk.Scrollbar(left_group_frame, orient="vertical", command=self.dup_group_tree.yview)
        self.dup_group_tree.configure(yscrollcommand=g_vsb.set)
        
        self.dup_group_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        g_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.dup_group_tree.bind("<<TreeviewSelect>>", self.on_dup_group_select)

        # Right: Specific Paths in the selected group
        right_paths_frame = ttk.Frame(paned, padding=5, style="Panel.TFrame")
        paned.add(right_paths_frame, weight=3)

        top_bar = ttk.Frame(right_paths_frame, style="Panel.TFrame")
        top_bar.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(top_bar, text="Paths Sharing this Signature", style="PanelTitle.TLabel").pack(side=tk.LEFT)
        
        p_cols = ("Name", "Folder", "Modified")
        self.dup_paths_tree = ttk.Treeview(right_paths_frame, columns=p_cols, show="headings", selectmode="browse")
        self.dup_paths_tree.heading("Name", text="File Name")
        self.dup_paths_tree.heading("Folder", text="Containing Directory")
        self.dup_paths_tree.heading("Modified", text="Date Modified")
        
        self.dup_paths_tree.column("Name", width=150, anchor=tk.W)
        self.dup_paths_tree.column("Folder", width=250, anchor=tk.W)
        self.dup_paths_tree.column("Modified", width=140, anchor=tk.CENTER)

        p_vsb = ttk.Scrollbar(right_paths_frame, orient="vertical", command=self.dup_paths_tree.yview)
        self.dup_paths_tree.configure(yscrollcommand=p_vsb.set)
        
        self.dup_paths_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        p_vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Bindings for duplicate detail list
        self.dup_paths_tree.bind("<Double-1>", self.on_dup_double_click)
        self.dup_paths_tree.bind("<Button-3>", self.show_dup_context_menu)
        self.dup_paths_tree.bind("<Button-2>", self.show_dup_context_menu)

    # ----------------------------------------------------
    # TAB SETUP: Recently Added
    # ----------------------------------------------------
    def setup_recent_tab(self):
        recent_tab = ttk.Frame(self.notebook, style="Panel.TFrame")
        self.notebook.add(recent_tab, text="📅 Recently Modified")

        recent_header = ttk.Frame(recent_tab, style="Panel.TFrame", padding=(10, 10, 10, 5))
        recent_header.pack(fill=tk.X)
        
        ttk.Label(recent_header, text="Recently Modified Files (Last 50)", style="PanelTitle.TLabel").pack(side=tk.LEFT)
        ttk.Button(recent_header, text="🔄 Refresh", style="Secondary.TButton", command=self.refresh_recently_added).pack(side=tk.RIGHT)

        recent_container = ttk.Frame(recent_tab, padding=(10, 5, 10, 10))
        recent_container.pack(fill=tk.BOTH, expand=True)

        cols = ("Name", "Ext", "Size", "Modified", "Path")
        self.recent_tree = ttk.Treeview(recent_container, columns=cols, show="headings", selectmode="browse")
        
        self.recent_tree.heading("Name", text="Name")
        self.recent_tree.heading("Ext", text="Ext")
        self.recent_tree.heading("Size", text="Size")
        self.recent_tree.heading("Modified", text="Date Modified")
        self.recent_tree.heading("Path", text="Path")

        self.recent_tree.column("Name", width=200, anchor=tk.W)
        self.recent_tree.column("Ext", width=50, anchor=tk.CENTER)
        self.recent_tree.column("Size", width=90, anchor=tk.E)
        self.recent_tree.column("Modified", width=140, anchor=tk.CENTER)
        self.recent_tree.column("Path", width=380, anchor=tk.W)

        vsb = ttk.Scrollbar(recent_container, orient="vertical", command=self.recent_tree.yview)
        self.recent_tree.configure(yscrollcommand=vsb.set)
        
        self.recent_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.recent_tree.bind("<Double-1>", self.on_recent_double_click)
        self.recent_tree.bind("<Button-3>", self.show_context_menu_for_recent)
        self.recent_tree.bind("<Button-2>", self.show_context_menu_for_recent)

    # ----------------------------------------------------
    # INTERACTION AND HANDLERS: Form Logic & Filters
    # ----------------------------------------------------
    def on_date_preset_change(self, event=None):
        """Shows or hides custom date input fields depending on preset selection."""
        if self.date_preset_var.get() == "Custom Range":
            self.custom_date_frame.pack(fill=tk.X, pady=(5, 0))
        else:
            self.custom_date_frame.pack_forget()

    def on_limit_change(self, event=None):
        """Updates records-per-page limit and re-runs search."""
        self.page_limit = int(self.limit_var.get())
        self.current_page = 1
        self.run_search()

    def reset_filters(self):
        """Clears search fields and updates the search results tree."""
        self.query_var.set("")
        self.ext_var.set("All Extensions")
        self.min_size_var.set("")
        self.max_size_var.set("")
        self.size_unit_var.set("MB")
        self.date_preset_var.set("Any Time")
        self.start_date_var.set("")
        self.end_date_var.set("")
        self.custom_date_frame.pack_forget()
        
        self.sort_by_var.set("Name")
        self.sort_order_var.set("Ascending")
        
        self.current_page = 1
        self.run_search()

    def set_sorting_from_col(self, col_name: str):
        """Toggles sorting column and order by clicking table column headers directly."""
        current_sort = self.sort_by_var.get()
        current_order = self.sort_order_var.get()
        
        # Maps tree columns to Database fields
        mapping = {"Name": "Name", "Size": "Size", "Date Modified": "Date Modified"}
        mapped_col = mapping.get(col_name)
        if not mapped_col:
            return
            
        if current_sort == mapped_col:
            new_order = "Descending" if current_order == "Ascending" else "Ascending"
            self.sort_order_var.set(new_order)
        else:
            self.sort_by_var.set(mapped_col)
            self.sort_order_var.set("Ascending")
            
        self.current_page = 1
        self.run_search()

    def get_parsed_filters(self) -> Dict[str, Any]:
        """Parses and computes search criteria from the input controls."""
        filters = {}

        # 1. Size
        size_multiplier = 1
        unit = self.size_unit_var.get()
        if unit == "KB":
            size_multiplier = 1024
        elif unit == "MB":
            size_multiplier = 1024 * 1024
        elif unit == "GB":
            size_multiplier = 1024 * 1024 * 1024

        try:
            min_size_str = self.min_size_var.get().strip()
            filters["min_size"] = int(min_size_str) * size_multiplier if min_size_str else None
        except ValueError:
            filters["min_size"] = None

        try:
            max_size_str = self.max_size_var.get().strip()
            filters["max_size"] = int(max_size_str) * size_multiplier if max_size_str else None
        except ValueError:
            filters["max_size"] = None

        # 2. Extension
        ext = self.ext_var.get()
        filters["extension"] = None if ext == "All Extensions" else ext

        # 3. Dates (Modified At Epoch)
        now = time.time()
        preset = self.date_preset_var.get()
        filters["min_date"] = None
        filters["max_date"] = None

        if preset == "Today":
            # Start of today (midnight local time)
            midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            filters["min_date"] = midnight.timestamp()
        elif preset == "Last 7 Days":
            filters["min_date"] = now - (7 * 24 * 3600)
        elif preset == "Last 30 Days":
            filters["min_date"] = now - (30 * 24 * 3600)
        elif preset == "Custom Range":
            try:
                start_str = self.start_date_var.get().strip()
                if start_str:
                    dt = datetime.strptime(start_str, "%Y-%m-%d")
                    filters["min_date"] = dt.timestamp()
            except ValueError:
                pass
            
            try:
                end_str = self.end_date_var.get().strip()
                if end_str:
                    # Include full day until 23:59:59
                    dt = datetime.strptime(end_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
                    filters["max_date"] = dt.timestamp()
            except ValueError:
                pass

        # 4. Sorting mapping
        sort_map = {
            "Name": "name",
            "Size": "size",
            "Date Modified": "modified_at",
            "Date Created": "created_at"
        }
        filters["sort_by"] = sort_map.get(self.sort_by_var.get(), "name")
        filters["sort_order"] = "desc" if self.sort_order_var.get() == "Descending" else "asc"

        return filters

    # ----------------------------------------------------
    # DATA LOADING AND QUERIES
    # ----------------------------------------------------
    def trigger_search(self):
        """Resets page number to 1 and runs the search."""
        self.current_page = 1
        self.run_search()

    def run_search(self):
        """Fetches search results from the database with pagination, sorting, and filters."""
        query = self.query_var.get().strip()
        filters = self.get_parsed_filters()
        
        offset = (self.current_page - 1) * self.page_limit

        # Query Database
        results, total_count = self.db.search_files(
            query_str=query,
            extension=filters["extension"],
            min_size=filters["min_size"],
            max_size=filters["max_size"],
            min_date=filters["min_date"],
            max_date=filters["max_date"],
            sort_by=filters["sort_by"],
            sort_order=filters["sort_order"],
            limit=self.page_limit,
            offset=offset
        )

        self.current_search_results = results
        self.total_search_count = total_count
        self.total_pages = max(1, (total_count + self.page_limit - 1) // self.page_limit)

        # Update Treeview rows
        self.search_tree.delete(*self.search_tree.get_children())
        for f in results:
            self.search_tree.insert("", tk.END, values=(
                f["name"],
                f["extension"],
                self.format_size(f["size"]),
                self.format_date(f["modified_at"]),
                f["path"]
            ))

        # Update controls state
        self.page_label.configure(text=f"Page {self.current_page} of {self.total_pages}")
        
        if self.current_page <= 1:
            self.prev_btn.configure(state=tk.DISABLED)
        else:
            self.prev_btn.configure(state=tk.NORMAL)
            
        if self.current_page >= self.total_pages:
            self.next_btn.configure(state=tk.DISABLED)
        else:
            self.next_btn.configure(state=tk.NORMAL)

        # Update count labels
        total_idx = self.db.get_total_count()
        self.results_count_label.configure(text=f"Showing {len(results)} of {total_count} matching files ({total_idx} total indexed)")

    def prev_page(self):
        """Navigates to the previous page."""
        if self.current_page > 1:
            self.current_page -= 1
            self.run_search()

    def next_page(self):
        """Navigates to the next page."""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.run_search()

    def refresh_recently_added(self):
        """Fetches and displays the newest modified files."""
        recent_files = self.db.get_recently_added(50)
        self.recent_tree.delete(*self.recent_tree.get_children())
        for f in recent_files:
            self.recent_tree.insert("", tk.END, values=(
                f["name"],
                f["extension"],
                self.format_size(f["size"]),
                self.format_date(f["modified_at"]),
                f["path"]
            ))

    def refresh_duplicates(self):
        """Fetches duplicate groupings and displays them on the duplicates tab."""
        self.duplicate_groups = self.db.get_duplicate_groups()
        
        self.dup_group_tree.delete(*self.dup_group_tree.get_children())
        self.dup_paths_tree.delete(*self.dup_paths_tree.get_children())

        for idx, group in enumerate(self.duplicate_groups):
            self.dup_group_tree.insert("", tk.END, iid=str(idx), values=(
                group["md5_hash"],
                self.format_size(group["size"]),
                group["count"]
            ))

    def on_dup_group_select(self, event):
        """Callback when a duplicate signature group is selected. Lists individual file occurrences."""
        selected = self.dup_group_tree.selection()
        if not selected:
            return
        
        group_idx = int(selected[0])
        group = self.duplicate_groups[group_idx]
        
        self.dup_paths_tree.delete(*self.dup_paths_tree.get_children())
        for f in group["files"]:
            folder = os.path.dirname(f["path"])
            self.dup_paths_tree.insert("", tk.END, iid=f["path"], values=(
                f["name"],
                folder,
                self.format_date(f["modified_at"])
            ))

    def refresh_extensions_list(self):
        """Populates the search extension combobox dynamically with extensions present in the database."""
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT extension FROM files WHERE extension IS NOT NULL AND extension != '' ORDER BY extension")
            exts = [r[0] for r in cursor.fetchall()]
        
        self.ext_combo["values"] = ["All Extensions"] + exts

    # ----------------------------------------------------
    # MULTITHREADED SCANNER RUNNER AND QUEUE
    # ----------------------------------------------------
    def toggle_scan(self):
        """Starts a background indexing run, or cancels it if one is active."""
        if self.scan_thread and self.scan_thread.is_alive():
            # Cancel requested
            self.scanner.cancel()
            self.status_label.configure(text="Status: Cancelling scan...")
            self.scan_btn.configure(state=tk.DISABLED)
            return

        target_dir = self.dir_path_var.get().strip()
        if not os.path.isdir(target_dir):
            messagebox.showerror("Invalid Directory", f"The directory '{target_dir}' does not exist.")
            return

        # Prepare UI for scan progress
        self.scan_btn.configure(text="Cancel Scan")
        self.browse_btn.configure(state=tk.DISABLED)
        self.dir_entry.configure(state=tk.DISABLED)
        self.progress_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(5, 0))
        self.progress_bar.start(10)
        self.status_label.configure(text="Status: Scanning...")

        # Spawn background thread to prevent UI freezing
        self.scan_thread = threading.Thread(
            target=self.run_background_scan,
            args=(target_dir,),
            daemon=True
        )
        self.scan_thread.start()

    def run_background_scan(self, target_dir: str):
        """Standard thread runner for directory scanner, feeding status back to the main UI queue."""
        def progress_cb(files, dirs):
            self.queue.put(("progress", (files, dirs)))

        def status_cb(msg):
            self.queue.put(("status", msg))

        try:
            files_indexed, dup_groups = self.scanner.scan_directory(
                target_dir,
                on_progress=progress_cb,
                on_status=status_cb
            )
            self.queue.put(("complete", (files_indexed, dup_groups)))
        except Exception as e:
            self.queue.put(("status", f"Error during scan: {str(e)}"))
            self.queue.put(("complete", (0, 0)))

    def poll_queue(self):
        """Monitors the communication queue, updating the main Tkinter thread widgets."""
        try:
            while True:
                msg_type, data = self.queue.get_nowait()
                if msg_type == "status":
                    self.status_label.configure(text=f"Status: {data}")
                elif msg_type == "progress":
                    files, dirs = data
                    self.progress_label.configure(text=f"Files found: {files} | Folders: {dirs}")
                elif msg_type == "complete":
                    files, dup_groups = data
                    self.progress_bar.stop()
                    self.progress_bar.pack_forget()
                    
                    self.scan_btn.configure(text="Start Scan", state=tk.NORMAL)
                    self.browse_btn.configure(state=tk.NORMAL)
                    self.dir_entry.configure(state=tk.NORMAL)
                    self.scan_thread = None

                    # Reload dynamic data in UI
                    self.refresh_extensions_list()
                    self.run_search()
                    self.refresh_recently_added()
                    self.refresh_duplicates()

                    messagebox.showinfo(
                        "Scan Finished", 
                        f"Scanning completed successfully!\n\nIndexed: {files} files\nDuplicate Content Groups: {dup_groups}"
                    )
        except queue.Empty:
            pass
        finally:
            # Reschedule check in 100ms
            self.after(100, self.poll_queue)

    def browse_directory(self):
        """Triggers path browser dialog and populates directory field."""
        selected = filedialog.askdirectory(initialdir=self.dir_path_var.get())
        if selected:
            self.dir_path_var.set(os.path.abspath(selected))

    # ----------------------------------------------------
    # FILE OPERATIONS (CONTEXT MENUS & CLICKS)
    # ----------------------------------------------------
    def format_size(self, size_bytes: int) -> str:
        """Returns human-readable representation of size in bytes."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
        else:
            return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

    def format_date(self, epoch_time: float) -> str:
        """Formats an epoch timestamp into standard visual representation."""
        try:
            return datetime.fromtimestamp(epoch_time).strftime("%Y-%m-%d %H:%M:%S")
        except (ValueError, OSError):
            return "Unknown"

    def get_selected_item_path(self, tree: ttk.Treeview) -> Optional[str]:
        """Utility to retrieve filepath field from the currently highlighted row in a treeview."""
        selected = tree.selection()
        if not selected:
            return None
        
        # Path is either stored in column index 4 (Search and Recent lists) 
        # or stored directly as the item ID (Duplicate Detail lists)
        if tree == self.dup_paths_tree:
            return selected[0] # The iid itself is the path

        item_values = tree.item(selected[0], "values")
        if item_values:
            return item_values[4] # Column index 4 represents full file path
        return None

    # Context Menu Handlers (Search & Recent Tables)
    def show_context_menu(self, event):
        """Displays search results right-click context menu."""
        # Find item under cursor position
        item = self.search_tree.identify_row(event.y)
        if item:
            self.search_tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def show_context_menu_for_recent(self, event):
        """Displays recently added files right-click context menu."""
        item = self.recent_tree.identify_row(event.y)
        if item:
            self.recent_tree.selection_set(item)
            # Reuses the standard context menu, operating on recent tree
            self.active_context_tree = self.recent_tree
            self.context_menu.post(event.x_root, event.y_root)
        else:
            self.active_context_tree = None

    def show_dup_context_menu(self, event):
        """Displays duplicates list right-click context menu."""
        item = self.dup_paths_tree.identify_row(event.y)
        if item:
            self.dup_paths_tree.selection_set(item)
            self.duplicate_context_menu.post(event.x_root, event.y_root)

    def _get_active_tree(self) -> ttk.Treeview:
        """Determines which list currently owns the click focus."""
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 0:
            return self.search_tree
        elif current_tab == 2:
            return self.recent_tree
        return self.search_tree

    def context_open_file(self):
        """Opens file in OS-default software from context menu click."""
        tree = self._get_active_tree()
        if hasattr(self, 'active_context_tree') and self.active_context_tree:
            tree = self.active_context_tree
            self.active_context_tree = None
        self.open_file_by_path(self.get_selected_item_path(tree))

    def context_open_folder(self):
        """Opens containing directory in Finder/Explorer from context menu click."""
        tree = self._get_active_tree()
        if hasattr(self, 'active_context_tree') and self.active_context_tree:
            tree = self.active_context_tree
            self.active_context_tree = None
        self.reveal_folder_by_path(self.get_selected_item_path(tree))

    def context_copy_path(self):
        """Copies highlighted full file path to Clipboard."""
        tree = self._get_active_tree()
        if hasattr(self, 'active_context_tree') and self.active_context_tree:
            tree = self.active_context_tree
            self.active_context_tree = None
        self.copy_path_to_clipboard(self.get_selected_item_path(tree))

    # Context Menu Handlers (Duplicates Tree)
    def dup_context_open_file(self):
        self.open_file_by_path(self.get_selected_item_path(self.dup_paths_tree))

    def dup_context_open_folder(self):
        self.reveal_folder_by_path(self.get_selected_item_path(self.dup_paths_tree))

    def dup_context_copy_path(self):
        self.copy_path_to_clipboard(self.get_selected_item_path(self.dup_paths_tree))

    def dup_context_delete_file(self):
        """Prompts user confirmation and deletes selected file from filesystem and db indices."""
        path = self.get_selected_item_path(self.dup_paths_tree)
        if not path or not os.path.exists(path):
            messagebox.showerror("Error", "Selected file path is invalid or already deleted.")
            return

        confirm = messagebox.askyesno(
            "Confirm Deletion",
            f"Are you absolutely sure you want to permanently delete this file?\n\n{path}\n\nThis cannot be undone!",
            icon="warning"
        )
        
        if confirm:
            try:
                # Remove file from disk
                os.remove(path)
                
                # Remove record from Database index
                with self.db._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM files WHERE path = ?", (path,))
                    conn.commit()

                # Refresh views
                self.refresh_duplicates()
                self.run_search()
                self.refresh_recently_added()
                
                messagebox.showinfo("Success", "File has been successfully deleted from disk and index.")
            except Exception as e:
                messagebox.showerror("Deletion Failed", f"An error occurred while deleting the file:\n{str(e)}")

    # Double click handlers
    def on_search_double_click(self, event):
        self.open_file_by_path(self.get_selected_item_path(self.search_tree))

    def on_recent_double_click(self, event):
        self.open_file_by_path(self.get_selected_item_path(self.recent_tree))

    def on_dup_double_click(self, event):
        self.open_file_by_path(self.get_selected_item_path(self.dup_paths_tree))

    # OS utilities
    def open_file_by_path(self, file_path: Optional[str]):
        """Opens file natively based on platform standard calls."""
        if not file_path:
            return
        
        if not os.path.exists(file_path):
            messagebox.showerror("File Not Found", f"The file no longer exists at:\n{file_path}")
            return

        try:
            if sys.platform == "win32":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.run(["open", file_path], check=True)
            else: # linux and others
                subprocess.run(["xdg-open", file_path], check=True)
        except Exception as e:
            messagebox.showerror("Error Opening File", f"Could not launch file:\n{str(e)}")

    def reveal_folder_by_path(self, file_path: Optional[str]):
        """Reveals file location in Finder/Explorer."""
        if not file_path:
            return
        
        if not os.path.exists(file_path):
            messagebox.showerror("File Not Found", f"The directory target no longer exists at:\n{file_path}")
            return

        folder_path = os.path.dirname(file_path)
        try:
            if sys.platform == "win32":
                subprocess.run(["explorer", "/select,", os.path.normpath(file_path)], check=True)
            elif sys.platform == "darwin":
                # Reveals the specific file in Finder
                subprocess.run(["open", "-R", file_path], check=True)
            else: # linux and others
                subprocess.run(["xdg-open", folder_path], check=True)
        except Exception as e:
            messagebox.showerror("Error Opening Location", f"Could not open containing directory:\n{str(e)}")

    def copy_path_to_clipboard(self, file_path: Optional[str]):
        """Copies text path value to clipboard system-wide."""
        if not file_path:
            return
        self.clipboard_clear()
        self.clipboard_append(file_path)
        self.update() # Keeps value on clipboard after closing
        
        # Display subtle visual confirmation in status bar
        old_status = self.status_label.cget("text")
        self.status_label.configure(text="Status: Path copied to clipboard!")
        self.after(2000, lambda: self.status_label.configure(text=old_status))
