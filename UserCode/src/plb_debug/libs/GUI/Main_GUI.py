import os
import re
import sys
import json
import getpass
import subprocess
from pathlib import Path
import traceback
from datetime import datetime
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox
from collections import Counter

from libs.GUI.Aux_GUI import ToolTip
from libs.Finder import Finder
from libs.Extractor import Extractor
from libs.Generator import Gen_PLB
from libs.Users import User_Manager

class PlistTool(Finder):
    def __init__(self, root):
        print("Running Init...")
        self.root = root
        self.root.title("SCAN BUNDLE TOOL")
        
        # Auto-adjust to screen size
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.geometry(f"{screen_width}x{screen_height}")
        self.root.state('zoomed')  # Maximize the window (Windows only)

        self.night_mode = tk.BooleanVar(value=False)
        self.night_mode_enabled = False 
        self.content = ""
        self.matches = []
        self.current_index = 0
        self.processed_text = ""
        self.IO_plb_output = ""
        self.file_path = ""  # Store the file path here
        self.Extracted_PreBurstPList_list = []  # Store extracted PreBurstPList
        self.include_preburst = tk.BooleanVar()  # Variable for the first switch
        self.use_debug_default = tk.BooleanVar(value=True)
        self.custom_name = tk.BooleanVar()  # Variable for the second switch
        self.custom_name_plb = tk.StringVar()  # Variable to store custom name
        self.output_file_path = ""  # Variable to store the output file path
        self.User_username = ""
        self.User_PListDebugFolder = ""
        self.User_BundleFolder = ""
        self.User_Project = ""
        self.User_Die = ""
        
        # Cache for network drive discovery
        self.network_drive_cache = {}
        
        # Store appended PList selections for accumulation
        self.appended_plist_content = ""

        self.extractor = Extractor(self)
        self.generator = Gen_PLB(self)
        self.user_manager = User_Manager(self)
        self.Setup_App() # Setup UI

    def Reset_search_results_and_extract(self) -> None:
        # Clear search state
        self.matches = []
        self.current_index = 0
        setattr(self, "matches_tab1", [])
        setattr(self, "matches_tab2", [])

        # Clear highlight (if any)
        try:
            self.Plist_file_viewer_text_area.tag_remove("highlight", "1.0", tk.END)
        except Exception:
            pass

        # Clear match counters on both tabs (if present)
        if hasattr(self, "search_match_count_label"):
            self.search_match_count_label.config(text="Matches: 0")
        if hasattr(self, "search_match_count_label_tab2"):
            self.search_match_count_label_tab2.config(text="Matches: 0")

        # Disable extract buttons (if present)
        if hasattr(self, "search_extract_matches_button"):
            self.search_extract_matches_button.config(state="disabled")
        if hasattr(self, "search_extract_matches_button_tab2"):
            self.search_extract_matches_button_tab2.config(state="disabled")

        # Clear extract frame content
        try:
            self.Selected_PList_extract_text_area.delete("1.0", tk.END)
        except Exception:
            pass

    def _on_search_tab_changed(self, event=None) -> None:
        self.Reset_search_results_and_extract()

    def Created_tabs(self): #P0

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')

        # Tab 1 - Plist
        self.tab1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text='Create Debug PList')
        self.control_frame_tab1 = tk.PanedWindow(self.tab1, orient=tk.HORIZONTAL, sashwidth=0)
        self.control_frame_tab1.pack(fill=tk.BOTH, expand=True)
        self.left_frame_tab1 = tk.Frame(self.control_frame_tab1, width=700)
        self.right_frame_tab1 = tk.Frame(self.control_frame_tab1)
        self.control_frame_tab1.add(self.left_frame_tab1)
        self.control_frame_tab1.add(self.right_frame_tab1)
        self.control_frame_tab1.sash_place(0, 700, 0)

        # Tab 2 - Create Bundle
        self.tab2 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2, text='Bundle (Soon)')
        self.notebook.tab(self.tab2, state='disabled')
        self.control_frame_tab2 = tk.Frame(self.tab2)
        self.control_frame_tab2.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _get_active_search_tab_index(self) -> int:
        notebook = getattr(self, "search_frame_notebook", None)
        if notebook is None:
            return 0
        try:
            return int(notebook.index("current"))
        except Exception:
            return 0

    def _get_active_search_entry(self):
        return self.search_filter_user_input_text_tab2 if self._get_active_search_tab_index() == 0 else self.search_filter_user_input_text

    def Set_matches_count(self, count: int) -> None:
        label = self.search_match_count_label_tab2 if self._get_active_search_tab_index() == 0 else self.search_match_count_label
        label.config(text=f"Matches: {count}")

    def Set_extract_matches_button_state(self, enabled: bool, match_count: int | None = None) -> None:
        button = self.search_extract_matches_button_tab2 if self._get_active_search_tab_index() == 0 else self.search_extract_matches_button
        if button is None:
            return
        button.config(state="normal" if enabled else "disabled")
        
    def Select_user_section(self, parent):  # P0
        user_frame = ttk.Frame(parent, relief="solid", borderwidth=1)
        user_frame.pack(side=tk.TOP, fill='x', pady=5, padx=5)

        user_label = tk.Label(user_frame, text="User:")
        user_label.pack(side=tk.LEFT, padx=(20, 5))

        self.user_list = ttk.Combobox(user_frame, state="readonly")
        self.user_list.pack(side=tk.LEFT, pady=10, padx=5)
        self.user_manager.Load_users_from_json()

        edit_user_button = tk.Button(user_frame, text="Edit User", bg="lightgray", fg="black", width=15, command=self.user_manager.Edit_existing_user_P0)
        edit_user_button.pack(side=tk.RIGHT, pady=10, padx=(15, 30))

        add_user_button = tk.Button(user_frame, text="Add User", bg="lightgray", fg="black", width=15, command=self.user_manager.Add_new_user_P0)
        add_user_button.pack(side=tk.RIGHT, pady=10, padx=10)

    def Create_plist_file_viewer(self, parent):  # P0.5
        self.Right_frame_viewer = tk.Frame(parent)
        self.Right_frame_viewer.pack(fill=tk.BOTH, expand=True)

        self.file_path_label = tk.Label(self.Right_frame_viewer, text="", bg="#87CEEB", fg="black", padx=5, pady=5, font=("Arial", 12, "bold"))
        self.file_path_label.pack(side=tk.TOP, pady=5, fill='x')
        scrollbar = tk.Scrollbar(self.Right_frame_viewer)
        scrollbar.pack(side=tk.RIGHT, fill='y')

        self.Plist_file_viewer_text_area = tk.Text(self.Right_frame_viewer, wrap='word', width=110, height=40, yscrollcommand=scrollbar.set, bg="white", fg="black", insertbackground="black")
        self.Plist_file_viewer_text_area.pack(side=tk.TOP, expand=True, fill='both')
        scrollbar.config(command=self.Plist_file_viewer_text_area.yview)

        self.bottom_frame = tk.Frame(self.Right_frame_viewer, bg="#87CEEB", height=100)
        self.bottom_frame.pack(side=tk.BOTTOM, fill='x', pady=10)
        mode_switch = ttk.Checkbutton(self.bottom_frame, text="Night Mode", variable=self.night_mode, command=self.Toggle_day_night_mode)
        mode_switch.pack(pady=5)
              
    def Open_plist_section(self, parent): # P1
        open_frame = ttk.Frame(parent, relief="solid", borderwidth=1)
        open_frame.pack(side=tk.TOP, fill='x', pady=5, padx=5)

        select_debug_plist_label = tk.Label(open_frame, text="Select debug plist file", font=("Arial", 10, "bold"))
        select_debug_plist_label.pack(side=tk.TOP, fill='x', pady=(6, 4))

        style = ttk.Style()
        style.configure("OpenPlistTabs.TNotebook.Tab", padding=(40, 5))

        open_plist_notebook = ttk.Notebook(open_frame, style="OpenPlistTabs.TNotebook")
        open_plist_notebook.pack(side=tk.TOP, fill='x', padx=5, pady=(0, 6))

        cwf_tab = ttk.Frame(open_plist_notebook)
        open_plist_notebook.add(cwf_tab, text="CWF HDMXPATS")

        cwf_button_group = ttk.Frame(cwf_tab)
        cwf_button_group.pack(pady=10)
        cwf_mscncdxcc_button = tk.Button(cwf_button_group, text="MscnCdXCC", width=12, bg="lightgray", fg="black", command=self.Open_MscnCdXCC)
        cwf_mscncdxcc_button.pack(side=tk.LEFT, padx=5)
        cwf_mscncorexcc_button = tk.Button(cwf_button_group, text="MscnCoreXCC", width=12, bg="lightgray", fg="black", command=self.Open_MscnCoreXCC)
        cwf_mscncorexcc_button.pack(side=tk.LEFT, padx=5)

        open_file_tab = ttk.Frame(open_plist_notebook)
        open_plist_notebook.add(open_file_tab, text="Open File")

        open_file_button_group = ttk.Frame(open_file_tab)
        open_file_button_group.pack(pady=10)
        plist_file_open_button = tk.Button(open_file_button_group, text="Browse", width=11, bg="lightgray", fg="black", command=self.Open_PLIST_File)
        plist_file_open_button.pack()
        
        spacer = tk.Frame(parent, height=1)
        spacer.pack(fill='x', pady=1)

    def Search_section(self, parent): # P2
        style = ttk.Style()
        style.configure("SearchTabs.TNotebook.Tab", padding=(87, 5), background="lightgray")
        style.map("SearchTabs.TNotebook.Tab",background=[("active", "!selected", "lightblue"),("selected", "royal blue"),("!selected", "lightgray"),],)

        self.search_frame_notebook = ttk.Notebook(parent, style="SearchTabs.TNotebook")
        self.search_frame_notebook.pack(side=tk.TOP, fill='x', pady=6, padx=10)
        self.search_frame_notebook.bind("<<NotebookTabChanged>>", self._on_search_tab_changed)

        search_frame_1 = ttk.Frame(self.search_frame_notebook, relief="solid", borderwidth=1)
        self.search_frame_notebook.add(search_frame_1, text="Searching for PLB IO by equivalent IE")
        search_frame_2 = ttk.Frame(self.search_frame_notebook, relief="solid", borderwidth=1)
        self.search_frame_notebook.add(search_frame_2, text="Searching using regex")

        # Tab 1 - Search
        search_title_label = tk.Label(search_frame_2, text="Search by Plist elements")
        search_title_label.pack(side=tk.TOP, pady=4) 
        search_filter_frame = tk.Frame(search_frame_2)
        search_filter_frame.pack(side=tk.TOP, fill='x', pady=4)
        search_filter_plist_label = tk.Label(search_filter_frame, text="PList:")
        search_filter_plist_label.pack(side=tk.LEFT, padx=5)
        search_entry_wrapper = tk.Frame(search_filter_frame)
        search_entry_wrapper.pack(side=tk.LEFT, fill='x', expand=True, padx=10)
        
        self.search_filter_user_input_text = tk.Entry(search_entry_wrapper, font=("Arial", 12), justify="center", width=55)
        self.search_filter_user_input_text.pack(fill='x', expand=True, ipady=5)
        tooltip_icon = tk.Label(search_filter_frame, text="🛈", font=("Arial", 25), fg="royal blue")
        tooltip_icon.pack(side=tk.LEFT, padx=10)
        ToolTip(tooltip_icon, "Use * for flexible search.\nExample: inf*atpg*ph1.")

        unified_button_row = tk.Frame(search_frame_2)
        unified_button_row.pack(side=tk.TOP, pady=6) 
        search_button = tk.Button(unified_button_row, text="Search", bg="lightgray", fg="black", width=7,command=self.Find_matches_search_main_global_PList)
        search_button.pack(side=tk.LEFT, padx=5)
        search_clear_button = tk.Button(unified_button_row, text="Clear", bg="lightgray", fg="black", width=7,command=self.Clear_search_partition_PList_area)
        search_clear_button.pack(side=tk.LEFT, padx=5)
        separator1 = tk.Frame(unified_button_row, width=2, height=30, bg="gray")
        separator1.pack(side=tk.LEFT, padx=10)
        self.search_extract_matches_button = tk.Button(unified_button_row, text="Extract Matches", bg="lightgray", fg="black", width=15,command=self.Extract_selected_matches)
        self.search_extract_matches_button.pack(side=tk.LEFT, padx=5)
        separator2 = tk.Frame(unified_button_row, width=2, height=30, bg="gray")
        separator2.pack(side=tk.LEFT, padx=10)
        search_previous_button = tk.Button(unified_button_row, text="←", bg="lightgray", fg="black", width=3,command=self.Previous_match_search_main_global_PList)
        search_previous_button.pack(side=tk.LEFT, padx=5)
        self.search_match_count_label = tk.Label(unified_button_row, text="Matches: 0")
        self.search_match_count_label.pack(side=tk.LEFT, padx=10)
        search_next_button = tk.Button(unified_button_row, text="→", bg="lightgray", fg="black", width=3,command=self.Next_match_search_main_global_PList)
        search_next_button.pack(side=tk.LEFT, padx=5)
        
        # Tab 2 - Search
        search_title_label_2 = tk.Label(search_frame_1, text="Search by GlobalPList elements")
        search_title_label_2.pack(side=tk.TOP, pady=4) 
        search_filter_frame_2 = tk.Frame(search_frame_1)
        search_filter_frame_2.pack(side=tk.TOP, fill='x', pady=4)
        search_filter_plist_label_2 = tk.Label(search_filter_frame_2, text="PList:")
        search_filter_plist_label_2.pack(side=tk.LEFT, padx=5)
        self.search_entry_wrapper_2 = tk.Frame(search_filter_frame_2)
        self.search_entry_wrapper_2.pack(side=tk.LEFT, fill='x', expand=True, padx=10)

        self.search_filter_user_input_text_tab2 = tk.Entry(self.search_entry_wrapper_2, font=("Arial", 12), justify="center", width=55)
        self.search_filter_user_input_text_tab2.pack(fill='x', expand=True, ipady=5)
        tooltip_icon_2 = tk.Label(search_filter_frame_2, text="🛈", font=("Arial", 25), fg="royal blue")
        tooltip_icon_2.pack(side=tk.LEFT, padx=10)
        ToolTip(tooltip_icon_2, "Enter the equivalent IE to search for the IO plist.\nExample:scn_c_inf_x_begin_sEs_edt_IEvinfra1_atpg_list\nIO Equivalent: scn_c_inf_x_begin_sSs_edt_vinfra1_atpg_list")

        unified_button_row_2 = tk.Frame(search_frame_1)
        unified_button_row_2.pack(side=tk.TOP, pady=6)
        self.search_button_tab2 = tk.Button(unified_button_row_2, text="Search", bg="lightgray", fg="black", width=7, command=self.Get_IO_Plist)
        self.search_button_tab2.pack(side=tk.LEFT, padx=5)
        self.search_clear_button_tab2 = tk.Button(unified_button_row_2,text="Clear",bg="lightgray",fg="black",width=7,command=self.Clear_search_partition_PList_area)
        self.search_clear_button_tab2.pack(side=tk.LEFT, padx=5)

        separator1_2 = tk.Frame(unified_button_row_2, width=2, height=30, bg="gray")
        separator1_2.pack(side=tk.LEFT, padx=10)
        self.search_extract_matches_button_tab2 = tk.Button(unified_button_row_2, text="Extract Matches", bg="lightgray", fg="black", width=15,command=self.Extract_selected_matches_IO)
        self.search_extract_matches_button_tab2.pack(side=tk.LEFT, padx=5)

        separator2_2 = tk.Frame(unified_button_row_2, width=2, height=30, bg="gray")
        separator2_2.pack(side=tk.LEFT, padx=10)
        self.search_previous_button_tab2 = tk.Button(unified_button_row_2, text="←", bg="lightgray", fg="black", width=3,command=self.Previous_match_search_main_global_PList)
        self.search_previous_button_tab2.pack(side=tk.LEFT, padx=5)
        self.search_match_count_label_tab2 = tk.Label(unified_button_row_2, text="Matches: 0")
        self.search_match_count_label_tab2.pack(side=tk.LEFT, padx=10)
        self.search_next_button_tab2 = tk.Button(unified_button_row_2, text="→", bg="lightgray", fg="black", width=3,command=self.Next_match_search_main_global_PList)
        self.search_next_button_tab2.pack(side=tk.LEFT, padx=5)

        # Start with extract disabled until a search runs
        try:
            self.search_extract_matches_button.config(state="disabled")
        except Exception:
            pass
        try:
            self.search_extract_matches_button_tab2.config(state="disabled")
        except Exception:
            pass

        spacer = tk.Frame(parent, height=1)
        spacer.pack(fill='x', pady=3)

    def Extract_section(self, parent): # P3
        extract_frame = ttk.Frame(parent, relief="solid", borderwidth=1)
        extract_frame.pack(side=tk.TOP, fill='both', expand=True, pady=5, padx=5)
        label_frame = tk.Frame(extract_frame)
        label_frame.pack(side=tk.TOP, pady=5)

        label_frame.grid_columnconfigure(0, weight=1, uniform="extract_header")
        label_frame.grid_columnconfigure(1, weight=1, uniform="extract_header")
        label_frame.grid_columnconfigure(2, weight=1, uniform="extract_header")
        label_frame.grid_columnconfigure(3, weight=1, uniform="extract_header")

        base_font = tkfont.nametofont("TkDefaultFont")
        base_size = int(base_font.cget("size"))
        extract_label_size = base_size + 1 if base_size > 0 else base_size - 1
        extract_label_font = tkfont.Font(
            root=self.root,
            family=base_font.actual().get("family"),
            size=extract_label_size,
        )

        extract_label = tk.Label(label_frame, text="PList to Extract:", font=extract_label_font)
        extract_label.grid(row=0, column=0, padx=10, pady=2)

        append_selection_button = tk.Button(label_frame, text="Append Selection", width=15, bg="lightgray", fg="black", command=self.Append_current_selection)
        append_selection_button.grid(row=0, column=1, padx=10, pady=2)

        extract_clear_button = tk.Button(label_frame, text="Clear Selection", width=13, bg="lightgray", fg="black", command=self.Clear_text_area_PList_to_extract)
        extract_clear_button.grid(row=0, column=2, padx=10, pady=2)

        tooltip_icon = tk.Label(label_frame, text="🛈", font=("Arial", 24), fg="royal blue")
        tooltip_icon.grid(row=0, column=3, padx=10, pady=2)
        ToolTip(tooltip_icon, "You can also copy from the window on the \nright and paste it directly here manually.\n\nUse 'Append Selection' to save current content\nbefore doing another search and extraction.")

        text_scroll_frame = tk.Frame(extract_frame)
        text_scroll_frame.pack(side=tk.TOP, fill='both', expand=True, pady=5, padx=5)
        extract_scrollbar = tk.Scrollbar(text_scroll_frame)
        extract_scrollbar.pack(side=tk.RIGHT, fill='y')
        self.Selected_PList_extract_text_area = tk.Text(text_scroll_frame, wrap='word', yscrollcommand=extract_scrollbar.set, bg="white", fg="black", insertbackground="black", width=70)
        self.Selected_PList_extract_text_area.pack(side=tk.LEFT, fill='both', expand=True)
        extract_scrollbar.config(command=self.Selected_PList_extract_text_area.yview)

        self.include_preburst.set(True)
        include_preburst_check = ttk.Checkbutton(extract_frame, text="Include PreBurstPList", variable=self.include_preburst)
        include_preburst_check.pack(side=tk.TOP, pady=5)
        spacer = tk.Frame(parent, height=1)
        spacer.pack(fill='x', pady=1)

    def Create_PList_debug_section(self, parent):  # P4
        debug_frame = ttk.LabelFrame(parent, text="Create Debug PList", relief="solid", borderwidth=1)
        debug_frame.pack(side=tk.TOP, fill='x', pady=5, padx=5)
        grid_frame = tk.Frame(debug_frame)
        grid_frame.pack(side=tk.TOP, pady=10)

        custom_name_label = tk.Label(grid_frame, text="Custom Text\nin Plb Name:")
        custom_name_label.grid(row=0, column=0, pady=(0,5), padx=10)
        self.custom_name_entry = tk.Entry(grid_frame, textvariable=self.custom_name_plb, width=20, justify='center')
        self.custom_name_entry.insert(0, "")
        self.custom_name_entry.grid(row=0, column=1, pady=(0,5), padx=(10,20))

        use_debug_check = tk.Checkbutton(grid_frame, text='Use "debug"\nas default', variable=self.use_debug_default, command=self.Toggle_custom_name_entry)
        use_debug_check.grid(row=0, column=2, pady=(0,5), padx=(20,30))
        generate_button = tk.Button(grid_frame, text="Generate\nDebug PList", height=2, width=16, bg="lightgray", fg="black", command=self._on_generate_debug_plb)
        generate_button.grid(row=0, column=3, pady=(0,5), padx=20)
        self.Toggle_custom_name_entry()

        spacer = tk.Frame(parent, height=1)
        spacer.pack(fill='x', pady=1)

    def Goto_bundle_section(self, parent, notebook, tab2):  # P5
        bundle_button_frame = ttk.Frame(parent, relief="solid", borderwidth=1)
        bundle_button_frame.pack(side=tk.TOP, fill='x', padx=5, pady=5)
        bundle_controls_row = tk.Frame(bundle_button_frame)
        bundle_controls_row.pack(side=tk.TOP, pady=5)

        self.use_previous_plist = tk.BooleanVar(value=True)
        continue_with_previous_check = ttk.Checkbutton(bundle_controls_row, text="Continue to the Bundle section \nwith the current plist file", variable=self.use_previous_plist)
        continue_with_previous_check.pack(side=tk.LEFT, padx=(5, 30))
        goto_bundle_button = tk.Button(bundle_controls_row, text="Go to Bundle Tab", height=2, width=20, bg="lightgray", fg="black", command=lambda: notebook.select(tab2))
        goto_bundle_button.pack(side=tk.LEFT)

    def Create_bundle_section(self):  # P6
        split_frame = tk.Frame(self.control_frame_tab2)
        split_frame.pack(fill='both', expand=True)

        self.left_frame_bundle_tab2 = tk.Frame(split_frame)
        self.left_frame_bundle_tab2.pack(side=tk.LEFT, fill='both', expand=True)

        self.right_frame_bundle_tab2 = tk.Frame(split_frame)
        self.right_frame_bundle_tab2.pack(side=tk.RIGHT, fill='both', expand=True)

        bundle_frame_P6 = ttk.Frame(self.left_frame_bundle_tab2, relief="solid", borderwidth=1)
        bundle_frame_P6.pack(side=tk.TOP, fill='x', pady=10, padx=10)

        bundle_title_label = tk.Label(bundle_frame_P6, text="Bundle Section", font=("Arial", 14, "bold"))
        bundle_title_label.pack(side=tk.TOP, pady=10)

        #######################         User Information        #######################        
        self.User_info_frame_P6 = ttk.LabelFrame(bundle_frame_P6, text="User Information")
        self.User_info_frame_P6.pack(side=tk.TOP, fill='x', padx=10, pady=(5, 10))
        self.Load_user_info_for_bundle_section_P6(self.User_info_frame_P6)

        #######################         Bundle Configuration        ####################### 
        Bundle_config_frame_P6 = ttk.LabelFrame(bundle_frame_P6, text="Bundle Configuration")
        Bundle_config_frame_P6.pack(side=tk.TOP, fill='x', padx=10, pady=10)

        # Folder name
        row_bundle_name = tk.Frame(Bundle_config_frame_P6)
        row_bundle_name.pack(fill='x', pady=2, padx=10)
        tk.Label(row_bundle_name, text="Folder name for the new bundle:", width=25, anchor='w').pack(side=tk.LEFT)
        self.bundle_name_entry = tk.Entry(row_bundle_name, width=40)
        self.bundle_name_entry.pack(side=tk.LEFT, padx=5)

        # Debug Plist
        row_debug_plist = tk.Frame(Bundle_config_frame_P6)
        row_debug_plist.pack(fill='x', pady=2, padx=10)
        tk.Label(row_debug_plist, text="Debug Plist file:", width=25, anchor='w').pack(side=tk.LEFT)
        self.debug_plist_path_generated = tk.Label(row_debug_plist, text="No file selected", anchor='w', fg="blue", width=60)
        self.debug_plist_path_generated.pack(side=tk.LEFT, padx=5)
        self.open_debug_plist_button = tk.Button(row_debug_plist, text="Browse", command=self.Open_debug_plist_for_bundle)
        self.open_debug_plist_button.pack(side=tk.RIGHT, padx=10)

        # Project
        row_project = tk.Frame(Bundle_config_frame_P6)
        row_project.pack(fill='x', pady=2, padx=10)
        tk.Label(row_project, text="Project:", width=25, anchor='w').pack(side=tk.LEFT)
        self.project_var = tk.StringVar(value=self.favorite_project)
        self.project_combobox = ttk.Combobox(row_project, textvariable=self.project_var, values=self.available_projects, width=40)
        self.project_combobox.pack(side=tk.LEFT, padx=5)

        # Die
        row_die = tk.Frame(Bundle_config_frame_P6)
        row_die.pack(fill='x', pady=2, padx=10)
        tk.Label(row_die, text="Die:", width=25, anchor='w').pack(side=tk.LEFT)
        self.die_var = tk.StringVar(value=self.favorite_die)
        self.die_combobox = ttk.Combobox(row_die, textvariable=self.die_var, values=self.available_dies, width=40)
        self.die_combobox.pack(side=tk.LEFT, padx=5)

        #######################         Bundle Command        ####################### 
        Bundle_command_frame_P6 = ttk.LabelFrame(bundle_frame_P6, text="Bundle Command")
        Bundle_command_frame_P6.pack(side=tk.TOP, fill='x', padx=10, pady=15)
        command_container = tk.Frame(Bundle_command_frame_P6)
        command_container.pack(fill='x', padx=10, pady=10)

        # Comando dinámico
        self.Generate_bundle_command(command_container)

        # Botón para copiar comando
        copy_button = tk.Button(command_container, text="Copy Command", command=self.Copy_bundle_command_to_clipboard)
        copy_button.pack(side=tk.RIGHT, padx=10)

        print_realpath_button = tk.Button(command_container, text="Print Realpath", command=lambda: self.Print_realpath(self.User_BundleFolder))
        print_realpath_button.pack(side=tk.RIGHT, padx=10)

        # Actualizaciones dinámicas
        self.project_var.trace_add("write", self.Update_die_options_P6)
        self.project_var.trace_add("write", lambda *args: self.Generate_bundle_command(command_container))
        self.die_var.trace_add("write", lambda *args: self.Generate_bundle_command(command_container))

    def PowerShell_subprocess_manager(self, parent_frame): #P7

        terminal_frame = ttk.LabelFrame(parent_frame, text="PowerShell Terminal")
        terminal_frame.pack(fill='both', expand=True, padx=10, pady=10)
        self.terminal_output = tk.Text(terminal_frame, height=20, wrap='word',bg='black', fg='white', insertbackground='white',state='disabled')
        self.terminal_output.pack(fill='both', expand=True, padx=5, pady=5)

        command_entry_frame = tk.Frame(terminal_frame)
        command_entry_frame.pack(fill='x', padx=5, pady=5)
        self.powershell_entry = tk.Entry(command_entry_frame)
        self.powershell_entry.pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 5))
        self.powershell_entry.bind("<Return>", self.Execute_PowerShell_Command)

        run_button = tk.Button(command_entry_frame, text="Run", command=self.Execute_PowerShell_Command)
        run_button.pack(side=tk.RIGHT)

    def Setup_App(self):
        log_file = "setup_errors.log"

        def log_error(section_name, error):
            with open(log_file, "a") as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] Error in {section_name}: {error}\n")

        print("Running Setup...")

        try:
            self.Created_tabs()
        except Exception as e:
            log_error("Created_tabs", traceback.format_exc())

        try:
            self.Select_user_section(self.left_frame_tab1)
        except Exception as e:
            log_error("Select_user_section", traceback.format_exc())

        try:
            self.Create_plist_file_viewer(self.right_frame_tab1)
        except Exception as e:
            log_error("Create_plist_file_viewer", traceback.format_exc())

        try:
            self.Open_plist_section(self.left_frame_tab1)
        except Exception as e:
            log_error("Open_plist_section", traceback.format_exc())

        try:
            self.Search_section(self.left_frame_tab1)
        except Exception as e:
            log_error("Search_section", traceback.format_exc())

        try:
            self.Extract_section(self.left_frame_tab1)
        except Exception as e:
            log_error("Extract_section", traceback.format_exc())

        try:
            self.Create_PList_debug_section(self.left_frame_tab1)
        except Exception as e:
            log_error("Create_PList_debug_section", traceback.format_exc())

        try:
            self.Goto_bundle_section(self.left_frame_tab1, self.notebook, self.tab2)
        except Exception as e:
            log_error("Goto_bundle_section", traceback.format_exc())

        try:
            self.Create_bundle_section()
        except Exception as e:
            log_error("Create_bundle_section", traceback.format_exc())

        try:
            self.PowerShell_subprocess_manager(self.right_frame_bundle_tab2)
        except Exception as e:
            log_error("PowerShell_subprocess_manager", traceback.format_exc())

        print("Setup Ok")

