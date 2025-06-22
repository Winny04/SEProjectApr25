# user_logic.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from datetime import datetime, timedelta
import pandas as pd
import barcode
from barcode.writer import ImageWriter
import os
from firebase_setup import db
from constants import NOTIFICATION_DAYS_BEFORE, COLUMNS, SAMPLE_STATUS_OPTIONS
from tkcalendar import DateEntry
import firebase_admin

# --- Logging Setup ---
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- End Logging Setup ---

class UserLogic:
    def __init__(self, root, app_instance):
        self.root = root
        self.app = app_instance
        self.tree = None
        self.status_label = None
        self.excel_imported = False
        self.current_selected_batch_id = None

        # Initialize ttk Style
        self.style = ttk.Style()
        # Set a modern theme, e.g., 'clam', 'alt', 'vista', 'xpnative'
        self.style.theme_use('clam')

        # Configure general styles
        self.style.configure('TFrame', background='#f0f0f0')
        self.style.configure('TLabel', font=('Helvetica', 10), background='#f0f0f0', foreground='#333333')

        # Configure different button styles
        # Primary button (e.g., for major actions like Select Batch, Add Sample)
        self.style.configure('Primary.TButton', font=('Helvetica', 10, 'bold'), padding=8, background='#007bff',
                             foreground='white', relief='raised')
        self.style.map('Primary.TButton', background=[('active', '#0056b3')])  # Darken on hover

        self.style.configure('add.TButton', font=('Helvetica', 10, 'bold'), padding=8, background="#94e119",
                             foreground='white', relief='raised')
        self.style.map('add.TButton', background=[('active', "#0ee969")])

        # Secondary button (e.g., for less critical actions like Refresh, Check Notifications)
        self.style.configure('Secondary.TButton', font=('Helvetica', 10, 'bold'), padding=8, background='#6c757d',
                             foreground='white', relief='raised')
        self.style.map('Secondary.TButton', background=[('active', '#545b62')])

        # Success button (e.g., for actions that add or confirm)
        self.style.configure('Success.TButton', font=('Helvetica', 10, 'bold'), padding=8, background='#28a745',
                             foreground='white', relief='raised')
        self.style.map('Success.TButton', background=[('active', '#218838')])

        # Warning/Info button (e.g., for filters, generate barcode)
        self.style.configure('Info.TButton', font=('Helvetica', 10, 'bold'), padding=8, background='#17a2b8',
                             foreground='white', relief='raised')
        self.style.map('Info.TButton', background=[('active', '#138496')])

        # Danger button (e.g., for delete actions)
        self.style.configure('Danger.TButton', font=('Helvetica', 10, 'bold'), padding=8, background='#dc3545',
                             foreground='white', relief='raised')
        self.style.map('Danger.TButton', background=[('active', '#c82333')])

        # Configure Entry and Combobox styles
        self.style.configure('TEntry', padding=5)
        self.style.configure('TCombobox', padding=5)
        self.style.configure('TCheckbutton', background='#f0f0f0')
        self.style.configure('TRadiobutton', background='#f0f0f0')

        # Configure Treeview style
        self.style.configure('Treeview',
                             font=('Helvetica', 9),
                             rowheight=25,
                             fieldbackground='#ffffff',
                             background='#ffffff',
                             foreground='#000000',
                             bordercolor='#cccccc',
                             lightcolor='#eeeeee',
                             darkcolor='#bbbbbb'
                             )
        self.style.map('Treeview', background=[('selected', '#347083')])  # Blue selection
        self.style.configure('Treeview.Heading', font=('Helvetica', 10, 'bold'), background='#e0e0e0',
                             foreground='#333333')
        self.style.map('Treeview.Heading', background=[('active', '#d0d0d0')])

        # Elements for forms (will be created dynamically)
        self.existing_batch_combobox = None
        self.new_batch_product_name = None
        self.new_batch_description = None
        self.entry_sample_display_id = None
        self.entry_owner_combobox = None
        self.entry_maturation_date_entry = None
        self.status_combobox = None

        # Filter form elements
        self.filter_maturation_date_var = tk.BooleanVar(value=False)
        self.filter_creation_date_var = tk.BooleanVar(value=False)

        self.filter_start_date_entry = None
        self.filter_end_date_entry = None
        self.filter_creation_start_date_entry = None
        self.filter_creation_end_date_entry = None
        self.filter_sample_id_entry = None
        self.filter_batch_id_entry = None
        self.filter_product_name_entry = None
        self.filter_status_combobox = None

        self.filter_mode = tk.StringVar(value="samples")
        self.find_batch_id_entry = None
        self.find_sample_id_entry = None  # New: Entry for finding sample details
        self.sample_filters_frame = None
        self.batch_search_frame = None
        self.sample_search_frame = None  # New: Frame for sample search

        self.maturation_date_filter_frame = None
        self.creation_date_filter_frame = None

        # Pagination variables
        self.current_page_index = 0
        self.samples_per_page = 100
        self.all_samples_page_cursors = []
        self.my_samples_page_cursors = []
        self.batch_samples_page_cursors = []
        self.last_loaded_query_type = None

        # Pagination UI elements
        self.page_info_label = None
        self.prev_sample_page_btn = None
        self.next_sample_page_btn = None

        # Buttons that need their state controlled based on view type
        self.edit_sample_button = None
        self.delete_sample_button = None

        logging.info("UserLogic initialized.")

    def user_dashboard(self):
        """Displays the user dashboard with sample management features."""
        logging.info("Entering user_dashboard method.")
        self.app.clear_root()
        # Set root background color
        self.root.config(bg='#f0f0f0')
        self.root.geometry("1300x600")
        self.excel_imported = False
        self.current_selected_batch_id = None

        # Reset pagination state for all views
        self.current_page_index = 0
        self.all_samples_page_cursors = []
        self.my_samples_page_cursors = []
        self.batch_samples_page_cursors = []
        self.last_loaded_query_type = None

        # === Menu Bar ===
        menubar = tk.Menu(self.root)

        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Import Excel (Local/DB)", command=self.open_excel_import_options_form)
        filemenu.add_command(label="Export Excel (Local)", command=self.export_excel)
        menubar.add_cascade(label="File", menu=filemenu)

        loadmenu = tk.Menu(menubar, tearoff=0)
        loadmenu.add_command(label="Load All Samples",
                             command=lambda: self.load_samples_paginated('all_samples', reset=True))
        loadmenu.add_command(label="Load My Samples",
                             command=lambda: self.load_samples_paginated('my_samples', reset=True))
        loadmenu.add_separator()
        loadmenu.add_command(label="Load All Batches", command=self.load_all_batches_to_tree)
        loadmenu.add_command(label="Load My Batches", command=self.load_my_batches_to_tree)
        menubar.add_cascade(label="Load", menu=loadmenu)

        self.root.config(menu=menubar)

        # === Top Toolbar Frame for Buttons ===
        # Using 'Toolbar.TFrame' style for consistency
        toolbar_top = ttk.Frame(self.root, padding=(10, 10), style='TFrame')
        toolbar_top.pack(fill="x", padx=10, pady=(10, 0))  # Add some top padding

        # Use different button styles
        ttk.Button(toolbar_top, text="Logout", command=self.app.logout, style='Secondary.TButton').pack(side=tk.RIGHT,
                                                                                                        padx=5)
        ttk.Button(toolbar_top, text="Refresh", command=self.refresh_tree, style='Secondary.TButton').pack(
            side=tk.RIGHT, padx=5)
        ttk.Button(toolbar_top, text="Load Today's Batches", command=self.load_todays_batches_to_tree,
                   style='Secondary.TButton').pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar_top, text="Check Notifications", command=self.check_notifications,
                   style='Info.TButton').pack(side=tk.LEFT, padx=5)
        self.add_sample_main_button = ttk.Button(toolbar_top, text="Select Batch",
                                                 command=self.open_batch_selection_screen, style='Primary.TButton')
        self.add_sample_main_button.pack(side=tk.LEFT, padx=5)
        self.add_single_sample_button = ttk.Button(toolbar_top, text="Add Sample to Current Batch",
                                                   command=self.open_single_sample_form, state=tk.DISABLED,
                                                   style='add.TButton')
        self.add_single_sample_button.pack(side=tk.LEFT, padx=5)

        self.edit_sample_button = ttk.Button(toolbar_top, text="Edit Sample", command=self.edit_sample,
                                             style='Info.TButton')
        self.edit_sample_button.pack(side=tk.LEFT, padx=5)
        self.delete_sample_button = ttk.Button(toolbar_top, text="Delete Sample", command=self.delete_sample,
                                               style='Danger.TButton')
        self.delete_sample_button.pack(side=tk.LEFT, padx=5)

        # === Treeview Frame for Data Display with Scrollbar ===
        tree_frame = ttk.Frame(self.root, style='TFrame', relief='sunken', borderwidth=1)  # Added relief and border
        tree_frame.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Treeview configured with style 'Treeview'
        self.tree = ttk.Treeview(tree_frame,
                                 columns=["DocID", "DisplaySampleID", "Owner", "MaturationDate", "Status", "BatchID",
                                          "CreationDate", "ProductName", "Description", "SubmissionDate",
                                          "NumberOfSamples"], show='headings', style='Treeview')

        tree_scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scrollbar.set)

        self.tree.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        tree_scrollbar.pack(side=tk.RIGHT, fill='y')

        self.tree.heading("DocID", text="Doc ID")
        self.tree.column("DocID", width=0, stretch=tk.NO)

        self.tree.heading("DisplaySampleID", text="Sample ID")
        self.tree.column("DisplaySampleID", width=100, anchor="center")

        self.tree.heading("Owner", text="Sample Owner")
        self.tree.column("Owner", width=100, anchor="center")

        self.tree.heading("MaturationDate", text="Maturation Date")
        self.tree.column("MaturationDate", width=120, anchor="center")

        self.tree.heading("Status", text="Status")
        self.tree.column("Status", width=80, anchor="center")

        self.tree.heading("BatchID", text="Batch ID")
        self.tree.column("BatchID", width=120, anchor="center")

        self.tree.heading("CreationDate", text="Creation Date")
        self.tree.column("CreationDate", width=120, anchor="center")

        self.tree.heading("ProductName", text="Product Name")
        self.tree.column("ProductName", width=0, stretch=tk.NO)

        self.tree.heading("Description", text="Description")
        self.tree.column("Description", width=0, stretch=tk.NO)

        self.tree.heading("SubmissionDate", text="Submission Date")
        self.tree.column("SubmissionDate", width=0, stretch=tk.NO)

        self.tree.heading("NumberOfSamples", text="Num Samples")
        self.tree.column("NumberOfSamples", width=0, stretch=tk.NO)

        self.tree.bind("<Double-1>", self._on_tree_double_click)

        # === Status Bar ===
        self.status_label = ttk.Label(self.root, text="Load samples from DB or import Excel.", anchor='w',
                                      font=('Helvetica', 9), background='#e0e0e0', foreground='#333333',
                                      relief=tk.SUNKEN, borderwidth=1)
        self.status_label.pack(fill=tk.X, padx=10, pady=(5, 10))  # Add some bottom padding

        # === Bottom Toolbar Frame for Generate Barcode, Pagination, and Filter Button ===
        bottom_toolbar = ttk.Frame(self.root, padding=(10, 5), style='TFrame')
        bottom_toolbar.pack(fill="x", padx=10, pady=(0, 10), side=tk.BOTTOM)

        ttk.Button(bottom_toolbar, text="Generate Barcode", command=self.generate_barcode, style='Info.TButton').pack(
            side=tk.LEFT, padx=5)

        pagination_frame = ttk.Frame(bottom_toolbar, style='TFrame')
        pagination_frame.pack(side=tk.LEFT, expand=True)

        self.prev_sample_page_btn = ttk.Button(pagination_frame, text="Previous",
                                               command=lambda: self.navigate_samples_page('prev'), state=tk.DISABLED,
                                               style='Secondary.TButton')
        self.prev_sample_page_btn.pack(side=tk.LEFT, padx=2)

        self.page_info_label = ttk.Label(pagination_frame, text="Page 1 of 1", style='TLabel')
        self.page_info_label.pack(side=tk.LEFT, padx=5)

        self.next_sample_page_btn = ttk.Button(pagination_frame, text="Next",
                                               command=lambda: self.navigate_samples_page('next'), state=tk.DISABLED,
                                               style='Secondary.TButton')
        self.next_sample_page_btn.pack(side=tk.LEFT, padx=2)

        ttk.Button(bottom_toolbar, text="Filter Samples/Find Batch", command=self.open_filter_form,
                   style='Info.TButton').pack(side=tk.RIGHT, padx=5)

        self.load_samples_paginated(query_type='all_samples', reset=True)
        logging.info("User dashboard loaded.")

    def _on_tree_double_click(self, event):
        """Handles double-click events on the Treeview to load batch samples."""
        logging.info("Treeview double-click event detected.")
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return

        item_values = self.tree.item(item_id, 'values')

        if self.last_loaded_query_type in ['batches', 'my_batches', 'todays_batches']:
            # Check if BatchID is present in Treeview values (index 5) and is valid
            if len(item_values) > 1 and item_values[5] and item_values[5] != 'N/A':
                batch_id_from_tree = item_values[5]
                logging.info(f"Double-clicked on batch with ID: {batch_id_from_tree}")
                self.current_selected_batch_id = batch_id_from_tree
                self.load_samples_for_current_batch(reset=True)
            else:
                logging.warning("Double-clicked item is not recognized as a valid batch.")
                messagebox.showwarning("Invalid Item", "Please double-click on a valid batch row.")
        else:
            logging.info("Double-click ignored as current view is not batches or is a local/filtered sample view.")

    def load_samples_to_treeview(self, samples_list, is_pagination_load=False, current_page=1, total_pages=1):
        """Populates the Treeview widget with the given list of samples.
        Adjusts column visibility based on context (samples vs batches)."""
        logging.info(
            f"Populating samples treeview. Pagination Load: {is_pagination_load}, Current Page: {current_page}, Total Pages: {total_pages}")
        # Clear existing items for a fresh load
        self.tree.delete(*self.tree.get_children())
        # Reset DataFrame for new data
        self.app.data = pd.DataFrame(columns=COLUMNS + ["DocID"])

        # Define columns for samples and batches for visibility control
        sample_cols = ["DisplaySampleID", "Owner", "MaturationDate", "Status", "BatchID", "CreationDate"]
        batch_cols = ["ProductName", "Description", "SubmissionDate", "NumberOfSamples"]

        # Set sample-specific columns visible
        for col in sample_cols:
            self.tree.column(col, width=100 if col != "MaturationDate" else 120, stretch=tk.YES)
        # Hide batch-specific columns
        for col in batch_cols:
            self.tree.column(col, width=0, stretch=tk.NO)

        if samples_list:
            df = pd.DataFrame(samples_list)
            # Rename columns for consistent display in Treeview
            df.rename(columns={
                "firestore_doc_id": "DocID",
                "sample_id": "DisplaySampleID",
                "owner": "Owner",
                "maturation_date": "MaturationDate",
                "status": "Status",
                "batch_id": "BatchID",
                "creation_date": "CreationDate"
            }, inplace=True)

            # Add missing expected columns with None to ensure DataFrame structure
            for col in ["DocID", "DisplaySampleID", "Owner", "MaturationDate", "Status", "BatchID", "CreationDate"]:
                if col not in df.columns:
                    df[col] = None

            self.app.data = df

            # Insert data into the Treeview
            for index, row in df.iterrows():
                mat_date_str = "N/A"
                creation_date_str = "N/A"

                mat_date = row.get('MaturationDate')
                # Robustly convert maturation date to string format
                if mat_date is not None:
                    if hasattr(mat_date, 'to_datetime'):
                        mat_date_dt = mat_date.to_datetime()
                    elif isinstance(mat_date, datetime):
                        mat_date_dt = mat_date
                    else:
                        try:
                            mat_date_dt = datetime.strptime(str(mat_date).split(' ')[0], "%Y-%m-%d")
                        except ValueError:
                            mat_date_dt = None
                    if mat_date_dt:
                        mat_date_str = mat_date_dt.strftime("%Y-%m-%d")

                creation_date = row.get('CreationDate')
                # Robustly convert creation date to string format
                if creation_date is not None:
                    if hasattr(creation_date, 'to_datetime'):
                        creation_date_dt = creation_date.to_datetime()
                    elif isinstance(creation_date, datetime):
                        creation_date_dt = creation_date
                    else:
                        try:
                            creation_date_dt = datetime.strptime(str(creation_date).split(' ')[0], "%Y-%m-%d")
                        except ValueError:
                            creation_date_dt = None
                    if creation_date_dt:
                        creation_date_str = creation_date_dt.strftime("%Y-%m-%d")

                self.tree.insert("", tk.END,
                                 values=(row.get('DocID', ''),
                                         row.get('DisplaySampleID', ''),
                                         row.get('Owner', ''),
                                         mat_date_str,
                                         row.get('Status', ''),
                                         row.get('BatchID', 'N/A'),
                                         creation_date_str,
                                         '', '', '', ''))  # Empty values for hidden batch columns

            self.status_label.config(text=f"Loaded {len(self.app.data)} samples. Page {current_page} of {total_pages}.")
            self.page_info_label.config(text=f"Page {current_page} of {total_pages}")
        else:
            self.status_label.config(text="No samples found.")
            self.page_info_label.config(text="Page 0 of 0")
            logging.info("No samples to display.")

        # Update pagination button states based on current page and total pages
        self.prev_sample_page_btn.config(state=tk.NORMAL if current_page > 1 else tk.DISABLED)
        self.next_sample_page_btn.config(state=tk.NORMAL if current_page < total_pages else tk.DISABLED)

        # Enable Edit and Delete Sample buttons when samples are displayed
        if self.edit_sample_button:
            self.edit_sample_button.config(state=tk.NORMAL)
        if self.delete_sample_button:
            self.delete_sample_button.config(state=tk.NORMAL)

        logging.info("Samples treeview populated and pagination buttons updated.")

    def load_batches_to_treeview(self, batches_list):
        """Populates the Treeview widget with the given list of batches.
        Adjusts column visibility for batch display."""
        logging.info(f"Populating batches treeview with {len(batches_list)} batches.")
        self.tree.delete(*self.tree.get_children())
        self.app.data = pd.DataFrame()

        # Define columns for samples and batches for visibility control
        sample_cols = ["DisplaySampleID", "Owner", "MaturationDate", "Status", "CreationDate"]
        batch_cols = ["BatchID", "ProductName", "Description", "SubmissionDate", "NumberOfSamples"]

        # Hide sample-specific columns
        for col in sample_cols:
            self.tree.column(col, width=0, stretch=tk.NO)
        # Set batch-specific columns visible and configure widths
        for col in batch_cols:
            self.tree.column(col, width=100, stretch=tk.YES)
        self.tree.column("BatchID", width=150, stretch=tk.YES)
        self.tree.column("ProductName", width=120, stretch=tk.YES)
        self.tree.column("Description", width=200, stretch=tk.YES)
        self.tree.column("SubmissionDate", width=120, anchor="center", stretch=tk.YES)
        self.tree.column("NumberOfSamples", width=100, anchor="center", stretch=tk.YES)

        if batches_list:
            df = pd.DataFrame(batches_list)
            df.rename(columns={
                "firestore_doc_id": "DocID",
                "batch_id": "BatchID",
                "product_name": "ProductName",
                "description": "Description",
                "submission_date": "SubmissionDate",
                "number_of_samples": "NumberOfSamples"
            }, inplace=True)

            self.app.data = df

            for index, row in self.app.data.iterrows():
                submission_date_str = "N/A"
                sub_date = row.get('SubmissionDate')
                # Robustly convert submission date to string format
                if sub_date is not None:
                    if hasattr(sub_date, 'to_datetime'):
                        sub_date_dt = sub_date.to_datetime()
                    elif isinstance(sub_date, datetime):
                        sub_date_dt = sub_date
                    else:
                        try:
                            sub_date_dt = datetime.strptime(str(sub_date).split(' ')[0], "%Y-%m-%d")
                        except ValueError:
                            sub_date_dt = None
                    if sub_date_dt:
                        submission_date_str = sub_date_dt.strftime("%Y-%m-%d")

                self.tree.insert("", tk.END,
                                 values=(row.get('DocID', ''),
                                         '', '', '', '',  # Empty values for hidden sample columns
                                         row.get('BatchID', 'N/A'),
                                         '',  # Empty for sample CreationDate
                                         row.get('ProductName', 'N/A'),
                                         row.get('Description', 'N/A'),
                                         submission_date_str,
                                         row.get('NumberOfSamples', 0)))
            self.status_label.config(text=f"Loaded {len(self.app.data)} batches.")
        else:
            self.status_label.config(text="No batches found.")

        # Disable sample-specific buttons and pagination controls when showing batches
        self.add_single_sample_button.config(state=tk.DISABLED)
        self.prev_sample_page_btn.config(state=tk.DISABLED)
        self.next_sample_page_btn.config(state=tk.DISABLED)
        self.page_info_label.config(text="Page 0 of 0")

        # Disable Edit and Delete Sample buttons when batches are displayed
        if self.edit_sample_button:
            self.edit_sample_button.config(state=tk.DISABLED)
        if self.delete_sample_button:
            self.delete_sample_button.config(state=tk.DISABLED)

        logging.info("Batches treeview populated.")

    def navigate_samples_page(self, direction):
        """Navigates to the previous or next page of samples based on the current query type."""
        logging.info(f"Navigating samples page: {direction}, current_page_index: {self.current_page_index}")
        if self.last_loaded_query_type == 'all_samples':
            if direction == 'next':
                self.current_page_index += 1
            elif direction == 'prev':
                self.current_page_index -= 1
            self.load_samples_paginated('all_samples', reset=False)
        elif self.last_loaded_query_type == 'my_samples':
            if direction == 'next':
                self.current_page_index += 1
            elif direction == 'prev':
                self.current_page_index -= 1
            self.load_samples_paginated('my_samples', reset=False)
        elif self.last_loaded_query_type == 'current_batch_samples':
            if direction == 'next':
                self.current_page_index += 1
            elif direction == 'prev':
                self.current_page_index -= 1
            self.load_samples_for_current_batch(reset=False)
        else:
            messagebox.showwarning("Navigation Error",
                                   "Cannot navigate pages for the current view type. Please load all samples or my samples first.")
            logging.warning("Attempted page navigation on unsupported view type.")

    def load_samples_paginated(self, query_type, reset=True):
        """
        Loads samples from Firestore with cursor-based pagination.
        query_type: 'all_samples' or 'my_samples'
        reset: If True, resets to the first page. If False, loads next/previous.
        """
        logging.info(f"Loading samples paginated. Query Type: {query_type}, Reset: {reset}")
        try:
            samples_ref = db.collection("samples")
            query = None

            # If resetting, clear all relevant pagination states
            if reset:
                self.current_page_index = 0
                self.all_samples_page_cursors = []
                self.my_samples_page_cursors = []
                self.batch_samples_page_cursors = []

            if query_type == 'all_samples':
                self.last_loaded_query_type = 'all_samples'

                query = samples_ref.order_by("creation_date").limit(self.samples_per_page)
                # Apply cursor for pagination if not on the first page
                if self.current_page_index > 0 and len(self.all_samples_page_cursors) > self.current_page_index - 1:
                    start_after_doc = self.all_samples_page_cursors[self.current_page_index - 1]
                    query = query.start_after(start_after_doc)
                logging.info(
                    f"Building query for all samples. Current page index: {self.current_page_index}, Cursor count: {len(self.all_samples_page_cursors)}")

            elif query_type == 'my_samples':
                # Check if user is logged in
                if not self.app.current_user or not self.app.current_user.get('employee_id'):
                    messagebox.showwarning("Warning", "User not logged in or employee ID not found.")
                    self.status_label.config(text="Cannot load my samples: User not identified.")
                    logging.warning("Attempted to load 'my_samples' without a logged-in user or employee ID.")
                    # Disable pagination buttons on error
                    self.prev_sample_page_btn.config(state=tk.DISABLED)
                    self.next_sample_page_btn.config(state=tk.DISABLED)
                    self.page_info_label.config(text="Page 0 of 0")
                    return

                self.last_loaded_query_type = 'my_samples'

                # Query samples submitted by the current user, ordered by creation date
                query = samples_ref.where("submitted_by_employee_id", "==",
                                          self.app.current_user['employee_id']).order_by("creation_date").limit(
                    self.samples_per_page)
                # Apply cursor for pagination if not on the first page
                if self.current_page_index > 0 and len(self.my_samples_page_cursors) > self.current_page_index - 1:
                    start_after_doc = self.my_samples_page_cursors[self.current_page_index - 1]
                    query = query.start_after(start_after_doc)
                logging.info(
                    f"Building query for my samples (user: {self.app.current_user['employee_id']}). Current page index: {self.current_page_index}, Cursor count: {len(self.my_samples_page_cursors)}")
            else:
                logging.error(f"Invalid query_type passed to load_samples_paginated: {query_type}")
                # Disable pagination buttons on invalid query type
                self.prev_sample_page_btn.config(state=tk.DISABLED)
                self.next_sample_page_btn.config(state=tk.DISABLED)
                self.page_info_label.config(text="Page 0 of 0")
                return

            docs = list(query.stream())
            logging.info(f"Fetched {len(docs)} documents for page {self.current_page_index + 1}.")
            samples_list = []
            for doc in docs:
                data = doc.to_dict()
                data['firestore_doc_id'] = doc.id
                # Convert Firestore Timestamp objects to datetime objects
                if data.get('maturation_date') and hasattr(data['maturation_date'], 'to_datetime'):
                    data['maturation_date'] = data['maturation_date'].to_datetime()
                if data.get('creation_date') and hasattr(data['creation_date'], 'to_datetime'):
                    data['creation_date'] = data['creation_date'].to_datetime()
                samples_list.append(data)

            # Determine total count for page info
            total_count = 0
            aggregate_query = db.collection("samples").count()
            aggregate_query_snapshot = aggregate_query.get()

            if aggregate_query_snapshot:
                try:
                    potential_result_object = aggregate_query_snapshot[0]
                    if isinstance(potential_result_object, list) and len(potential_result_object) > 0:
                        potential_result_object = potential_result_object[0]
                    if hasattr(potential_result_object, 'value'):
                        total_count = potential_result_object.value
                    elif isinstance(potential_result_object, dict) and 'count' in potential_result_object:
                        total_count = potential_result_object.get('count', 0)
                    else:
                        logging.error(
                            f"Unexpected structure for aggregate result object (all_samples): {type(potential_result_object)}")
                        total_count = 0
                except IndexError:
                    logging.warning("AggregateQuerySnapshot was empty or index 0 out of bounds (all_samples).")
                    total_count = 0
                except Exception as unexpected_e:
                    logging.error(f"Unexpected error when getting total count for all samples: {unexpected_e}",
                                  exc_info=True)
                    total_count = 0
            else:
                total_count = 0
            logging.info(f"Total count for all samples: {total_count}")

            # Store cursor for the next page if a full page was fetched
            if docs and len(docs) == self.samples_per_page:
                if len(self.all_samples_page_cursors) == self.current_page_index:
                    self.all_samples_page_cursors.append(docs[-1])
                else:
                    self.all_samples_page_cursors[self.current_page_index] = docs[-1]
            elif not docs and self.current_page_index > 0:
                logging.info("Reached end of 'all_samples' data during pagination.")

            elif query_type == 'my_samples':
                aggregate_query = db.collection("samples").where("submitted_by_employee_id", "==",
                                                                 self.app.current_user['employee_id']).count()
                aggregate_query_snapshot = aggregate_query.get()

                if aggregate_query_snapshot:
                    try:
                        potential_result_object = aggregate_query_snapshot[0]
                        if isinstance(potential_result_object, list) and len(potential_result_object) > 0:
                            potential_result_object = potential_result_object[0]
                        if hasattr(potential_result_object, 'value'):
                            total_count = potential_result_object.value
                        elif isinstance(potential_result_object, dict) and 'count' in potential_result_object:
                            total_count = potential_result_object.get('count', 0)
                        else:
                            logging.error(
                                f"Unexpected structure for aggregate result object (my_samples): {type(potential_result_object)}")
                            total_count = 0
                    except IndexError:
                        logging.warning("AggregateQuerySnapshot was empty or index 0 out of bounds (my_samples).")
                        total_count = 0
                    except Exception as unexpected_e:
                        logging.error(f"Unexpected error when getting total count for my samples: {unexpected_e}",
                                      exc_info=True)
                        total_count = 0
                else:
                    total_count = 0
                logging.info(f"Total count for my samples: {total_count}")

                # Store cursor for the next page if a full page was fetched
                if docs and len(docs) == self.samples_per_page:
                    if len(self.my_samples_page_cursors) == self.current_page_index:
                        self.my_samples_page_cursors.append(docs[-1])
                    else:
                        self.my_samples_page_cursors[self.current_page_index] = docs[-1]
                elif not docs and self.current_page_index > 0:
                    logging.info("Reached end of 'my_samples' data during pagination.")

            # Calculate total pages based on fetched total count
            total_pages = (total_count + self.samples_per_page - 1) // self.samples_per_page if total_count > 0 else 1
            logging.info(f"Calculated total pages: {total_pages}")

            self.load_samples_to_treeview(samples_list, is_pagination_load=True,
                                          current_page=self.current_page_index + 1, total_pages=total_pages)

        except Exception as e:
            logging.error(f"Failed to load samples paginated: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load samples: {e}")
            self.status_label.config(text="Failed to load samples.")
            # Ensure buttons are disabled on error
            self.prev_sample_page_btn.config(state=tk.DISABLED)
            self.next_sample_page_btn.config(state=tk.DISABLED)
            self.page_info_label.config(text="Page 0 of 0")

    def load_all_batches_to_tree(self):
        """Loads all batches from Firestore and displays them in the Treeview."""
        logging.info("Loading all batches to tree.")
        # Reset sample pagination states when loading batches
        self.current_page_index = 0
        self.all_samples_page_cursors = []
        self.my_samples_page_cursors = []
        self.batch_samples_page_cursors = []

        self.last_loaded_query_type = 'batches'

        try:
            batches_ref = db.collection("batches")
            batches_list = []
            for batch_doc in batches_ref.stream():
                data = batch_doc.to_dict()
                data['firestore_doc_id'] = batch_doc.id
                # Convert Firestore Timestamp to datetime object
                if data.get('submission_date') and hasattr(data['submission_date'], 'to_datetime'):
                    data['submission_date'] = data['submission_date'].to_datetime()
                batches_list.append(data)
            self.load_batches_to_treeview(batches_list)
            logging.info(f"Successfully loaded {len(batches_list)} all batches.")
        except Exception as e:
            logging.error(f"Failed to load all batches: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load all batches: {e}")
            self.status_label.config(text="Failed to load all batches.")

    def load_my_batches_to_tree(self):
        """Loads batches created by the current user from Firestore."""
        logging.info("Loading my batches to tree.")
        # Reset sample pagination states when loading batches
        self.current_page_index = 0
        self.all_samples_page_cursors = []
        self.my_samples_page_cursors = []
        self.batch_samples_page_cursors = []

        self.last_loaded_query_type = 'my_batches'

        try:
            # Check for current user and employee ID before proceeding with the query
            if not self.app.current_user or not self.app.current_user.get('employee_id'):
                messagebox.showwarning("Warning",
                                       "User not logged in or employee ID not found. Cannot load my batches.")
                self.status_label.config(text="Cannot load my batches: User not identified.")
                logging.warning("Attempted to load 'my_batches' without a logged-in user or employee ID.")
                self.load_batches_to_treeview([])
                return

            batches_ref = db.collection("batches")
            batches_list = []
            # Query batches by the current user's employee ID
            for batch_doc in batches_ref.where("user_employee_id", "==", self.app.current_user['employee_id']).stream():
                data = batch_doc.to_dict()
                data['firestore_doc_id'] = batch_doc.id
                # Convert Firestore Timestamp to datetime object
                if data.get('submission_date') and hasattr(data['submission_date'], 'to_datetime'):
                    data['submission_date'] = data['submission_date'].to_datetime()
                batches_list.append(data)
            self.load_batches_to_treeview(batches_list)
            logging.info(
                f"Successfully loaded {len(batches_list)} my batches for user {self.app.current_user['employee_id']}.")
        except Exception as e:
            logging.error(f"Failed to load my batches: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load my batches: {e}")
            self.status_label.config(text="Failed to load my batches.")

    def load_todays_batches_to_tree(self):
        """Loads batches submitted today from Firestore."""
        logging.info("Loading today's batches to tree.")
        # Reset sample pagination states when loading batches
        self.current_page_index = 0
        self.all_samples_page_cursors = []
        self.my_samples_page_cursors = []
        self.batch_samples_page_cursors = []

        self.last_loaded_query_type = 'todays_batches'

        try:
            # Define today's start and end timestamps
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            logging.info(f"Fetching batches from {today_start} to {today_end}")

            batches_ref = db.collection("batches")
            batches_list = []
            # Query batches submitted within today's date range
            query = batches_ref.where("submission_date", ">=", today_start).where("submission_date", "<=", today_end)

            for batch_doc in query.stream():
                data = batch_doc.to_dict()
                data['firestore_doc_id'] = batch_doc.id
                # Convert Firestore Timestamp to datetime object
                if data.get('submission_date') and hasattr(data['submission_date'], 'to_datetime'):
                    data['submission_date'] = data['submission_date'].to_datetime()
                batches_list.append(data)
            self.load_batches_to_treeview(batches_list)
            logging.info(f"Successfully loaded {len(batches_list)} today's batches.")
        except Exception as e:
            logging.error(f"Failed to load today's batches: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load today's batches: {e}")
            self.status_label.config(text="Failed to load today's batches.")

    def open_excel_import_options_form(self):
        """Opens a Toplevel window to choose how to import Excel data (local, new batch, existing batch)."""
        logging.info("Opening Excel import options form.")
        import_options_form = tk.Toplevel(self.root)
        import_options_form.title("Excel Import Options")
        import_options_form.geometry("480x400")
        import_options_form.grab_set()
        import_options_form.transient(self.root)
        import_options_form.config(bg='#f0f0f0')  # Set background

        frame = ttk.Frame(import_options_form, padding=15, style='TFrame')
        frame.pack(expand=True, fill="both")

        self.excel_import_choice = tk.StringVar(value="local")  # Default to local import

        # Radio buttons for import choices
        ttk.Radiobutton(frame, text="Import to Local Table (temporary)",
                        variable=self.excel_import_choice, value="local", style='TRadiobutton',
                        command=self._toggle_excel_import_fields).grid(row=0, column=0, columnspan=2, sticky="w",
                                                                       pady=5)

        ttk.Radiobutton(frame, text="Add to New Batch in Database",
                        variable=self.excel_import_choice, value="new_batch", style='TRadiobutton',
                        command=self._toggle_excel_import_fields).grid(row=1, column=0, columnspan=2, sticky="w",
                                                                       pady=5)

        ttk.Label(frame, text="  New Product Name:", style='TLabel').grid(row=2, column=0, sticky="e", pady=2, padx=5)
        self.excel_new_batch_product_name_entry = ttk.Entry(frame, width=35, state="disabled", style='TEntry')
        self.excel_new_batch_product_name_entry.grid(row=2, column=1, sticky="ew", pady=2, padx=5)

        ttk.Label(frame, text="  New Description:", style='TLabel').grid(row=3, column=0, sticky="e", pady=2, padx=5)
        self.excel_new_batch_description_entry = ttk.Entry(frame, width=35, state="disabled", style='TEntry')
        self.excel_new_batch_description_entry.grid(row=3, column=1, sticky="ew", pady=2, padx=5)

        ttk.Radiobutton(frame, text="Add to Existing Batch in Database",
                        variable=self.excel_import_choice, value="existing_batch", style='TRadiobutton',
                        command=self._toggle_excel_import_fields).grid(row=4, column=0, columnspan=2, sticky="w",
                                                                       pady=5)

        ttk.Label(frame, text="  Existing Batch ID:", style='TLabel').grid(row=5, column=0, sticky="e", pady=2, padx=5)
        self.excel_existing_batch_combobox = ttk.Combobox(frame, state="disabled", width=32, style='TCombobox')
        self.excel_existing_batch_combobox.grid(row=5, column=1, sticky="ew", pady=2, padx=5)
        self._load_existing_batches_into_combobox_for_excel_import(self.excel_existing_batch_combobox)

        ttk.Button(frame, text="Select Excel File and Proceed",
                   command=lambda: self._handle_excel_import_choice(import_options_form), style='Primary.TButton').grid(
            row=6, column=0, columnspan=2, pady=20)

        self._toggle_excel_import_fields()  # Set initial state of fields based on default radio button

        import_options_form.protocol("WM_DELETE_WINDOW", import_options_form.destroy)
        logging.info("Excel import options form opened.")

    def _toggle_excel_import_fields(self):
        """Toggles the state of Excel import fields based on selected radio button."""
        choice = self.excel_import_choice.get()
        logging.debug(f"Toggling Excel import fields. Current choice: {choice}")

        # Reset and disable all fields first
        self.excel_new_batch_product_name_entry.config(state="disabled")
        self.excel_new_batch_product_name_entry.delete(0, tk.END)
        self.excel_new_batch_description_entry.config(state="disabled")
        self.excel_new_batch_description_entry.delete(0, tk.END)
        self.excel_existing_batch_combobox.config(state="disabled")
        self.excel_existing_batch_combobox.set('')
        self.excel_existing_batch_combobox['values'] = []  # Clear values when disabling

        # Enable fields based on selected choice
        if choice == "new_batch":
            self.excel_new_batch_product_name_entry.config(state="normal")
            self.excel_new_batch_description_entry.config(state="normal")
        elif choice == "existing_batch":
            self.excel_existing_batch_combobox.config(state="readonly")
            self._load_existing_batches_into_combobox_for_excel_import(
                self.excel_existing_batch_combobox)  # Reload values for existing batches
        logging.debug("Excel import fields toggled.")

    def _load_existing_batches_into_combobox_for_excel_import(self, target_combobox):
        """Loads batch IDs created by the current user from Firestore into a specific combobox for Excel import."""
        logging.info("Loading existing batches into combobox for Excel import.")
        # Ensure user is logged in before querying for user-specific batches
        if not self.app.current_user or not self.app.current_user.get('employee_id'):
            logging.warning("Cannot load existing batches: User not logged in or employee ID not found.")
            target_combobox['values'] = []
            return

        batches_ref = db.collection("batches")
        try:
            batches = batches_ref.where("user_employee_id", "==", self.app.current_user['employee_id']).stream()
            batch_ids = [batch.id for batch in batches]
            target_combobox['values'] = batch_ids
            logging.info(f"Loaded {len(batch_ids)} existing batches for Excel import combobox.")
        except Exception as e:
            logging.error(f"Failed to load existing batches for Excel import combobox: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load existing batches for Excel import: {e}")
            target_combobox['values'] = []

    def _handle_excel_import_choice(self, form_window):
        """Handles the user's choice for Excel import, reads the file, and proceeds based on selected option."""
        logging.info("Handling Excel import choice.")
        filetypes = (("Excel files", "*.xlsx *.xls"), ("All files", "*.*"))
        filename = filedialog.askopenfilename(title="Open Excel file", filetypes=filetypes)

        if not filename:
            logging.info("Excel file selection cancelled.")
            return

        df = None
        try:
            df = pd.read_excel(filename)
            logging.info(f"Successfully read Excel file: {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read Excel file:\n{e}")
            logging.error(f"Failed to read Excel file {filename}: {e}", exc_info=True)
            return

        # Sanitize column names for robust matching
        df.columns = df.columns.str.strip().str.lower()

        # Map potential variations of column names to standardized ones
        column_name_mapping = {
            'sampleid': 'sample_id',
            'owner': 'owner',
            'maturationdate': 'maturation_date',
            'status': 'status',
            'batchid': 'batch_id',
            'creationdate': 'creation_date',
            'submitted_by_employee_id': 'submitted_by_employee_id',
            'ubmitted_by_employee_ic': 'submitted_by_employee_id',
            'd_by_emp': 'submitted_by_employee_id',
            'batch id': 'batch_id',
            'sample id': 'sample_id',
            'maturation date': 'maturation_date',
            'creation date': 'creation_date',
            'submitted by emp id': 'submitted_by_employee_id',
        }
        df.rename(columns=column_name_mapping, inplace=True)

        # Ensure essential columns are present, adding defaults if missing
        if 'sample_id' not in df.columns:
            messagebox.showwarning("Missing Column", "Excel file must contain a 'SampleID' column (or 'sample_id').")
            logging.warning("Excel file missing 'sample_id' column.")
            return
        if 'owner' not in df.columns:
            messagebox.showwarning("Missing Column",
                                   "Excel file should ideally contain an 'Owner' column. Defaulting to current user.")
            df['owner'] = self.app.current_user.get('username', 'N/A')
        if 'maturation_date' not in df.columns:
            messagebox.showwarning("Missing Column",
                                   "Excel file should ideally contain a 'MaturationDate' column. Defaulting to None.")
            df['maturation_date'] = None
        if 'status' not in df.columns:
            df['status'] = SAMPLE_STATUS_OPTIONS[0]
            logging.warning("Excel file missing 'status' column. Defaulting to first status option.")
        if 'creation_date' not in df.columns:
            df['creation_date'] = datetime.now()
        if 'submitted_by_employee_id' not in df.columns:
            df['submitted_by_employee_id'] = self.app.current_user.get('employee_id')

        # Convert date columns to datetime objects, coercing errors
        for col in ['maturation_date', 'creation_date']:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                df[col] = df[col].apply(lambda x: x.to_pydatetime() if pd.notna(x) else None)

        choice = self.excel_import_choice.get()
        if choice == "local":
            self._import_excel_locally(df, filename, form_window)
        elif choice == "new_batch":
            product_name = self.excel_new_batch_product_name_entry.get().strip()
            description = self.excel_new_batch_description_entry.get().strip()
            self._add_excel_to_new_batch_db(df, product_name, description, form_window)
        elif choice == "existing_batch":
            batch_id = self.excel_existing_batch_combobox.get().strip()
            self._add_excel_to_existing_batch_db(df, batch_id, form_window)

    def _import_excel_locally(self, df, filename, form_window):
        """Imports data from a DataFrame into the application's local DataFrame and displays it."""
        logging.info("Importing Excel data locally.")
        self.app.data = df
        self.app.file_path = filename
        self.load_samples_to_treeview(self.app.data.to_dict('records'), is_pagination_load=True)
        self.status_label.config(text=f"Loaded data from {os.path.basename(filename)} (Local)")
        self.excel_imported = True
        self.current_selected_batch_id = None
        self.add_single_sample_button.config(state=tk.DISABLED)
        # Disable pagination buttons for local import as it's not paginated from DB
        self.prev_sample_page_btn.config(state=tk.DISABLED)
        self.next_sample_page_btn.config(state=tk.DISABLED)
        self.page_info_label.config(text="Page 0 of 0")
        messagebox.showinfo("Success", f"Excel data loaded locally from {os.path.basename(filename)}.")
        form_window.destroy()
        logging.info("Excel data imported locally.")

    def _add_excel_to_new_batch_db(self, df, product_name, description, form_window):
        """Adds Excel data to a new batch in Firestore."""
        logging.info("Adding Excel data to a new batch in DB.")
        if not product_name:
            messagebox.showerror("Error", "Product Name is required for a new batch.")
            logging.warning("Product Name missing for new batch from Excel.")
            return

        # Generate a unique batch ID
        new_batch_id = f"batch_{self.app.current_user['employee_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        if db.collection("batches").document(new_batch_id).get().exists:
            messagebox.showerror("Error", "Generated Batch ID already exists. Please try again.")
            logging.error(f"Generated batch ID '{new_batch_id}' already exists.")
            return

        new_batch_data = {
            "batch_id": new_batch_id,
            "product_name": product_name,
            "description": description,
            "submission_date": datetime.now(),
            "user_employee_id": self.app.current_user['employee_id'],
            "user_username": self.app.current_user['username'],
            "user_email": self.app.current_user['email'],
            "status": "pending approval",
            "number_of_samples": 0
        }

        try:
            batch_write = db.batch()
            batch_doc_ref = db.collection("batches").document(new_batch_id)
            batch_write.set(batch_doc_ref, new_batch_data)

            samples_added_count = 0
            for index, row in df.iterrows():
                # Check for duplicate sample_id for each row before adding
                sample_id = row['sample_id']
                existing_samples_with_display_id = db.collection("samples").where("sample_id", "==", sample_id).limit(
                    1).get()
                if list(existing_samples_with_display_id):
                    logging.warning(f"Skipping duplicate sample ID '{sample_id}' from Excel import.")
                    continue

                sample_data = {
                    "sample_id": row['sample_id'],
                    "owner": row['owner'],
                    "maturation_date": row['maturation_date'],
                    "status": row['status'],
                    "batch_id": new_batch_id,
                    "creation_date": row['creation_date'],
                    "submitted_by_employee_id": row['submitted_by_employee_id'],
                    "last_updated_by_user_id": self.app.current_user.get('employee_id'),  # New field
                    "last_updated_timestamp": datetime.now()  # New field
                }
                sample_doc_ref = db.collection("samples").document()
                batch_write.set(sample_doc_ref, sample_data)
                samples_added_count += 1

            # Increment the number of samples in the batch document
            batch_write.update(batch_doc_ref,
                               {"number_of_samples": firebase_admin.firestore.Increment(samples_added_count)})

            batch_write.commit()
            messagebox.showinfo("Success",
                                f"Excel data successfully added to new batch '{new_batch_id}' with {samples_added_count} samples.")
            logging.info(f"Excel data added to new batch '{new_batch_id}' with {samples_added_count} samples.")

            self.current_selected_batch_id = new_batch_id
            self.load_samples_for_current_batch(reset=True)
            if hasattr(self.app, 'admin_logic'):
                self.app.admin_logic.load_batches()
            form_window.destroy()

        except Exception as e:
            logging.error(f"Failed to add Excel data to new batch: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to add Excel data to new batch:\n{e}")

    def _add_excel_to_existing_batch_db(self, df, batch_id, form_window):
        """Adds Excel data to an existing batch in Firestore."""
        logging.info(f"Adding Excel data to existing batch '{batch_id}' in DB.")
        if not batch_id:
            messagebox.showerror("Error", "Please select an existing Batch ID.")
            logging.warning("No batch ID selected for existing batch import.")
            return

        batch_doc_ref = db.collection("batches").document(batch_id)
        existing_batch_doc = batch_doc_ref.get()

        if not existing_batch_doc.exists:
            messagebox.showerror("Error", f"Batch ID '{batch_id}' does not exist.")
            logging.error(f"Selected existing batch ID '{batch_id}' not found.")
            return

        try:
            batch_write = db.batch()
            samples_added_count = 0
            for index, row in df.iterrows():
                # Check for duplicate sample_id before adding to existing batch
                sample_id = row['sample_id']
                existing_samples_with_display_id = db.collection("samples").where("sample_id", "==", sample_id).limit(
                    1).get()
                if list(existing_samples_with_display_id):
                    logging.warning(f"Skipping duplicate sample ID '{sample_id}' from Excel import.")
                    continue

                sample_data = {
                    "sample_id": row['sample_id'],
                    "owner": row['owner'],
                    "maturation_date": row['maturation_date'],
                    "status": row['status'],
                    "batch_id": batch_id,
                    "creation_date": row['creation_date'],
                    "submitted_by_employee_id": row['submitted_by_employee_id'],
                    "last_updated_by_user_id": self.app.current_user.get('employee_id'),  # New field
                    "last_updated_timestamp": datetime.now()  # New field
                }
                sample_doc_ref = db.collection("samples").document()
                batch_write.set(sample_doc_ref, sample_data)
                samples_added_count += 1

            # Increment the number of samples in the batch document
            batch_write.update(batch_doc_ref,
                               {"number_of_samples": firebase_admin.firestore.Increment(samples_added_count)})

            batch_write.commit()
            messagebox.showinfo("Success",
                                f"Excel data successfully added to existing batch '{batch_id}' with {samples_added_count} new samples.")
            logging.info(f"Excel data added to existing batch '{batch_id}' with {samples_added_count} new samples.")

            self.current_selected_batch_id = batch_id
            self.load_samples_for_current_batch(reset=True)
            if hasattr(self.app, 'admin_logic'):
                self.app.admin_logic.load_batches()
            form_window.destroy()

        except Exception as e:
            logging.error(f"Failed to add Excel data to existing batch: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to add Excel data to existing batch:\n{e}")

    def export_excel(self):
        """Exports current data in the local DataFrame to an Excel file."""
        logging.info("Attempting to export Excel file.")
        if self.app.data.empty:
            messagebox.showwarning("Warning", "No data to export.")
            logging.warning("No data found to export to Excel.")
            return

        filetypes = (("Excel files", "*.xlsx"),)
        filename = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=filetypes)

        if filename:
            try:
                df_to_prepare = self.app.data.copy()

                # Define the desired standardized Excel output header names
                expected_import_headers = {
                    'batch_id',
                    'submitted_by_employee_id',
                    'status',
                    'sample_id',
                    'owner',
                    'maturation_date',
                    'creation_date',
                    'last_updated_by_user_id',  # Include new field for export if desired
                    'last_updated_timestamp'  # Include new field for export if desired
                }

                column_rename_map = {}
                for col in df_to_prepare.columns:
                    # Skip 'DocID' column from export
                    if 'docid' in col.lower():
                        continue

                    # Explicitly map Treeview/internal names to desired export format
                    if col == 'BatchID':
                        column_rename_map[col] = 'batch_id'
                    elif col == 'DisplaySampleID':
                        column_rename_map[col] = 'sample_id'
                    elif col == 'Owner':
                        column_rename_map[col] = 'owner'
                    elif col == 'MaturationDate':
                        column_rename_map[col] = 'maturation_date'
                    elif col == 'Status':
                        column_rename_map[col] = 'status'
                    elif col == 'CreationDate':
                        column_rename_map[col] = 'creation_date'
                    elif col == 'submitted_by_employee_id':
                        column_rename_map[col] = 'submitted_by_employee_id'
                    elif col == 'd_by_emp':  # Handle typo from import side
                        column_rename_map[col] = 'submitted_by_employee_id'
                    elif col == 'last_updated_by_user_id':  # Map the new internal field
                        column_rename_map[col] = 'last_updated_by_user_id'
                    elif col == 'last_updated_timestamp':  # Map the new internal field
                        column_rename_map[col] = 'last_updated_timestamp'
                    elif col.lower().replace(' ', '_') in expected_import_headers:
                        column_rename_map[col] = col.lower().replace(' ', '_')
                    else:
                        logging.warning(
                            f"Column '{col}' not explicitly mapped for export. Defaulting to lowercase_with_underscores.")
                        column_rename_map[col] = col.lower().replace(' ', '_')

                df_to_prepare.rename(columns=column_rename_map, inplace=True, errors='ignore')

                # Define the final desired order of columns in the Excel file
                final_excel_output_order = [
                    'batch_id',
                    'submitted_by_employee_id',
                    'status',
                    'sample_id',
                    'owner',
                    'maturation_date',
                    'creation_date',
                    'last_updated_by_user_id',  # Add to final output order
                    'last_updated_timestamp'  # Add to final output order
                ]

                # Reindex the DataFrame to select only the desired columns and put them in the correct order.
                df_for_export_final = df_to_prepare.reindex(columns=final_excel_output_order)

                # Ensure datetime objects are timezone-naive before export
                for col in df_for_export_final.columns:
                    if pd.api.types.is_datetime64_any_dtype(df_for_export_final[col]):
                        if df_for_export_final[col].dt.tz is not None:
                            df_for_export_final[col] = df_for_export_final[col].dt.tz_localize(None)

                df_for_export_final.to_excel(filename, index=False)
                self.status_label.config(text=f"Data exported to {os.path.basename(filename)}")
                logging.info(f"Successfully exported data to {filename}.")
            except Exception as e:
                logging.error(f"Failed to export Excel file: {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to export Excel file:\n{e}")

    def refresh_tree(self):
        """Refreshes the Treeview widget with the current DataFrame data or reloads from DB based on last query."""
        logging.info(f"Refreshing tree. Last loaded query type: {self.last_loaded_query_type}")
        if self.last_loaded_query_type in ['all_samples', 'my_samples']:
            self.load_samples_paginated(self.last_loaded_query_type, reset=False)
        elif self.last_loaded_query_type == 'current_batch_samples' and self.current_selected_batch_id:
            self.load_samples_for_current_batch(reset=False)
        elif self.last_loaded_query_type in ['filtered_samples', 'excel_import']:
            # For filtered or excel_import, reload locally as they are not paginated from DB directly
            self.load_samples_to_treeview(self.app.data.to_dict('records'))
        elif self.last_loaded_query_type in ['batches', 'my_batches', 'todays_batches']:
            # For batches, reload from DB
            if self.last_loaded_query_type == 'batches':
                self.load_all_batches_to_tree()
            elif self.last_loaded_query_type == 'my_batches':
                self.load_my_batches_to_tree()
            elif self.last_loaded_query_type == 'todays_batches':
                self.load_todays_batches_to_tree()
        else:
            # Fallback to loading all samples if no specific type is known
            self.load_samples_paginated(query_type='all_samples', reset=True)
        self.status_label.config(text=f"Treeview refreshed. Displaying {len(self.app.data)} items.")
        logging.info(f"Tree refreshed. Displaying {len(self.app.data)} items.")

    def generate_barcode(self):
        """Generates a barcode for the selected sample ID (user-facing ID)."""
        logging.info("Attempting to generate barcode.")
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample from the list.")
            logging.warning("No sample selected for barcode generation.")
            return

        item = self.tree.item(selected[0])
        # Ensure the selected item is a sample, not a batch
        if self.last_loaded_query_type in ['batches', 'my_batches', 'todays_batches']:
            messagebox.showwarning("Warning",
                                   "Please select a sample to generate a barcode (currently displaying batches).")
            logging.warning("Selected item is a batch, not a sample. Barcode generation aborted.")
            return

        sample_id_for_barcode = str(item['values'][1]) if len(item['values']) > 1 else ""

        if not sample_id_for_barcode:
            messagebox.showerror("Error", "Selected sample has no valid Sample ID for barcode generation.")
            logging.error("Selected sample has no valid Sample ID for barcode generation.")
            return

        try:
            # Get Code128 barcode class and generate barcode
            EAN = barcode.get_barcode_class('code128')
            ean = EAN(sample_id_for_barcode, writer=ImageWriter())
            # Prompt user for save location
            save_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                     filetypes=[("PNG files", "*.png")],
                                                     initialfile=f"{sample_id_for_barcode}_barcode.png")
            if save_path:
                ean.save(save_path)
                messagebox.showinfo("Success", f"Barcode saved at {save_path}")
                logging.info(f"Barcode saved at {save_path} for sample ID: {sample_id_for_barcode}")
        except Exception as e:
            logging.error(f"Barcode generation failed for {sample_id_for_barcode}: {e}", exc_info=True)
            messagebox.showerror("Error", f"Barcode generation failed:\n{e}")

    def check_notifications(self):
        """Checks for samples maturing within the defined notification period."""
        logging.info("Checking for notifications.")
        if self.app.data.empty:
            messagebox.showwarning("Warning", "No data loaded.")
            logging.warning("No data loaded for notification check.")
            return

        # Ensure we are checking samples, not batches
        if self.last_loaded_query_type in ['batches', 'my_batches', 'todays_batches']:
            messagebox.showwarning("Warning", "Notifications are for samples only. Please load samples first.")
            logging.warning("Notification check attempted when batches are displayed.")
            return

        # Additional check if 'MaturationDate' column exists
        if 'MaturationDate' not in self.app.data.columns:
            messagebox.showwarning("Warning",
                                   "Maturation date information is not available in the current data set for notifications.")
            logging.warning("Notification check attempted but 'MaturationDate' column is missing.")
            return

        # Make 'today' timezone-naive for consistent comparison
        today = datetime.now().replace(tzinfo=None)

        notifications = []

        for _, row in self.app.data.iterrows():
            mat_date = row.get('MaturationDate')
            if pd.isna(mat_date) or mat_date is None:
                continue

            mat_date_dt = None
            if isinstance(mat_date, pd.Timestamp):
                mat_date_dt = mat_date.to_pydatetime()
            elif isinstance(mat_date, datetime):
                mat_date_dt = mat_date
            else:
                try:
                    # Attempt to convert Firestore Timestamp or string to datetime
                    if hasattr(mat_date, 'to_datetime'):
                        mat_date_dt = mat_date.to_datetime()
                    else:
                        mat_date_dt = datetime.strptime(str(mat_date).split(' ')[0], "%Y-%m-%d")
                except (ValueError, TypeError):
                    logging.warning(
                        f"Could not parse maturation date for sample: {row.get('DisplaySampleID', 'N/A')}. Value: {mat_date}")
                    continue

            # Ensure mat_date_dt is also timezone-naive before comparison
            if mat_date_dt and mat_date_dt.tzinfo is not None:
                mat_date_dt = mat_date_dt.replace(tzinfo=None)

            if mat_date_dt:
                delta = mat_date_dt - today
                if 0 <= delta.days <= NOTIFICATION_DAYS_BEFORE:
                    notifications.append(
                        f"Sample {row.get('DisplaySampleID', 'N/A')} owned by {row.get('Owner', 'N/A')} matures on {mat_date_dt.strftime('%Y-%m-%d')}.")

        if notifications:
            messagebox.showinfo("Notifications", "\n".join(notifications))
            logging.info(f"Found {len(notifications)} notifications.")
        else:
            messagebox.showinfo("Notifications", f"No samples maturing within {NOTIFICATION_DAYS_BEFORE} days.")
            logging.info(f"No samples maturing within {NOTIFICATION_DAYS_BEFORE} days.")

    def open_batch_selection_screen(self):
        """Opens a Toplevel window for selecting an existing batch or creating a new one."""
        logging.info("Opening batch selection screen.")
        batch_selection_form = tk.Toplevel(self.root)
        batch_selection_form.title("Select or Create Batch")
        batch_selection_form.geometry("450x320")
        batch_selection_form.grab_set()
        batch_selection_form.transient(self.root)
        batch_selection_form.config(bg='#f0f0f0')  # Set background

        frame = ttk.Frame(batch_selection_form, padding=10, style='TFrame')
        frame.pack(expand=True, fill="both")

        self.batch_choice = tk.StringVar(value="existing")
        radio_existing = ttk.Radiobutton(frame, text="Select Existing Batch", variable=self.batch_choice,
                                         value="existing", style='TRadiobutton')
        radio_new = ttk.Radiobutton(frame, text="Create New Batch", variable=self.batch_choice, value="new",
                                    style='TRadiobutton')

        radio_existing.grid(row=0, column=0, columnspan=2, sticky="w", pady=5)
        radio_new.grid(row=1, column=0, columnspan=2, sticky="w", pady=5)

        ttk.Label(frame, text="Existing Batch ID:", style='TLabel').grid(row=2, column=0, sticky="e", pady=5, padx=5)
        self.existing_batch_combobox = ttk.Combobox(frame, state="readonly", width=30, style='TCombobox')
        self.existing_batch_combobox.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
        self._load_existing_batches_into_combobox()

        ttk.Label(frame, text="New Product Name:", style='TLabel').grid(row=3, column=0, sticky="e", pady=5, padx=5)
        self.new_batch_product_name = ttk.Entry(frame, width=30, state="disabled", style='TEntry')
        self.new_batch_product_name.grid(row=3, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(frame, text="New Description:", style='TLabel').grid(row=4, column=0, sticky="e", pady=5, padx=5)
        self.new_batch_description = ttk.Entry(frame, width=30, state="disabled", style='TEntry')
        self.new_batch_description.grid(row=4, column=1, sticky="ew", pady=5, padx=5)

        # Configure commands for radio buttons to toggle fields
        radio_existing.config(command=lambda: self._toggle_batch_fields_on_selection(True))
        radio_new.config(command=lambda: self._toggle_batch_fields_on_selection(False))

        # Set initial state of fields based on default radio button
        self._toggle_batch_fields_on_selection(True)

        ttk.Button(frame, text="Confirm Batch Selection",
                   command=lambda: self._handle_batch_selection_confirmation(batch_selection_form),
                   style='Primary.TButton').grid(row=5, column=0, columnspan=2, pady=20)
        batch_selection_form.protocol("WM_DELETE_WINDOW", batch_selection_form.destroy)
        logging.info("Batch selection screen opened.")

    def _toggle_batch_fields_on_selection(self, is_existing_batch_selected):
        """Internal helper to toggle the visibility/state of new/existing batch fields."""
        logging.debug(f"Toggling batch fields. Is existing batch selected: {is_existing_batch_selected}")
        try:
            if self.existing_batch_combobox:
                self.existing_batch_combobox.config(state="readonly" if is_existing_batch_selected else "disabled")
                if not is_existing_batch_selected:
                    self.existing_batch_combobox.set('')  # Clear selection when disabled
        except Exception as e:
            logging.warning(f"Error configuring existing_batch_combobox: {e}")

        try:
            if self.new_batch_product_name:
                self.new_batch_product_name.config(state="normal" if not is_existing_batch_selected else "disabled")
                if is_existing_batch_selected:
                    self.new_batch_product_name.delete(0, tk.END)
        except Exception as e:
            logging.warning(f"Error configuring new_batch_product_name: {e}")

        try:
            if self.new_batch_description:
                self.new_batch_description.config(state="normal" if not is_existing_batch_selected else "disabled")
                if is_existing_batch_selected:
                    self.new_batch_description.delete(0, tk.END)
        except Exception as e:
            logging.warning(f"Error configuring new_batch_description: {e}")
        logging.debug("Batch fields toggled.")

    def _load_existing_batches_into_combobox(self):
        """Loads batch IDs created by the current user from Firestore into the combobox."""
        logging.info("Loading existing batches into combobox.")
        # Ensure user is logged in before querying for user-specific batches
        if not self.app.current_user or not self.app.current_user.get('employee_id'):
            logging.warning("Cannot load existing batches: User not logged in or employee ID not found.")
            self.existing_batch_combobox['values'] = []
            return

        batches_ref = db.collection("batches")
        try:
            batches = batches_ref.where("user_employee_id", "==", self.app.current_user['employee_id']).stream()
            batch_ids = [batch.id for batch in batches]
            self.existing_batch_combobox['values'] = batch_ids
            logging.info(f"Loaded {len(batch_ids)} existing batches for combobox.")
        except Exception as e:
            logging.error(f"Failed to load existing batches into combobox: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load existing batches: {e}")
            self.existing_batch_combobox['values'] = []

    def _handle_batch_selection_confirmation(self, form_window):
        """Handles the confirmation of batch selection or creation."""
        logging.info("Handling batch selection confirmation.")
        selected_batch_id = None

        if self.batch_choice.get() == "new":
            product_name = self.new_batch_product_name.get().strip()
            description = self.new_batch_description.get().strip()
            creation_date_dt = datetime.now()

            if not product_name:
                messagebox.showerror("Error", "New Batch Product Name is required.")
                logging.warning("New batch product name is missing.")
                return

            # Generate a unique batch ID
            selected_batch_id = f"batch_{self.app.current_user['employee_id']}_{datetime.now().strftime('%Y%m%d')}"

            # Check if generated ID already exists (collision is unlikely with timestamp but good practice)
            if db.collection("batches").document(selected_batch_id).get().exists:
                messagebox.showerror("Error", "Generated Batch ID already exists. Please try again.")
                logging.error(
                    f"Generated batch ID '{selected_batch_id}' already exists. Retrying generation might be needed.")
                return

            new_batch_data = {
                "batch_id": selected_batch_id,
                "product_name": product_name,
                "description": description,
                "submission_date": creation_date_dt,
                "user_employee_id": self.app.current_user['employee_id'],
                "user_username": self.app.current_user['username'],
                "user_email": self.app.current_user['email'],
                "status": "pending approval",
                "number_of_samples": 0
            }
            try:
                # Set the new batch document in Firestore
                db.collection("batches").document(selected_batch_id).set(new_batch_data)
                messagebox.showinfo("Success", f"New batch '{selected_batch_id}' created successfully.")
                self.current_selected_batch_id = selected_batch_id
                # Load samples for the new batch
                self.load_samples_for_current_batch(reset=True)
                # If admin_logic is available, update its batches
                if hasattr(self.app, 'admin_logic'):
                    self.app.admin_logic.load_batches()
                form_window.destroy()
                logging.info(f"New batch '{selected_batch_id}' created and samples loaded.")
            except Exception as e:
                logging.error(f"Failed to create new batch: {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to create new batch: {e}")
                return

        else:  # Existing batch selected
            selected_batch_id = self.existing_batch_combobox.get().strip()
            if not selected_batch_id:
                messagebox.showerror("Error", "Please select an existing batch.")
                logging.warning("No existing batch selected.")
                return

            try:
                existing_batch_doc = db.collection("batches").document(selected_batch_id).get()
                if not existing_batch_doc.exists:
                    messagebox.showerror("Error", "Selected batch does not exist in the database.")
                    logging.error(f"Selected batch ID '{selected_batch_id}' not found in database.")
                    return

                self.current_selected_batch_id = selected_batch_id
                # Load samples for the existing batch
                self.load_samples_for_current_batch(reset=True)
                messagebox.showinfo("Batch Selected", f"Samples for batch '{selected_batch_id}' are now displayed.")
                form_window.destroy()
                logging.info(f"Existing batch '{selected_batch_id}' selected and samples loaded.")
            except Exception as e:
                logging.error(f"Failed to handle existing batch selection: {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to retrieve batch details: {e}")

    def load_samples_for_current_batch(self, reset=True):
        """
        Loads samples for the currently selected batch ID with pagination and updates the Treeview.
        reset: If True, resets to the first page. If False, loads next/previous page.
        """
        logging.info(f"Loading samples for current batch: {self.current_selected_batch_id}, Reset: {reset}")
        if not self.current_selected_batch_id:
            self.status_label.config(text="No batch selected to display samples.")
            logging.warning("load_samples_for_current_batch called with no current_selected_batch_id.")
            # Disable pagination buttons as there's no batch data to paginate
            self.prev_sample_page_btn.config(state=tk.DISABLED)
            self.next_sample_page_btn.config(state=tk.DISABLED)
            self.page_info_label.config(text="Page 0 of 0")
            return

        # Reset sample pagination state for this specific view if reset is True
        if reset:
            self.current_page_index = 0
            self.all_samples_page_cursors = []
            self.my_samples_page_cursors = []
            self.batch_samples_page_cursors = []

        self.last_loaded_query_type = 'current_batch_samples'

        self.tree.delete(*self.tree.get_children())
        samples_list = []
        try:
            samples_ref = db.collection("samples")
            # Build query for the specific batch, ordered by creation_date
            query = samples_ref.where("batch_id", "==", self.current_selected_batch_id).order_by("creation_date").limit(
                self.samples_per_page)

            # Apply cursor for pagination if not on the first page
            if self.current_page_index > 0 and len(self.batch_samples_page_cursors) > self.current_page_index - 1:
                start_after_doc = self.batch_samples_page_cursors[self.current_page_index - 1]
                query = query.start_after(start_after_doc)
            logging.info(
                f"Building query for batch samples ({self.current_selected_batch_id}). Current page index: {self.current_page_index}, Cursor count: {len(self.batch_samples_page_cursors)}")

            docs = list(query.stream())
            logging.info(
                f"Fetched {len(docs)} documents for page {self.current_page_index + 1} of batch {self.current_selected_batch_id}.")

            for sample in docs:
                data = sample.to_dict()
                data['firestore_doc_id'] = sample.id
                # Convert Firestore Timestamp to datetime objects
                if data.get('maturation_date') and hasattr(data['maturation_date'], 'to_datetime'):
                    data['maturation_date'] = data['maturation_date'].to_datetime()
                if data.get('creation_date') and hasattr(data['creation_date'], 'to_datetime'):
                    data['creation_date'] = data['creation_date'].to_datetime()
                samples_list.append(data)

            # Determine total count for page info for this specific batch
            total_count = 0
            aggregate_query = db.collection("samples").where("batch_id", "==", self.current_selected_batch_id).count()
            aggregate_query_snapshot = aggregate_query.get()

            if aggregate_query_snapshot:
                try:
                    potential_result_object = aggregate_query_snapshot[0]
                    if isinstance(potential_result_object, list) and len(potential_result_object) > 0:
                        potential_result_object = potential_result_object[0]
                    if hasattr(potential_result_object, 'value'):
                        total_count = potential_result_object.value
                    elif isinstance(potential_result_object, dict) and 'count' in potential_result_object:
                        total_count = potential_result_object.get('count', 0)
                    else:
                        logging.error(
                            f"Unexpected structure for aggregate result object (batch samples): {type(potential_result_object)}")
                        total_count = 0
                except IndexError:
                    logging.warning("AggregateQuerySnapshot was empty or index 0 out of bounds (batch samples).")
                    total_count = 0
                except Exception as unexpected_e:
                    logging.error(f"Unexpected error when getting total count for batch samples: {unexpected_e}",
                                  exc_info=True)
                    total_count = 0
            else:
                total_count = 0
            logging.info(f"Total count for batch {self.current_selected_batch_id}: {total_count}")

            # Store cursor for the next page if a full page was fetched
            if docs and len(docs) == self.samples_per_page:
                if len(self.batch_samples_page_cursors) == self.current_page_index:
                    self.batch_samples_page_cursors.append(docs[-1])
                else:
                    self.batch_samples_page_cursors[self.current_page_index] = docs[-1]
            elif not docs and self.current_page_index > 0:
                logging.info("Reached end of data for current batch during pagination.")

            # Calculate total pages for the batch
            total_pages = (total_count + self.samples_per_page - 1) // self.samples_per_page if total_count > 0 else 1
            logging.info(f"Calculated total pages for batch {self.current_selected_batch_id}: {total_pages}")

            self.load_samples_to_treeview(samples_list, is_pagination_load=True,
                                          current_page=self.current_page_index + 1, total_pages=total_pages)

            if samples_list:
                self.status_label.config(
                    text=f"Loaded {len(self.app.data)} samples for Batch: {self.current_selected_batch_id}. Page {self.current_page_index + 1} of {total_pages}.")
                logging.info(f"Loaded {len(samples_list)} samples for batch {self.current_selected_batch_id}.")
            else:
                self.status_label.config(text=f"No samples found for Batch: {self.current_selected_batch_id}")
                logging.info(f"No samples found for batch {self.current_selected_batch_id}.")

            self.add_single_sample_button.config(state=tk.NORMAL)
            # Enable/disable pagination controls based on the current page for the batch
            self.prev_sample_page_btn.config(state=tk.NORMAL if self.current_page_index > 0 else tk.DISABLED)
            self.next_sample_page_btn.config(
                state=tk.NORMAL if self.current_page_index < total_pages - 1 else tk.DISABLED)
            self.page_info_label.config(text=f"Page {self.current_page_index + 1} of {total_pages}")


        except Exception as e:
            logging.error(f"Failed to load samples for batch {self.current_selected_batch_id} (paginated): {e}",
                          exc_info=True)
            messagebox.showerror("Error", f"Failed to load samples for batch: {e}")
            self.status_label.config(text="Failed to load samples for batch.")
            # Ensure pagination buttons are disabled on error
            self.prev_sample_page_btn.config(state=tk.DISABLED)
            self.next_sample_page_btn.config(state=tk.DISABLED)
            self.page_info_label.config(text="Page 0 of 0")

    def open_single_sample_form(self):
        """Opens a form to add a single new sample to the currently selected batch."""
        logging.info(f"Opening single sample form for batch: {self.current_selected_batch_id}")
        if not self.current_selected_batch_id:
            messagebox.showwarning("Warning",
                                   "Please select or create a batch first using 'Add Sample to Batch' button.")
            logging.warning("open_single_sample_form called with no current_selected_batch_id.")
            return

        form = tk.Toplevel(self.root)
        form.title(f"Add Sample to Batch: {self.current_selected_batch_id}")
        form.geometry("500x350")
        form.grab_set()
        form.transient(self.root)
        form.config(bg='#f0f0f0')  # Set background

        frame = ttk.Frame(form, padding=10, style='TFrame')
        frame.pack(expand=True, fill="both")

        current_row = 0

        ttk.Label(frame, text="Batch ID:", style='TLabel').grid(row=current_row, column=0, sticky="e", pady=5, padx=5)
        ttk.Label(frame, text=self.current_selected_batch_id, font=('Helvetica', 10, 'bold'), background='#f0f0f0',
                  foreground='#333333').grid(row=current_row, column=1, sticky="w", pady=5, padx=5)
        current_row += 1

        ttk.Label(frame, text="Sample ID (e.g., SMPL-001):", style='TLabel').grid(row=current_row, column=0, sticky="e",
                                                                                  pady=5, padx=5)
        self.entry_sample_display_id = ttk.Entry(frame, width=30, style='TEntry')
        self.entry_sample_display_id.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        current_row += 1

        ttk.Label(frame, text="Sample Owner:", style='TLabel').grid(row=current_row, column=0, sticky="e", pady=5,
                                                                    padx=5)
        self.entry_owner_combobox = ttk.Combobox(frame, state="readonly", width=27, style='TCombobox')
        self.entry_owner_combobox.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        self._load_users_into_owner_combobox(self.entry_owner_combobox)
        # Set default owner to current user if available
        if self.app.current_user and self.app.current_user.get('username'):
            self.entry_owner_combobox.set(self.app.current_user['username'])
        current_row += 1

        ttk.Label(frame, text="Maturation Date (YYYY-MM-DD):", style='TLabel').grid(row=current_row, column=0,
                                                                                    sticky="e", pady=5, padx=5)
        self.entry_maturation_date_entry = DateEntry(frame, width=28, background='darkblue', foreground='white',
                                                     borderwidth=2,
                                                     date_pattern='yyyy-mm-dd')  # TkCalendar styling
        self.entry_maturation_date_entry.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        self.entry_maturation_date_entry.set_date(datetime.now().date())  # Default to today
        current_row += 1

        ttk.Label(frame, text="Status:", style='TLabel').grid(row=current_row, column=0, padx=5, pady=5, sticky="e")
        self.status_combobox = ttk.Combobox(frame, values=SAMPLE_STATUS_OPTIONS, state="readonly", width=27,
                                            style='TCombobox')
        self.status_combobox.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        self.status_combobox.set(SAMPLE_STATUS_OPTIONS[0])  # Default to "pending approval"
        current_row += 1

        ttk.Button(frame, text="Add Sample to Batch", command=lambda: self._submit_single_sample(form),
                   style='Success.TButton').grid(row=current_row, column=0, columnspan=2, pady=15)
        form.protocol("WM_DELETE_WINDOW", form.destroy)
        logging.info("Single sample form opened.")

    def _load_users_into_owner_combobox(self, target_combobox):
        """Loads usernames from Firestore into the sample owner combobox."""
        logging.info("Loading users into owner combobox.")
        users_ref = db.collection("users")
        try:
            users = users_ref.stream()
            usernames = [user.to_dict().get("username", "") for user in users if user.to_dict().get("username")]
            target_combobox['values'] = usernames
            logging.info(f"Loaded {len(usernames)} users for owner combobox.")
        except Exception as e:
            logging.error(f"Failed to load users for owner selection: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load users for owner selection: {e}")
            target_combobox['values'] = []

    def _submit_single_sample(self, form_window):
        """Handles submission of a single new sample to the current batch."""
        logging.info("Submitting single sample.")
        sample_display_id = self.entry_sample_display_id.get().strip()
        owner = self.entry_owner_combobox.get().strip()
        sample_status = self.status_combobox.get().strip()

        # Validate Maturation Date
        mat_date_from_entry = self.entry_maturation_date_entry.get_date()
        if not mat_date_from_entry or mat_date_from_entry == datetime(1, 1, 1).date():
            messagebox.showerror("Error", "Maturation Date is required.")
            logging.warning("Maturation Date is missing for single sample submission.")
            return

        mat_date_dt = datetime(mat_date_from_entry.year, mat_date_from_entry.month, mat_date_from_entry.day)

        # Maturation date validation: Must not be in the past
        today_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if mat_date_dt < today_date:
            messagebox.showerror("Validation Error", "Maturation Date cannot be in the past.")
            logging.warning(f"Maturation Date {mat_date_dt.strftime('%Y-%m-%d')} is in the past. Submission prevented.")
            return

        sample_created_date_dt = datetime.now()

        # Validate Sample ID and Owner
        if not sample_display_id or not owner:
            messagebox.showerror("Error", "Sample ID and Owner are required.")
            logging.warning("Sample ID or Owner missing for single sample submission.")
            return

        try:
            # Check for duplicate sample_id across the entire 'samples' collection
            existing_samples_with_display_id = db.collection("samples").where("sample_id", "==",
                                                                              sample_display_id).limit(1).get()
            if list(existing_samples_with_display_id):
                messagebox.showerror("Error", "Sample ID already exists in the database. Please use a unique ID.")
                logging.error(f"Duplicate sample ID '{sample_display_id}' detected.")
                return
        except Exception as e:
            logging.error(f"Failed to check existing sample ID: {e}", exc_info=True)
            messagebox.showerror("Database Error", f"Failed to check existing sample ID: {e}")
            return

        sample_data = {
            "sample_id": sample_display_id,
            "owner": owner,
            "creation_date": sample_created_date_dt,
            "status": sample_status,
            "batch_id": self.current_selected_batch_id,
            "submitted_by_employee_id": self.app.current_user.get('employee_id'),
            "maturation_date": mat_date_dt,
            "last_updated_by_user_id": self.app.current_user.get('employee_id'),  # Store user ID of creator
            "last_updated_timestamp": datetime.now()  # Store timestamp of creation
        }
        logging.debug(f"Sample data prepared: {sample_data}")

        try:
            batch_write = db.batch()

            # Let Firestore generate the document ID for the sample for true uniqueness
            sample_doc_ref = db.collection("samples").document()
            batch_write.set(sample_doc_ref, sample_data)
            logging.info(f"Prepared to add sample with auto-generated doc ID: {sample_doc_ref.id}")

            batch_doc_ref = db.collection("batches").document(self.current_selected_batch_id)
            # Check if batch exists before attempting to update its sample count
            if not batch_doc_ref.get().exists:
                messagebox.showwarning("Warning",
                                       f"Batch '{self.current_selected_batch_id}' not found. Sample added, but batch count not updated.")
                logging.warning(
                    f"Batch '{self.current_selected_batch_id}' not found when adding sample. Batch count not updated.")
            else:
                batch_write.update(batch_doc_ref, {"number_of_samples": firebase_admin.firestore.Increment(1)})
                logging.info(f"Prepared to increment sample count for batch: {self.current_selected_batch_id}")

            batch_write.commit()
            logging.info("Firestore batch committed successfully.")

            messagebox.showinfo("Success",
                                f"Sample '{sample_display_id}' added successfully to Batch '{self.current_selected_batch_id}'.")

            # Reload samples for the current batch to refresh Treeview
            self.load_samples_for_current_batch(reset=False)

            # If admin_logic is available, update its batches
            if hasattr(self.app, 'admin_logic'):
                self.app.admin_logic.load_batches()

            form_window.destroy()
            logging.info("Single sample submission complete.")

        except Exception as e:
            logging.error(f"Failed to add sample: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to add sample: {e}")

    def delete_sample(self):
        """Deletes a selected sample from Firestore and decrements the batch's sample count."""
        logging.info("Starting delete_sample process.")
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample to delete.")
            logging.warning("Delete sample aborted: No sample selected.")
            return

        item = self.tree.item(selected[0])
        logging.debug(f"Selected Treeview item raw values: {item['values']}")

        firestore_doc_id = item['values'][0]
        display_sample_id = item['values'][1]
        batch_id = item['values'][5] if len(item['values']) > 5 else None

        logging.info(
            f"Extracted values for deletion: DocID='{firestore_doc_id}', DisplaySampleID='{display_sample_id}', BatchID='{batch_id}'")

        # Prevent deletion of locally imported samples that are not in DB
        if not firestore_doc_id or firestore_doc_id == 'N/A (Local)':
            messagebox.showerror("Error",
                                 "Cannot delete a locally imported sample directly from the database. Please export and re-import if needed.")
            logging.error("Attempted to delete a local-only sample from the database.")
            return

        confirm = messagebox.askyesno("Confirm Delete",
                                      f"Are you sure you want to delete sample '{display_sample_id}' from Batch '{batch_id}'?")
        if not confirm:
            logging.info("Delete sample aborted: User cancelled.")
            return

        try:
            logging.info("Attempting Firestore batch write operations for deletion...")
            batch_write = db.batch()

            # Delete the sample document
            sample_doc_ref = db.collection("samples").document(firestore_doc_id)
            logging.info(f"Prepared to delete sample document: {firestore_doc_id}")
            batch_write.delete(sample_doc_ref)

            # Decrement sample count in the associated batch
            if batch_id and batch_id != 'N/A':
                batch_doc_ref = db.collection("batches").document(batch_id)
                logging.info(f"Checking existence of batch document: {batch_id}")
                if batch_doc_ref.get().exists:
                    logging.info(f"Batch document '{batch_id}' exists. Preparing to decrement sample count.")
                    batch_write.update(batch_doc_ref, {"number_of_samples": firebase_admin.firestore.Increment(-1)})
                else:
                    logging.warning(
                        f"Batch '{batch_id}' not found for sample '{display_sample_id}'. Cannot update sample count.")
            else:
                logging.warning(
                    f"No valid Batch ID found for sample '{display_sample_id}'. Cannot update sample count.")

            batch_write.commit()
            logging.info("Firestore batch committed successfully.")

            messagebox.showinfo("Success", f"Sample '{display_sample_id}' deleted successfully.")
            logging.info("Success message displayed.")

            # Refresh the Treeview based on the last loaded query type, maintaining current page
            if self.last_loaded_query_type in ['all_samples', 'my_samples']:
                self.load_samples_paginated(self.last_loaded_query_type, reset=False)
            elif self.last_loaded_query_type == 'current_batch_samples' and self.current_selected_batch_id:
                self.load_samples_for_current_batch(reset=False)
            else:  # Fallback to refresh all samples if context is unclear
                self.load_samples_paginated(query_type='all_samples', reset=True)

            logging.info("Sample data reloaded and tree refreshed.")

            if hasattr(self.app, 'admin_logic'):
                logging.info("Updating admin_logic batches...")
                self.app.admin_logic.load_batches()
                logging.info("Admin_logic batches updated.")

            logging.info("Delete_sample process completed successfully.")

        except Exception as e:
            logging.error(f"Error during delete_sample: {e}", exc_info=True)
            messagebox.showerror("Error",
                                 f"Failed to delete sample: {e}\nSample might have been deleted, but an issue occurred during UI update or batch count adjustment.")
            logging.error("Delete_sample process completed with error.")

    def edit_sample(self):
        """Opens a form to edit details of a selected sample from Firestore."""
        logging.info("Opening edit sample form.")
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample to edit.")
            logging.warning("No sample selected for editing.")
            return

        item = self.tree.item(selected[0])
        firestore_doc_id = item['values'][0]
        display_sample_id = item['values'][1]

        # Prevent editing of locally imported samples
        if not firestore_doc_id or firestore_doc_id == 'N/A (Local)':
            messagebox.showwarning("Warning",
                                   "Cannot edit locally imported samples directly. Please add them to a batch first.")
            logging.warning("Attempted to edit a local-only sample.")
            return

        row = {}
        try:
            sample_doc = db.collection("samples").document(firestore_doc_id).get()
            if not sample_doc.exists:
                messagebox.showerror("Error", "Selected sample not found in database.")
                logging.error(f"Sample with doc ID {firestore_doc_id} not found for editing.")
                # Refresh current view if sample not found
                if self.last_loaded_query_type in ['all_samples', 'my_samples']:
                    self.load_samples_paginated(self.last_loaded_query_type, reset=False)
                elif self.last_loaded_query_type == 'current_batch_samples' and self.current_selected_batch_id:
                    self.load_samples_for_current_batch(reset=False)
                else:
                    self.load_samples_paginated(query_type='all_samples', reset=True)
                return
            row = sample_doc.to_dict()
            logging.info(f"Fetched sample data for editing (DocID: {firestore_doc_id}).")
        except Exception as e:
            logging.error(f"Failed to retrieve sample data for editing: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to retrieve sample data: {e}")
            return

        form = tk.Toplevel(self.root)
        form.title(f"Edit Sample {display_sample_id}")
        form.geometry("450x250")
        form.grab_set()
        form.transient(self.root)
        form.config(bg='#f0f0f0')  # Set background

        current_row = 0

        ttk.Label(form, text="Sample ID:", style='TLabel').grid(row=current_row, column=0, sticky="e", pady=5, padx=5)
        entry_sample_display_id = ttk.Entry(form, style='TEntry')
        entry_sample_display_id.insert(0, row.get('sample_id', ''))
        entry_sample_display_id.config(state='disabled')  # Sample ID is usually not editable
        entry_sample_display_id.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        current_row += 1

        ttk.Label(form, text="Sample Owner:", style='TLabel').grid(row=current_row, column=0, sticky="e", pady=5,
                                                                   padx=5)
        edit_owner_combobox = ttk.Combobox(form, state="readonly", style='TCombobox')
        self._load_users_into_owner_combobox(edit_owner_combobox)
        edit_owner_combobox.set(row.get('owner', ''))
        edit_owner_combobox.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        current_row += 1

        ttk.Label(form, text="Maturation Date (YYYY-MM-DD):", style='TLabel').grid(row=current_row, column=0,
                                                                                   sticky="e", pady=5, padx=5)
        self.edit_mat_date_entry = DateEntry(form, width=28, background='darkblue', foreground='white', borderwidth=2,
                                             date_pattern='yyyy-mm-dd')  # TkCalendar styling
        self.edit_mat_date_entry.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)

        # Set the current maturation date or a default empty date
        mat_date_for_entry = None
        if isinstance(row.get('maturation_date'), datetime):
            mat_date_for_entry = row['maturation_date']
        elif row.get('maturation_date') and hasattr(row['maturation_date'], 'to_datetime'):
            try:
                mat_date_for_entry = row['maturation_date'].to_datetime()
            except Exception:
                pass

        if mat_date_for_entry:
            self.edit_mat_date_entry.set_date(mat_date_for_entry)
        else:
            self.edit_mat_date_entry.set_date(datetime(1, 1, 1).date())
        current_row += 1

        ttk.Label(form, text="Status:", style='TLabel').grid(row=current_row, column=0, sticky="e", pady=5, padx=5)
        status_combobox_edit = ttk.Combobox(form, values=SAMPLE_STATUS_OPTIONS, state="readonly", style='TCombobox')
        status_combobox_edit.set(row.get('status', SAMPLE_STATUS_OPTIONS[0]))
        status_combobox_edit.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        current_row += 1

        ttk.Button(form, text="Save Changes", command=lambda: self._submit_edit_sample(
            form, firestore_doc_id, edit_owner_combobox.get(), self.edit_mat_date_entry.get_date(),
            status_combobox_edit.get()
        ), style='Success.TButton').grid(row=current_row, column=0, columnspan=2, pady=15)
        form.protocol("WM_DELETE_WINDOW", form.destroy)
        logging.info("Edit sample form opened and populated.")

    def _submit_edit_sample(self, form_window, firestore_doc_id, new_owner, new_mat_date_dt, new_status):
        """Submits the edited sample data to Firestore."""
        logging.info(f"Submitting edited sample (DocID: {firestore_doc_id}).")
        if not new_owner or not new_status:
            messagebox.showerror("Error", "Owner and Status fields are required.")
            logging.warning("Owner or Status missing for sample edit.")
            return

        # Maturation date validation: Must not be in the past
        today_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        if new_mat_date_dt and new_mat_date_dt < today_date.date():  # Compare date objects directly
            messagebox.showerror("Validation Error", "Maturation Date cannot be in the past.")
            logging.warning(
                f"Maturation Date {new_mat_date_dt.strftime('%Y-%m-%d')} is in the past. Submission prevented.")
            return

        # Convert new_mat_date_dt to datetime object for Firestore
        mat_date_for_db = None
        if new_mat_date_dt and new_mat_date_dt != datetime(1, 1, 1).date():
            mat_date_for_db = datetime(new_mat_date_dt.year, new_mat_date_dt.month, new_mat_date_dt.day)
        else:
            messagebox.showerror("Error", "Maturation Date is required.")
            logging.warning("Maturation Date is empty/default after edit, but is required.")
            return

        updated_data = {
            "owner": new_owner,
            "status": new_status,
            "maturation_date": mat_date_for_db,
            "last_updated_by_user_id": self.app.current_user.get('employee_id'),  # New field: user ID who last updated
            "last_updated_timestamp": datetime.now()  # New field: timestamp of last update
        }

        logging.debug(f"Updated data for sample {firestore_doc_id}: {updated_data}")
        try:
            db.collection("samples").document(firestore_doc_id).update(updated_data)
            messagebox.showinfo("Success", "Sample updated successfully.")
            logging.info(f"Sample {firestore_doc_id} updated successfully in Firestore.")

            # Refresh the Treeview based on the last loaded query type, maintaining current page
            if self.last_loaded_query_type in ['all_samples', 'my_samples']:
                self.load_samples_paginated(self.last_loaded_query_type, reset=False)
            elif self.last_loaded_query_type == 'current_batch_samples' and self.current_selected_batch_id:
                self.load_samples_for_current_batch(reset=False)
            else:  # Fallback to refresh all samples if context is unclear
                self.load_samples_paginated(query_type='all_samples', reset=True)

            form_window.destroy()
            logging.info("Sample edit complete.")
        except Exception as e:
            logging.error(f"Failed to update sample {firestore_doc_id}: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to update sample: {e}")

    def open_filter_form(self):
        """Opens a Toplevel window for users to input filtering criteria."""
        logging.info("Opening filter form.")
        filter_form = tk.Toplevel(self.root)
        filter_form.title("Filter Options")
        filter_form.geometry("450x500")
        filter_form.grab_set()
        filter_form.transient(self.root)
        filter_form.config(bg='#f0f0f0')  # Set background

        # Radio buttons to choose filtering mode
        radio_frame = ttk.Frame(filter_form, style='TFrame')
        radio_frame.pack(fill="x", padx=10, pady=10)

        ttk.Radiobutton(radio_frame, text="Filter Samples (by Sample/Batch/Product name)",
                        variable=self.filter_mode, value="samples", style='TRadiobutton',
                        command=self._toggle_filter_frames).pack(anchor="w", pady=5)
        ttk.Radiobutton(radio_frame, text="Find Batch Details (by Batch ID)",
                        variable=self.filter_mode, value="batch_search", style='TRadiobutton',
                        command=self._toggle_filter_frames).pack(anchor="w", pady=5)
        # New radio button for finding sample details
        ttk.Radiobutton(radio_frame, text="Find Sample Details (by Sample ID)",
                        variable=self.filter_mode, value="sample_search", style='TRadiobutton',
                        command=self._toggle_filter_frames).pack(anchor="w", pady=5)

        # Frames to hold specific filter options
        self.sample_filters_frame = ttk.Frame(filter_form, style='TFrame')
        self.batch_search_frame = ttk.Frame(filter_form, style='TFrame')
        self.sample_search_frame = ttk.Frame(filter_form, style='TFrame')  # New frame for sample search

        # Maturation Date Filter widgets within its own frame
        self.maturation_date_filter_frame = ttk.Frame(self.sample_filters_frame, style='TFrame')
        ttk.Checkbutton(self.sample_filters_frame, text="Enable Maturation Date Filter",
                        variable=self.filter_maturation_date_var, style='TCheckbutton',
                        command=self._toggle_maturation_filter_state).grid(row=0, column=0, sticky="w", pady=5, padx=5,
                                                                           columnspan=2)

        ttk.Label(self.maturation_date_filter_frame, text="From (YYYY-MM-DD):", style='TLabel').grid(row=0, column=0,
                                                                                                     sticky="e", pady=5,
                                                                                                     padx=5)
        self.filter_start_date_entry = DateEntry(self.maturation_date_filter_frame, width=28, background='darkblue',
                                                 foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.filter_start_date_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
        self.filter_start_date_entry.set_date(datetime.now().date())

        ttk.Label(self.maturation_date_filter_frame, text="To (YYYY-MM-DD):", style='TLabel').grid(row=1, column=0,
                                                                                                   sticky="e", pady=5,
                                                                                                   padx=5)
        self.filter_end_date_entry = DateEntry(self.maturation_date_filter_frame, width=28, background='darkblue',
                                               foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.filter_end_date_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
        self.filter_end_date_entry.set_date(datetime.now().date())

        # Creation Date Filter widgets within its own frame
        self.creation_date_filter_frame = ttk.Frame(self.sample_filters_frame, style='TFrame')
        ttk.Checkbutton(self.sample_filters_frame, text="Enable Creation Date Filter",
                        variable=self.filter_creation_date_var, style='TCheckbutton',
                        command=self._toggle_creation_filter_state).grid(row=2, column=0, sticky="w", pady=5, padx=5,
                                                                         columnspan=2)

        ttk.Label(self.creation_date_filter_frame, text="From (YYYY-MM-DD):", style='TLabel').grid(row=0, column=0,
                                                                                                   sticky="e", pady=5,
                                                                                                   padx=5)
        self.filter_creation_start_date_entry = DateEntry(self.creation_date_filter_frame, width=28,
                                                          background='darkblue', foreground='white', borderwidth=2,
                                                          date_pattern='yyyy-mm-dd')
        self.filter_creation_start_date_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
        self.filter_creation_start_date_entry.set_date(datetime.now().date())

        ttk.Label(self.creation_date_filter_frame, text="To (YYYY-MM-DD):", style='TLabel').grid(row=1, column=0,
                                                                                                 sticky="e", pady=5,
                                                                                                 padx=5)
        self.filter_creation_end_date_entry = DateEntry(self.creation_date_filter_frame, width=28,
                                                        background='darkblue', foreground='white', borderwidth=2,
                                                        date_pattern='yyyy-mm-dd')
        self.filter_creation_end_date_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
        self.filter_creation_end_date_entry.set_date(datetime.now().date())

        # Initial state of date filter frames (hidden by default)
        self._toggle_maturation_filter_state()
        self._toggle_creation_filter_state()

        # Other filters always visible, positioned after date filter frames
        current_filter_row = 4

        ttk.Label(self.sample_filters_frame, text="Sample ID (similar/contains):", style='TLabel').grid(
            row=current_filter_row, column=0, sticky="e", pady=5, padx=5)
        self.filter_sample_id_entry = ttk.Entry(self.sample_filters_frame, width=30, style='TEntry')
        self.filter_sample_id_entry.grid(row=current_filter_row, column=1, sticky="ew", pady=5, padx=5)
        current_filter_row += 1

        ttk.Label(self.sample_filters_frame, text="Batch ID (similar/contains):", style='TLabel').grid(
            row=current_filter_row, column=0, sticky="e", pady=5, padx=5)
        self.filter_batch_id_entry = ttk.Entry(self.sample_filters_frame, width=30, style='TEntry')
        self.filter_batch_id_entry.grid(row=current_filter_row, column=1, sticky="ew", pady=5, padx=5)
        current_filter_row += 1

        ttk.Label(self.sample_filters_frame, text="Product Name (similar/contains):", style='TLabel').grid(
            row=current_filter_row, column=0, sticky="e", pady=5, padx=5)
        self.filter_product_name_entry = ttk.Entry(self.sample_filters_frame, width=30, style='TEntry')
        self.filter_product_name_entry.grid(row=current_filter_row, column=1, sticky="ew", pady=5, padx=5)
        current_filter_row += 1

        ttk.Label(self.sample_filters_frame, text="Status:", style='TLabel').grid(row=current_filter_row, column=0,
                                                                                  sticky="e", pady=5, padx=5)
        self.filter_status_combobox = ttk.Combobox(self.sample_filters_frame, values=[""] + SAMPLE_STATUS_OPTIONS,
                                                   state="readonly", width=27, style='TCombobox')
        self.filter_status_combobox.set("")  # Default to empty to show all statuses
        self.filter_status_combobox.grid(row=current_filter_row, column=1, sticky="ew", pady=5, padx=5)
        current_filter_row += 1

        # Populate batch_search_frame
        ttk.Label(self.batch_search_frame, text="Enter Batch ID:", style='TLabel').grid(row=0, column=0, sticky="e",
                                                                                        pady=5, padx=5)
        self.find_batch_id_entry = ttk.Entry(self.batch_search_frame, width=30, style='TEntry')
        self.find_batch_id_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        # Populate sample_search_frame
        ttk.Label(self.sample_search_frame, text="Enter Sample ID:", style='TLabel').grid(row=0, column=0, sticky="e",
                                                                                          pady=5, padx=5)
        self.find_sample_id_entry = ttk.Entry(self.sample_search_frame, width=30, style='TEntry')
        self.find_sample_id_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        # Buttons common to both modes
        button_frame = ttk.Frame(filter_form, style='TFrame')
        button_frame.pack(fill="x", side="bottom", padx=10, pady=10)

        ttk.Button(button_frame, text="Apply", command=lambda: self.apply_filters(filter_form),
                   style='Success.TButton').pack(side=tk.LEFT, padx=5, pady=10)
        ttk.Button(button_frame, text="Clear Filters", command=lambda: self.clear_filters(filter_form),
                   style='Secondary.TButton').pack(side=tk.LEFT, padx=5, pady=10)

        # Initial display of filter frames
        self._toggle_filter_frames()

        filter_form.protocol("WM_DELETE_WINDOW", filter_form.destroy)
        logging.info("Filter form opened.")

    def _toggle_maturation_filter_state(self):
        """Toggles the visibility and state of maturation date filter entries."""
        logging.debug(f"Toggling maturation filter state: {self.filter_maturation_date_var.get()}")
        if self.filter_maturation_date_var.get():
            self.maturation_date_filter_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        else:
            self.maturation_date_filter_frame.grid_forget()
            # Reset dates when filter is disabled
            if self.filter_start_date_entry:
                self.filter_start_date_entry.set_date(datetime.now().date())
            if self.filter_end_date_entry:
                self.filter_end_date_entry.set_date(datetime.now().date())
        logging.debug("Maturation filter state toggled.")

    def _toggle_creation_filter_state(self):
        """Toggles the visibility and state of creation date filter entries."""
        logging.debug(f"Toggling creation filter state: {self.filter_creation_date_var.get()}")
        if self.filter_creation_date_var.get():
            self.creation_date_filter_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        else:
            self.creation_date_filter_frame.grid_forget()
            # Reset dates when filter is disabled
            if self.filter_creation_start_date_entry:
                self.filter_creation_start_date_entry.set_date(datetime.now().date())
            if self.filter_creation_end_date_entry:
                self.filter_creation_end_date_entry.set_date(datetime.now().date())
        logging.debug("Creation filter state toggled.")

    def _toggle_filter_frames(self):
        """Toggles visibility of filter frames based on radio button selection."""
        logging.info(f"Toggling filter frames. Current mode: {self.filter_mode.get()}")
        # Hide all frames first
        self.sample_filters_frame.pack_forget()
        self.batch_search_frame.pack_forget()
        self.sample_search_frame.pack_forget()  # Hide new sample search frame

        # Ensure date filter frames are hidden and their variables are reset when switching modes
        self.maturation_date_filter_frame.grid_forget()
        self.creation_date_filter_frame.grid_forget()
        self.filter_maturation_date_var.set(False)
        self.filter_creation_date_var.set(False)

        if self.filter_mode.get() == "samples":
            self.sample_filters_frame.pack(fill="both", expand=True, padx=10, pady=10)
            self._toggle_maturation_filter_state()  # Re-apply state
            self._toggle_creation_filter_state()  # Re-apply state
            logging.info("Switched to Sample Filter mode.")
        elif self.filter_mode.get() == "batch_search":
            self.batch_search_frame.pack(fill="both", expand=True, padx=10, pady=10)
            logging.info("Switched to Batch Search mode.")
        elif self.filter_mode.get() == "sample_search":  # Handle new sample search mode
            self.sample_search_frame.pack(fill="both", expand=True, padx=10, pady=10)
            logging.info("Switched to Sample Search mode.")

    def apply_filters(self, form_window):
        """Applies the filters based on the selected mode (sample filter, batch search, or sample search)."""
        logging.info(f"Apply Filters called. Mode: {self.filter_mode.get()}")
        if self.filter_mode.get() == "samples":
            filters = {}

            # Process Maturation Date Filters
            if self.filter_maturation_date_var.get():
                start_date_obj = self.filter_start_date_entry.get_date()
                end_date_obj = self.filter_end_date_entry.get_date()
                if start_date_obj and start_date_obj != datetime(1, 1, 1).date():
                    filters['start_date'] = datetime(start_date_obj.year, start_date_obj.month, start_date_obj.day)
                if end_date_obj and end_date_obj != datetime(1, 1, 1).date():
                    filters['end_date'] = datetime(end_date_obj.year, end_date_obj.month, end_date_obj.day, 23, 59, 59,
                                                   999999)
                if filters.get('start_date') and filters.get('end_date') and filters['start_date'] > filters[
                    'end_date']:
                    messagebox.showerror("Error", "'Maturation Date From' cannot be after 'Maturation Date To'.")
                    logging.warning("Maturation date 'From' is after 'To' date.")
                    return

            # Process Creation Date Filters
            if self.filter_creation_date_var.get():
                creation_start_date_obj = self.filter_creation_start_date_entry.get_date()
                creation_end_date_obj = self.filter_creation_end_date_entry.get_date()
                if creation_start_date_obj and creation_start_date_obj != datetime(1, 1, 1).date():
                    filters['creation_start_date'] = datetime(creation_start_date_obj.year,
                                                              creation_start_date_obj.month,
                                                              creation_start_date_obj.day)
                if creation_end_date_obj and creation_end_date_obj != datetime(1, 1, 1).date():
                    filters['creation_end_date'] = datetime(creation_end_date_obj.year, creation_end_date_obj.month,
                                                            creation_end_date_obj.day, 23, 59, 59, 999999)
                if filters.get('creation_start_date') and filters.get('creation_end_date') and filters[
                    'creation_start_date'] > filters['creation_end_date']:
                    messagebox.showerror("Error", "'Creation Date From' cannot be after 'Creation Date To'.")
                    logging.warning("Creation date 'From' is after 'To' date.")
                    return

            logging.info(
                f"Maturation Date Filters processed: Start={filters.get('start_date')}, End={filters.get('end_date')}")
            logging.info(
                f"Creation Date Filters processed: Start={filters.get('creation_start_date')}, End={filters.get('creation_end_date')}")

            # Get text-based filter values
            sample_id = self.filter_sample_id_entry.get().strip()
            batch_id = self.filter_batch_id_entry.get().strip()
            product_name = self.filter_product_name_entry.get().strip()
            status = self.filter_status_combobox.get().strip()

            if sample_id:
                filters['sample_id'] = sample_id
            if batch_id:
                filters['batch_id'] = batch_id
            if product_name:
                filters['product_name'] = product_name
            if status:
                filters['status'] = status

            logging.info(f"Applying sample filters: {filters}")
            self.load_all_user_samples_from_db_with_filters(filters)
            form_window.destroy()

        elif self.filter_mode.get() == "batch_search":
            batch_id_to_find = self.find_batch_id_entry.get().strip()
            logging.info(f"Searching for batch ID: {batch_id_to_find}")
            if not batch_id_to_find:
                messagebox.showerror("Error", "Please enter a Batch ID to search.")
                logging.warning("No batch ID entered for batch search.")
                return

            try:
                batch_doc = db.collection("batches").document(batch_id_to_find).get()
                if batch_doc.exists:
                    logging.info("Batch found. Displaying details.")
                    self._display_batch_details_window(batch_doc.to_dict())
                    form_window.destroy()
                else:
                    logging.info("Batch Not Found.")
                    messagebox.showinfo("Batch Not Found", f"Batch with ID '{batch_id_to_find}' does not exist.")
            except Exception as e:
                logging.error(f"Error retrieving batch details for '{batch_id_to_find}': {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to retrieve batch details: {e}")

        elif self.filter_mode.get() == "sample_search":  # New: Handle sample search mode
            sample_id_to_find = self.find_sample_id_entry.get().strip()
            logging.info(f"Searching for sample ID: {sample_id_to_find}")
            if not sample_id_to_find:
                messagebox.showerror("Error", "Please enter a Sample ID to search.")
                logging.warning("No sample ID entered for sample search.")
                return

            try:
                # Find sample by sample_id (which is a field, not the Firestore document ID)
                sample_docs = db.collection("samples").where("sample_id", "==", sample_id_to_find).limit(1).get()
                sample_doc = None
                for doc in sample_docs:  # Iterate over the results (should be at most one due to limit(1))
                    sample_doc = doc
                    break

                if sample_doc and sample_doc.exists:
                    logging.info("Sample found. Displaying details.")
                    self._display_sample_details_window(sample_doc.to_dict())
                    form_window.destroy()
                else:
                    logging.info("Sample Not Found.")
                    messagebox.showinfo("Sample Not Found", f"Sample with ID '{sample_id_to_find}' does not exist.")
            except Exception as e:
                logging.error(f"Error retrieving sample details for '{sample_id_to_find}': {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to retrieve sample details: {e}")

    def load_all_user_samples_from_db_with_filters(self, filters=None):
        """
        Loads all sample data from Firestore and populates the local DataFrame and Treeview,
        applying filters directly. This is a non-paginated search for filtered results.
        """
        logging.info(f"Loading all user samples from DB with filters: {filters}")
        # Reset sample pagination state when loading filtered samples
        self.current_page_index = 0
        self.all_samples_page_cursors = []
        self.my_samples_page_cursors = []
        self.batch_samples_page_cursors = []
        self.last_loaded_query_type = 'filtered_samples'

        self.tree.delete(*self.tree.get_children())
        samples_list = []
        try:
            samples_ref = db.collection("samples")
            query = samples_ref

            firestore_maturation_date_filter_applied = False
            firestore_creation_date_filter_applied = False

            if filters:
                # Apply date range filters to Firestore query if present
                if 'start_date' in filters and 'end_date' in filters:
                    query = query.where("maturation_date", ">=", filters['start_date'])
                    query = query.where("maturation_date", "<=", filters['end_date'])
                    firestore_maturation_date_filter_applied = True
                    logging.info("Applied Firestore maturation_date range filter.")
                elif 'creation_start_date' in filters and 'creation_end_date' in filters:
                    query = query.where("creation_date", ">=", filters['creation_start_date'])
                    query = query.where("creation_date", "<=", filters['creation_end_date'])
                    firestore_creation_date_filter_applied = True
                    logging.info("Applied Firestore creation_date range filter.")

                # Apply direct equality filter for status if present
                if filters.get('status'):
                    query = query.where("status", "==", filters['status'])

            samples = query.stream()

            for sample in samples:
                data = sample.to_dict()
                data['firestore_doc_id'] = sample.id
                # Convert Firestore Timestamp to datetime objects
                if data.get('maturation_date') and hasattr(data['maturation_date'], 'to_datetime'):
                    data['maturation_date'] = data['maturation_date'].to_datetime()
                if data.get('creation_date') and hasattr(data['creation_date'], 'to_datetime'):
                    data['creation_date'] = data['creation_date'].to_datetime()
                # Ensure last_updated_timestamp is converted for consistency, though not displayed
                if data.get('last_updated_timestamp') and hasattr(data['last_updated_timestamp'], 'to_datetime'):
                    data['last_updated_timestamp'] = data['last_updated_timestamp'].to_datetime()

                samples_list.append(data)
            logging.info(f"Initial fetch for filtered samples returned {len(samples_list)} results.")

            df = pd.DataFrame(samples_list)

            # Apply local filters for 'similar/contains' matching and secondary date filters
            if filters:
                # Filter by Sample ID (contains)
                if filters.get('sample_id'):
                    if 'sample_id' in df.columns:
                        df = df[df['sample_id'].astype(str).str.contains(filters['sample_id'], case=False, na=False)]
                    elif 'DisplaySampleID' in df.columns:
                        df = df[
                            df['DisplaySampleID'].astype(str).str.contains(filters['sample_id'], case=False, na=False)]
                    logging.debug(f"Filtered by sample_id, {len(df)} remaining.")

                # Filter by Batch ID (contains)
                if filters.get('batch_id'):
                    if 'batch_id' in df.columns:
                        df = df[df['batch_id'].astype(str).str.contains(filters['batch_id'], case=False, na=False)]
                    elif 'BatchID' in df.columns:
                        df = df[df['BatchID'].astype(str).str.contains(filters['batch_id'], case=False, na=False)]
                    logging.debug(f"Filtered by batch_id, {len(df)} remaining.")

                # Filter by Product Name (contains) - requires fetching batch product names
                if filters.get('product_name'):
                    product_name_filter_val = filters['product_name'].lower()
                    valid_batch_ids = df['batch_id'].dropna().unique() if 'batch_id' in df.columns else []
                    batch_product_names = {}
                    for b_id in valid_batch_ids:
                        if b_id and b_id != 'N/A' and pd.notna(b_id):
                            batch_doc = db.collection("batches").document(b_id).get()
                            if batch_doc.exists:
                                batch_product_names[b_id] = batch_doc.to_dict().get('product_name', '').lower()
                    df = df[df['batch_id'].apply(
                        lambda x: product_name_filter_val in batch_product_names.get(x, '') if pd.notna(x) else False)]
                    logging.debug(f"Filtered by product_name, {len(df)} remaining.")

                # Apply secondary date filters locally if not applied by Firestore
                if 'start_date' in filters and 'end_date' in filters and not firestore_maturation_date_filter_applied:
                    df = df[df['maturation_date'].apply(lambda x: x and filters['start_date'] <= x)]
                    df = df[df['maturation_date'].apply(lambda x: x and x <= filters['end_date'])]
                    logging.debug(f"Applied local maturation_date filter, {len(df)} remaining.")

                if 'creation_start_date' in filters and 'creation_end_date' in filters and not firestore_creation_date_filter_applied:
                    df = df[df['creation_date'].apply(lambda x: x and filters['creation_start_date'] <= x)]
                    df = df[df['creation_date'].apply(lambda x: x and x <= filters['creation_end_date'])]
                    logging.debug(f"Applied local creation_date filter, {len(df)} remaining.")

            self.load_samples_to_treeview(df.to_dict('records'))

            if not df.empty:
                self.status_label.config(text=f"Loaded {len(self.app.data)} samples from database matching filters.")
                logging.info(f"Finished loading filtered samples. Displaying {len(self.app.data)} samples.")
            else:
                self.status_label.config(text="No samples found in the database matching filters.")
                logging.info("No samples found matching filters.")

            self.current_selected_batch_id = None
            self.add_single_sample_button.config(state=tk.DISABLED)

            # Disable pagination controls for filtered samples as it's a specific search result
            self.prev_sample_page_btn.config(state=tk.DISABLED)
            self.next_sample_page_btn.config(state=tk.DISABLED)
            self.page_info_label.config(text="Page 0 of 0")


        except Exception as e:
            logging.error(f"Failed to load samples from database with filters: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load samples from database: {e}")
            self.status_label.config("Failed to load samples from database.")

    def _display_batch_details_window(self, batch_data):
        """Displays batch details in a new window with copyable text."""
        logging.info(f"Displaying batch details for batch: {batch_data.get('batch_id', 'N/A')}")
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Batch Details: {batch_data.get('batch_id', 'N/A')}")
        details_window.geometry("500x300")
        details_window.grab_set()
        details_window.transient(self.root)
        details_window.config(bg='#f0f0f0')  # Set background

        text_frame = ttk.Frame(details_window, padding=10, style='TFrame')
        text_frame.pack(expand=True, fill="both")

        text_widget = tk.Text(text_frame, wrap='word', font=('Consolas', 10),
                              bg='#ffffff', bd=0, highlightthickness=0,
                              foreground='#333333')  # White background for text
        text_widget.pack(side=tk.LEFT, expand=True, fill="both")

        scrollbar = ttk.Scrollbar(text_frame, command=text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill='y')
        text_widget.config(yscrollcommand=scrollbar.set)

        details_str = f"Batch ID: {batch_data.get('batch_id', 'N/A')}\n"
        details_str += f"Product Name: {batch_data.get('product_name', 'N/A')}\n"
        details_str += f"Description: {batch_data.get('description', 'N/A')}\n"

        submission_date = batch_data.get('submission_date')
        if submission_date is not None:
            if hasattr(submission_date, 'to_datetime'):
                submission_date_dt = submission_date.to_datetime()
            elif isinstance(submission_date, datetime):
                submission_date_dt = submission_date
            else:
                try:
                    submission_date_dt = datetime.strptime(str(submission_date).split(' ')[0], "%Y-%m-%d")
                except ValueError:
                    submission_date_dt = None

            if submission_date_dt:
                details_str += f"Creation Date: {submission_date_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
            else:
                details_str += f"Creation Date: N/A\n"
        else:
            details_str += f"Creation Date: N/A\n"

        details_str += f"Submitted By (Employee ID): {batch_data.get('user_employee_id', 'N/A')}\n"
        details_str += f"Submitted By (Username): {batch_data.get('user_username', 'N/A')}\n"
        details_str += f"Status: {batch_data.get('status', 'N/A')}\n"
        details_str += f"Number of Samples: {batch_data.get('number_of_samples', 0)}\n"

        text_widget.insert(tk.END, details_str)
        text_widget.config(state='normal')  # Allow selection and copying

        ttk.Button(details_window, text="Close", command=details_window.destroy, style='Secondary.TButton').pack(
            pady=10)
        details_window.protocol("WM_DELETE_WINDOW", details_window.destroy)
        logging.info(f"Batch details window displayed for {batch_data.get('batch_id', 'N/A')}.")

    def _display_sample_details_window(self, sample_data):
        """Displays sample details in a new window with copyable text."""
        logging.info(f"Displaying sample details for sample: {sample_data.get('sample_id', 'N/A')}")
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Sample Details: {sample_data.get('sample_id', 'N/A')}")
        details_window.geometry("500x350")
        details_window.grab_set()
        details_window.transient(self.root)
        details_window.config(bg='#f0f0f0')  # Set background

        text_frame = ttk.Frame(details_window, padding=10, style='TFrame')
        text_frame.pack(expand=True, fill="both")

        text_widget = tk.Text(text_frame, wrap='word', font=('Consolas', 10),
                              bg='#ffffff', bd=0, highlightthickness=0,
                              foreground='#333333')  # White background for text
        text_widget.pack(side=tk.LEFT, expand=True, fill="both")

        scrollbar = ttk.Scrollbar(text_frame, command=text_widget.yview)
        scrollbar.pack(side=tk.RIGHT, fill='y')
        text_widget.config(yscrollcommand=scrollbar.set)

        details_str = f"Sample ID: {sample_data.get('sample_id', 'N/A')}\n"
        details_str += f"Owner: {sample_data.get('owner', 'N/A')}\n"
        details_str += f"Status: {sample_data.get('status', 'N/A')}\n"
        details_str += f"Batch ID: {sample_data.get('batch_id', 'N/A')}\n"
        details_str += f"Submitted By (Employee ID): {sample_data.get('submitted_by_employee_id', 'N/A')}\n"

        # Format Maturation Date
        maturation_date = sample_data.get('maturation_date')
        if maturation_date is not None:
            if hasattr(maturation_date, 'to_datetime'):
                maturation_date_dt = maturation_date.to_datetime()
            elif isinstance(maturation_date, datetime):
                maturation_date_dt = maturation_date
            else:
                try:
                    maturation_date_dt = datetime.strptime(str(maturation_date).split(' ')[0], "%Y-%m-%d")
                except ValueError:
                    maturation_date_dt = None
            if maturation_date_dt:
                details_str += f"Maturation Date: {maturation_date_dt.strftime('%Y-%m-%d')}\n"
            else:
                details_str += f"Maturation Date: N/A\n"
        else:
            details_str += f"Maturation Date: N/A\n"

        # Format Creation Date
        creation_date = sample_data.get('creation_date')
        if creation_date is not None:
            if hasattr(creation_date, 'to_datetime'):
                creation_date_dt = creation_date.to_datetime()
            elif isinstance(creation_date, datetime):
                creation_date_dt = creation_date
            else:
                try:
                    creation_date_dt = datetime.strptime(str(creation_date).split(' ')[0], "%Y-%m-%d")
                except ValueError:
                    creation_date_dt = None
            if creation_date_dt:
                details_str += f"Creation Date: {creation_date_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
            else:
                details_str += f"Creation Date: N/A\n"
        else:
            details_str += f"Creation Date: N/A\n"

        # Format Last Updated By and Timestamp
        last_updated_by = sample_data.get('last_updated_by_user_id', 'N/A')
        last_updated_timestamp = sample_data.get('last_updated_timestamp')

        details_str += f"Last Updated By: {last_updated_by}\n"
        if last_updated_timestamp is not None:
            if hasattr(last_updated_timestamp, 'to_datetime'):
                last_updated_timestamp_dt = last_updated_timestamp.to_datetime()
            elif isinstance(last_updated_timestamp, datetime):
                last_updated_timestamp_dt = last_updated_timestamp
            else:
                try:
                    last_updated_timestamp_dt = datetime.strptime(str(last_updated_timestamp).split(' ')[0],
                                                                  "%Y-%m-%d %H:%M:%S.%f")
                except ValueError:
                    last_updated_timestamp_dt = None
            if last_updated_timestamp_dt:
                details_str += f"Last Updated On: {last_updated_timestamp_dt.strftime('%Y-%m-%d %H:%M:%S')}\n"
            else:
                details_str += f"Last Updated On: N/A\n"
        else:
            details_str += f"Last Updated On: N/A\n"

        text_widget.insert(tk.END, details_str)
        text_widget.config(state='normal')  # Allow selection and copying

        ttk.Button(details_window, text="Close", command=details_window.destroy, style='Secondary.TButton').pack(
            pady=10)
        details_window.protocol("WM_DELETE_WINDOW", details_window.destroy)
        logging.info(f"Sample details window displayed for {sample_data.get('sample_id', 'N/A')}.")

    def clear_filters(self, form_window):
        """Clears all filter fields and reloads all samples."""
        logging.info("Clear Filters called.")
        if self.filter_mode.get() == "samples":
            # Set checkbox variables to False, which will trigger the _toggle functions to hide/clear entries
            self.filter_maturation_date_var.set(False)
            self.filter_creation_date_var.set(False)
            # Ensure entries are cleared immediately by calling toggle functions first
            self._toggle_maturation_filter_state()
            self._toggle_creation_filter_state()

            # Clear the actual entry widgets if they exist
            if self.filter_sample_id_entry:
                self.filter_sample_id_entry.delete(0, tk.END)
            if self.filter_batch_id_entry:
                self.filter_batch_id_entry.delete(0, tk.END)
            if self.filter_product_name_entry:
                self.filter_product_name_entry.delete(0, tk.END)
            if self.filter_status_combobox:
                self.filter_status_combobox.set("")
            logging.info("Sample filters cleared.")
        elif self.filter_mode.get() == "batch_search" and self.find_batch_id_entry:
            self.find_batch_id_entry.delete(0, tk.END)
            logging.info("Batch search filter cleared.")
        elif self.filter_mode.get() == "sample_search" and self.find_sample_id_entry:  # Clear sample search field
            self.find_sample_id_entry.delete(0, tk.END)
            logging.info("Sample search filter cleared.")

        # Always reload all samples (paginated) and reset all pagination states after clearing filters
        self.load_samples_paginated(query_type='all_samples', reset=True)
        form_window.destroy()
        logging.info("Filters cleared and all samples reloaded.")

    def delete_batch(self):
        """Deletes a selected batch and all its associated samples from Firestore."""
        logging.info("Starting delete_batch process.")
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a batch to delete.")
            logging.warning("Delete batch aborted: No batch selected.")
            return

        item = self.tree.item(selected[0])
        # Ensure the selected item is actually a batch based on `last_loaded_query_type`
        if self.last_loaded_query_type not in ['batches', 'my_batches', 'todays_batches']:
            messagebox.showwarning("Warning",
                                   "Please select a batch to delete (currently displaying samples or unknown data type).")
            logging.warning("Selected item is not a batch. Delete batch aborted.")
            return

        firestore_batch_doc_id = item['values'][0]
        # BatchID is at index 5 in the Treeview values for batches
        batch_id_display = item['values'][5]

        logging.info(f"Attempting to delete batch: DocID='{firestore_batch_doc_id}', BatchID='{batch_id_display}'")

        confirm = messagebox.askyesno("Confirm Delete Batch",
                                      f"Are you sure you want to delete Batch '{batch_id_display}'?\n\n"
                                      "This will PERMANENTLY DELETE ALL SAMPLES associated with this batch as well. This action cannot be undone.")
        if not confirm:
            logging.info("Delete batch aborted: User cancelled.")
            return

        try:
            batch_write = db.batch()

            # Delete all samples associated with this batch
            samples_to_delete = db.collection("samples").where("batch_id", "==", batch_id_display).stream()
            deleted_samples_count = 0
            for sample_doc in samples_to_delete:
                batch_write.delete(sample_doc.reference)
                deleted_samples_count += 1
            logging.info(f"Prepared to delete {deleted_samples_count} samples for batch '{batch_id_display}'.")

            # Delete the batch document itself
            batch_doc_ref = db.collection("batches").document(firestore_batch_doc_id)
            batch_write.delete(batch_doc_ref)
            logging.info(f"Prepared to delete batch document: {firestore_batch_doc_id}.")

            batch_write.commit()
            logging.info("Firestore batch committed successfully (batch and samples deleted).")

            messagebox.showinfo("Success",
                                f"Batch '{batch_id_display}' and its {deleted_samples_count} associated samples deleted successfully.")
            logging.info(f"Batch '{batch_id_display}' and its samples deleted.")

            # Refresh the Treeview to reflect the deletion
            if self.last_loaded_query_type == 'batches':
                self.load_all_batches_to_tree()
            elif self.last_loaded_query_type == 'my_batches':
                self.load_my_batches_to_tree()
            elif self.last_loaded_query_type == 'todays_batches':
                self.load_todays_batches_to_tree()
            else:
                self.load_all_batches_to_tree()

            if hasattr(self.app, 'admin_logic'):
                self.app.admin_logic.load_batches()

            logging.info("Batch data reloaded and tree refreshed after deletion.")

        except Exception as e:
            logging.error(f"Failed to delete batch '{batch_id_display}': {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to delete batch and its samples:\n{e}")