##############################      FUNCTIONS       ##############################

    def Create_user_window_popup(self, title, width=450, height=250): # P0
        popup = tk.Toplevel(self.root)
        popup.title(title)
        popup.configure(bg="lightgray")
        popup.geometry(f"{width}x{height}")
        popup.update_idletasks()
        x = (popup.winfo_screenwidth() // 2) - (width // 2)
        y = (popup.winfo_screenheight() // 2) - (height // 2)
        popup.geometry(f"+{x}+{y}")
        return popup

    def Create_user_window_label_entrys(self, parent, label_text, initial_value="", tooltip_text=None): # P0
        row = tk.Frame(parent, bg="lightgray")
        row.pack(fill='x', pady=5)
        tk.Label(row, text=label_text, width=18, anchor='w', bg="lightgray").pack(side=tk.LEFT)
        entry = tk.Entry(row, width=45)
        entry.insert(0, initial_value)
        entry.pack(side=tk.RIGHT, expand=True, fill='x')
        if tooltip_text:
            ToolTip(entry, tooltip_text)
        return entry

    def Create_user_window_dropdown(self, parent, label_text, variable, values): # P0
        row = tk.Frame(parent, bg="lightgray")
        row.pack(fill='x', pady=5)
        tk.Label(row, text=label_text, width=18, anchor='w', bg="lightgray").pack(side=tk.LEFT)
        dropdown = ttk.Combobox(row, textvariable=variable, values=values, state="readonly", width=42)
        dropdown.pack(side=tk.RIGHT, fill='x')
        return dropdown

    def Create_user_window_save_button(self, parent, command): # P0
        tk.Button(parent, text="Save", bg="dodger blue", fg="white",
                  font=("Arial", 10, "bold"), command=command,
                  width=10, height=2).pack(pady=(0, 20))

        
    def Set_day_mode(self):  # P1
        self.Plist_file_viewer_text_area.config(bg="white", fg="black", insertbackground="black")
        self.Selected_PList_extract_text_area.config(bg="white", fg="black", insertbackground="black")
        self.search_filter_user_input_text.config(bg="white", fg="black", insertbackground="black")
        self.search_filter_user_input_text_tab2.config(bg="white", fg="black", insertbackground="black")

        
    def Set_night_mode(self):  # P1
        self.Plist_file_viewer_text_area.config(bg="black", fg="white", insertbackground="white")
        self.Selected_PList_extract_text_area.config(bg="black", fg="white", insertbackground="white")
        self.search_filter_user_input_text.config(bg="black", fg="white", insertbackground="white")
        self.search_filter_user_input_text_tab2.config(bg="black", fg="white", insertbackground="white")

    def Toggle_day_night_mode(self):  # P1
        if self.night_mode.get():
            self.Set_night_mode()
            self.Plist_file_viewer_text_area.tag_config("highlight", background="deep sky blue")
        else:
            self.Set_day_mode()
            self.Plist_file_viewer_text_area.tag_config("highlight", background="yellow")

    def Load_plist_file(self, path, label_prefix="File"): #P1
        try:
            with open(path, 'r') as file:
                self.content = file.read()
                self.Plist_file_viewer_text_area.delete(1.0, tk.END)
                self.Plist_file_viewer_text_area.insert(tk.END, self.content)
            self.current_index = 0
            self.matches = []
            self.file_path_label.config(text=f"{label_prefix}: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"The file could not be opened:\n{e}")

    def Open_PLIST_File(self): #P1
        self.file_path = filedialog.askopenfilename(filetypes=[("PLIST Files", "*.plist")])
        if self.file_path:
            self.Load_plist_file(self.file_path, label_prefix="PList File")

    def Open_HDMXPATHS_Folder(self, initial_folder): #P1
        self.file_path = filedialog.askopenfilename(initialdir=initial_folder, filetypes=[("PLIST Files", "*.plist")])
        if self.file_path:
            self.Load_plist_file(self.file_path)
    
    def Find_network_drive_path(self, relative_path): #P1
        """
        Find the correct network drive letter for a given path.
        Searches from I: to Z: and caches the result.
        
        Args:
            relative_path: Path relative to drive letter (e.g., 'hdmxpats\\cwf\\MscnCdXCC')
        
        Returns:
            Full path with correct drive letter, or None if not found
        """
        # Check cache first
        if relative_path in self.network_drive_cache:
            cached_path = self.network_drive_cache[relative_path]
            if os.path.exists(cached_path):
                return cached_path
        
        # Search for the path in available drives, starting with I:
        drives_to_check = ['I'] + [chr(i) for i in range(ord('J'), ord('Z')+1)]
        
        for drive_letter in drives_to_check:
            full_path = f"{drive_letter}:\\{relative_path}"
            if os.path.exists(full_path):
                # Cache the found path
                self.network_drive_cache[relative_path] = full_path
                
                # Notify user if alternate drive was used
                if drive_letter != 'I':
                    print(f"Info: Using network drive {drive_letter}: instead of I: for {relative_path}")
                    messagebox.showinfo(
                        "Network Drive Info",
                        f"Using network drive {drive_letter}: instead of I:\n\n"
                        f"Path: {full_path}\n\n"
                        f"This selection will be remembered for this session."
                    )
                
                return full_path
        
        # Path not found in any drive
        messagebox.showerror(
            "Path Not Found",
            f"Could not find path '{relative_path}' in any network drive (I: to Z:).\n\n"
            f"Please ensure the network drive is mounted and accessible."
        )
        return None
     
    def Open_MscnCdXCC(self): #P1
        path = self.Find_network_drive_path(r"hdmxpats\cwf\MscnCdXCC")
        if path:
            self.Open_HDMXPATHS_Folder(path)

    def Open_MscnCoreXCC(self): #P1
        path = self.Find_network_drive_path(r"hdmxpats\cwf\MscnCoreXCC")
        if path:
            self.Open_HDMXPATHS_Folder(path)

    def Clear_search_partition_PList_area(self): #P2
        entry = self._get_active_search_entry()
        entry.delete(0, tk.END)
        entry.focus_set()
        
    def Next_match_search_main_global_PList(self): #P2
        if self.matches:
            self.current_index = (self.current_index + 1) % len(self.matches)
            self.Highlight_matches_search_main_global_PList()

    def Previous_match_search_main_global_PList(self): #P2
        if self.matches:
            self.current_index = (self.current_index - 1) % len(self.matches)
            self.Highlight_matches_search_main_global_PList()
        
    def Highlight_matches_search_main_global_PList(self):  # P2
        self.Plist_file_viewer_text_area.tag_remove("highlight", "1.0", tk.END)
        if self.matches:
            start, _ = self.matches[self.current_index]
            line_start = f"{start.split('.')[0]}.0"
            line_end = f"{start.split('.')[0]}.end"
            self.Plist_file_viewer_text_area.tag_add("highlight", line_start, line_end)

            highlight_color = "deep sky blue" if self.night_mode.get() else "yellow"
            self.Plist_file_viewer_text_area.tag_config("highlight", background=highlight_color)

            self.Plist_file_viewer_text_area.see(line_start)

    def Clear_text_area_PList_to_extract(self): #P3
        self.Selected_PList_extract_text_area.delete("1.0", tk.END) #Clear the content of the 'PList to Extract' text area
        self.appended_plist_content = "" #Clear appended content as well

    def Append_current_selection(self): #P3
        """
        Save the current content from Selected_PList_extract_text_area
        to preserve it across multiple Extract Matches operations.
        """
        current_content = self.Selected_PList_extract_text_area.get("1.0", "end-1c").strip()
        if current_content:
            if self.appended_plist_content:
                # If there's already appended content, add separator and new content
                self.appended_plist_content += "\n" + current_content
            else:
                # First time appending
                self.appended_plist_content = current_content
            messagebox.showinfo("Success", "Current selection has been saved.\n\nFuture extractions will be appended to this saved content.")
        else:
            messagebox.showwarning("Warning", "No content to append. Please extract matches first.")

    def _on_generate_debug_plb(self):  # P4
        self.extractor.Extract_selected_PList()
        return self.generator.Generate_debug_plb()

    def Toggle_custom_name_entry(self): # P4
        if self.use_debug_default.get():
            self.custom_name_entry.config(state='disabled')
        else:
            self.custom_name_entry.config(state='normal')

    def Load_user_info_for_bundle_section_P6(self, parent_frame):  # P6
        
        for widget in parent_frame.winfo_children():
            widget.destroy()
        selected_user = self.user_list.get()
        user_info = self.user_data.get("users", {}).get(selected_user, {})

        self.user_config_values = {
            "Username": selected_user,
            "PListDebugFolder": user_info.get("PListDebugFolder", ""),
            "BundleFolder": user_info.get("BundleFolder", "")
        }

        self.user_info_display = {}

        row_username = tk.Frame(parent_frame)
        row_username.pack(fill='x', pady=2, padx=10)
        tk.Label(row_username, text="Username:", width=22, anchor='w').pack(side=tk.LEFT)
        tk.Label(row_username, text=selected_user, anchor='w', fg="blue").pack(side=tk.LEFT)

        row_debug = tk.Frame(parent_frame)
        row_debug.pack(fill='x', pady=2, padx=10)
        tk.Label(row_debug, text="Folder for PList Debug:", width=22, anchor='w').pack(side=tk.LEFT)
        debug_label = tk.Label(row_debug, text=self.user_config_values["PListDebugFolder"] or "N/A", anchor='w', fg="blue")
        debug_label.pack(side=tk.LEFT)
        tk.Button(row_debug, text="Browse", command=lambda: self.Bundle_folder_browse_and_update_P6(debug_label, "PListDebugFolder")).pack(side=tk.LEFT, padx=5)
        self.user_info_display["PListDebugFolder"] = debug_label

        row_bundle = tk.Frame(parent_frame)
        row_bundle.pack(fill='x', pady=2, padx=10)
        tk.Label(row_bundle, text="Folder for Bundle:", width=22, anchor='w').pack(side=tk.LEFT)
        bundle_label = tk.Label(row_bundle, text=self.user_config_values["BundleFolder"] or "N/A", anchor='w', fg="blue")
        bundle_label.pack(side=tk.LEFT)
        tk.Button(row_bundle, text="Browse", command=lambda: self.Bundle_folder_browse_and_update_P6(bundle_label, "BundleFolder")).pack(side=tk.LEFT, padx=5)
        self.user_info_display["BundleFolder"] = bundle_label

        self.User_username = selected_user
        self.User_PListDebugFolder = self.user_config_values["PListDebugFolder"]
        self.User_BundleFolder = self.user_config_values["BundleFolder"]
    
    def Make_new_bundle_folder(self,event=None):  # P6
        try:
            folder_name = self.bundle_name_entry.get().strip()
            invalid_chars = r'[<>:"/\\|?*]' 

            if not folder_name:
                raise ValueError("The bundle name is empty.")

            if re.search(invalid_chars, folder_name):
                messagebox.showerror("Invalid Name", "The folder name contains invalid characters.")
                return

            if not self.User_BundleFolder:
                messagebox.showwarning("Missing Path", "Please select a base folder first.")
                return
            new_folder_path = os.path.join(self.User_BundleFolder, folder_name)
            self.Sub_Bundle_Folder_Path = new_folder_path
            if os.path.exists(new_folder_path):
                messagebox.showinfo("Already Exists", f"The folder already exists:\n{new_folder_path}")
            else:
                os.makedirs(new_folder_path)
                messagebox.showinfo("Success", f"Folder created at:\n{new_folder_path}")

        except ValueError as ve:
            messagebox.showwarning("Missing Name", str(ve))
        except Exception as e:
            messagebox.showerror("Error", f"Could not create folder:\n{e}")      
    
    def Bundle_folder_browse_and_update_P6(self, label_widget, key_name): #P6
        selected_folder = filedialog.askdirectory()
        if selected_folder:
            label_widget.config(text=selected_folder)
            self.user_config_values[key_name] = selected_folder
       
    def Open_debug_plist_for_bundle(self): #P6
        initial_dir = self.User_PListDebugFolder if self.User_PListDebugFolder else os.getcwd()
        file_path = filedialog.askopenfilename(
            initialdir=initial_dir,
            title="Select Debug Plist File",
            filetypes=(("Property List files", "*.plist"), ("All files", "*.*"))
        )
        if file_path:
            self.debug_plist_path_generated.config(text=file_path)
    
    def Update_die_options_P6(self, *args): #P6
        selected_project = self.project_var.get()
        dies_by_project = self.user_data.get("definitions", {}).get("Dies", {})
        new_dies = dies_by_project.get(selected_project, ["NA"])
        self.die_combobox['values'] = new_dies
        if self.die_var.get() not in new_dies:
            self.die_var.set(new_dies[0])
        
    def Generate_bundle_command(self, parent_frame): #P6
        selected_project = self.project_var.get().lower()
        selected_die = self.die_var.get()

        if selected_die == "Top Die":
            die_value = "MscnCoreXCC"
        elif selected_die == "Base Die":
            die_value = "MscnCdXCC"
        else:
            die_value = "UnknownDie"

        destpath = f"/nfs/cr/disks/mfg_hvmpats_032/hdmxpats/{selected_project}/dev/rafaelja/ddrfmbb1_tatpg_debug"
        plistpath = f"/nfs/site/disks/mfg_{selected_project}_001/rafaelja/Bundles/ww40p4/ddrfmbb1_tatpg.plist"

        command_text = f"bundle_debug_pats.py -p {selected_project} -module {die_value} -tester hdmt2 -site CR -destpath {destpath} {plistpath}"

        if hasattr(self, "command_label"):
            self.command_label.config(text=command_text)
        else:
            self.command_label = tk.Label(
                parent_frame,
                text=command_text,
                anchor='w',
                justify='left',
                wraplength=700,
                fg="darkgreen"
            )
            self.command_label.pack(side=tk.LEFT, fill='x', expand=True)
            
    def Copy_bundle_command_to_clipboard(self): #P6
        if hasattr(self, "command_label"):
            command_text = self.command_label.cget("text")
            self.control_frame_tab2.clipboard_clear()
            self.control_frame_tab2.clipboard_append(command_text)
            self.control_frame_tab2.update() 
    
    def Print_realpath(self, folder_path):
        if folder_path:
            try:
                real_path = Path(folder_path).resolve()
                print(f"Resolved path: {real_path}")
                return str(real_path)
            except Exception as e:
                print(f"Error resolving path: {e}")
                return None
        else:
            print("No folder path provided.")
            return None
            
    def Execute_PowerShell_Command(self, event=None):  # P7
        command = self.powershell_entry.get()
        if not command.strip():
            return

        self.terminal_output.config(state='normal')
        self.terminal_output.insert(tk.END, f"> {command}\n")
        self.powershell_entry.delete(0, tk.END)

        try:
            result = subprocess.check_output(
                ["powershell", "-Command", command],
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.User_BundleFolder if self.User_BundleFolder else None #Set initial folder
            )
        except subprocess.CalledProcessError as e:
            result = e.output
        except Exception as ex:
            result = str(ex)

        self.terminal_output.insert(tk.END, result + "\n")
        self.terminal_output.see(tk.END)
        self.terminal_output.config(state='disabled')

def main():
    print(getpass.getuser())
    root = tk.Tk()
    app = PlistTool(root)
    root.mainloop()         
    
if __name__ == "__main__":
    main()  