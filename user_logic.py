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
# Configure logging to show INFO messages and above, with timestamp and log level
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

        # Elements for forms (will be created dynamically)
        self.existing_batch_combobox = None
        self.new_batch_product_name = None
        self.new_batch_description = None
        self.entry_sample_display_id = None
        self.entry_owner_combobox = None
        self.entry_maturation_date_entry = None
        self.status_combobox = None

        # Filter form elements
        self.filter_maturation_date_var = tk.BooleanVar(value=False) # New: for optional maturation date filter
        self.filter_creation_date_var = tk.BooleanVar(value=False)   # New: for optional creation date filter

        self.filter_start_date_entry = None
        self.filter_end_date_entry = None
        self.filter_creation_start_date_entry = None
        self.filter_creation_end_date_entry = None
        self.filter_sample_id_entry = None
        self.filter_batch_id_entry = None # For sample filtering by batch ID
        self.filter_product_name_entry = None

        # New: Filter mode and specific batch search entry
        self.filter_mode = tk.StringVar(value="samples") # 'samples' or 'batch_search'
        self.find_batch_id_entry = None # Entry for finding a specific batch by ID
        self.sample_filters_frame = None # Frame to hold sample filtering widgets
        self.batch_search_frame = None   # Frame to hold batch search widget

        # Frames to hold the optional date filters within sample_filters_frame
        self.maturation_date_filter_frame = None
        self.creation_date_filter_frame = None

        # Pagination variables
        self.current_page_index = 0 # 0-based index for the current page being displayed
        self.samples_per_page = 100 # Default samples per page
        self.all_samples_page_cursors = [] # Stores the last document of each page for 'Load All Samples'
        self.my_samples_page_cursors = []  # Stores the last document of each page for 'Load My Samples'
        self.last_loaded_query_type = None # To distinguish between 'all_samples' and 'my_samples' for pagination

        # Pagination UI elements (initialized in user_dashboard)
        self.page_info_label = None
        self.prev_sample_page_btn = None
        self.next_sample_page_btn = None

        logging.info("UserLogic initialized.")


    def user_dashboard(self):
        """Displays the user dashboard with sample management features."""
        logging.info("Entering user_dashboard method.")
        self.app.clear_root()
        self.root.geometry("1000x600")
        self.excel_imported = False
        self.current_selected_batch_id = None
        
        # Reset pagination state
        self.current_page_index = 0
        self.all_samples_page_cursors = []
        self.my_samples_page_cursors = []
        self.last_loaded_query_type = None

        # === Menu Bar ===
        menubar = tk.Menu(self.root)
        
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Import Excel (Local)", command=self.import_excel)
        filemenu.add_command(label="Export Excel (Local)", command=self.export_excel)
        menubar.add_cascade(label="File", menu=filemenu)

        # Load Menu (Dropdown)
        loadmenu = tk.Menu(menubar, tearoff=0)
        loadmenu.add_command(label="Load All Samples", command=lambda: self.load_samples_paginated('all_samples', reset=True))
        loadmenu.add_command(label="Load My Samples", command=lambda: self.load_samples_paginated('my_samples', reset=True))
        loadmenu.add_separator()
        loadmenu.add_command(label="Load All Batches", command=self.load_all_batches_to_tree)
        loadmenu.add_command(label="Load My Batches", command=self.load_my_batches_to_tree)
        menubar.add_cascade(label="Load", menu=loadmenu)

        # Logout button (right-aligned in menubar)
        logout_menu = tk.Menu(menubar, tearoff=0)
        logout_menu.add_command(label="Logout", command=self.app.logout)
        menubar.add_cascade(label="Logout", menu=logout_menu) 

        self.root.config(menu=menubar)

        # === Toolbar Frame for Buttons and Pagination ===
        toolbar = tk.Frame(self.root, pady=10)
        toolbar.pack(fill="x", padx=10)

        # Standalone "Load Today's Batches" button
        ttk.Button(toolbar, text="Load Today's Batches", command=self.load_todays_batches_to_tree).pack(side=tk.LEFT, padx=5)

        # Pagination Controls for samples
        pagination_frame = ttk.Frame(toolbar)
        pagination_frame.pack(side=tk.LEFT, padx=10)

        self.prev_sample_page_btn = ttk.Button(pagination_frame, text="Previous", command=lambda: self.navigate_samples_page('prev'), state=tk.DISABLED)
        self.prev_sample_page_btn.pack(side=tk.LEFT, padx=2)

        self.page_info_label = ttk.Label(pagination_frame, text="Page 1 of 1")
        self.page_info_label.pack(side=tk.LEFT, padx=5)

        self.next_sample_page_btn = ttk.Button(pagination_frame, text="Next", command=lambda: self.navigate_samples_page('next'), state=tk.DISABLED)
        self.next_sample_page_btn.pack(side=tk.LEFT, padx=2)
        
        # Existing action buttons
        ttk.Button(toolbar, text="Generate Barcode", command=self.generate_barcode).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Check Notifications", command=self.check_notifications).pack(side=tk.LEFT, padx=5)
        self.add_sample_main_button = ttk.Button(toolbar, text="Add Sample to Batch", command=self.open_batch_selection_screen)
        self.add_sample_main_button.pack(side=tk.LEFT, padx=5)
        self.add_single_sample_button = ttk.Button(toolbar, text="Add Single Sample to Current Batch", command=self.open_single_sample_form, state=tk.DISABLED)
        self.add_single_sample_button.pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Edit Sample", command=self.edit_sample).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Delete Sample", command=self.delete_sample).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Filter Samples/Find Batch", command=self.open_filter_form).pack(side=tk.LEFT, padx=5)


        # === Treeview for Data Display ===
        # Columns for samples: "DocID", "DisplaySampleID", "Owner", "MaturationDate", "Status", "BatchID", "CreationDate"
        # Columns for batches: "DocID", "BatchID", "ProductName", "Description", "SubmissionDate", "NumberOfSamples"
        self.tree = ttk.Treeview(self.root, columns=["DocID", "DisplaySampleID", "Owner", "MaturationDate", "Status", "BatchID", "CreationDate", "ProductName", "Description", "SubmissionDate", "NumberOfSamples"], show='headings')

        # Define headings and initial column widths, many will be hidden initially or adjust based on data type
        self.tree.heading("DocID", text="Doc ID")
        self.tree.column("DocID", width=0, stretch=tk.NO) # Hidden by default for samples and batches

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

        # Batch specific columns (initially narrow/hidden, expanded when batch data is loaded)
        self.tree.heading("ProductName", text="Product Name")
        self.tree.column("ProductName", width=0, stretch=tk.NO) # Hidden

        self.tree.heading("Description", text="Description")
        self.tree.column("Description", width=0, stretch=tk.NO) # Hidden

        self.tree.heading("SubmissionDate", text="Submission Date")
        self.tree.column("SubmissionDate", width=0, stretch=tk.NO) # Hidden

        self.tree.heading("NumberOfSamples", text="Num Samples")
        self.tree.column("NumberOfSamples", width=0, stretch=tk.NO) # Hidden

        self.tree.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # === Status Bar ===
        self.status_label = tk.Label(self.root, text="Load samples from DB or import Excel.", anchor='w', bd=1, relief=tk.SUNKEN)
        self.status_label.pack(fill=tk.X, padx=10, pady=5)

        # Initial load when dashboard opens
        self.load_samples_paginated(query_type='all_samples', reset=True)
        logging.info("User dashboard loaded.")

    def load_samples_to_treeview(self, samples_list, is_pagination_load=False, current_page=1, total_pages=1):
        """Populates the Treeview widget with the given list of samples.
        Adjusts column visibility based on context (samples vs batches)."""
        logging.info(f"Populating samples treeview. Pagination Load: {is_pagination_load}, Current Page: {current_page}, Total Pages: {total_pages}")
        # Always clear for a fresh load, or if not a direct pagination "next/prev" click
        if not is_pagination_load:
            self.tree.delete(*self.tree.get_children())
            self.app.data = pd.DataFrame(columns=COLUMNS + ["DocID"]) # Reset DataFrame for new data

        # Set sample-specific columns visible and batch-specific columns hidden
        sample_cols = ["DisplaySampleID", "Owner", "MaturationDate", "Status", "BatchID", "CreationDate"]
        batch_cols = ["ProductName", "Description", "SubmissionDate", "NumberOfSamples"]

        for col in sample_cols:
            self.tree.column(col, width=100 if col != "MaturationDate" else 120, stretch=tk.YES)
        for col in batch_cols:
            self.tree.column(col, width=0, stretch=tk.NO) # Hide batch columns

        if samples_list:
            df = pd.DataFrame(samples_list)
            # Ensure consistent column names for display
            df.rename(columns={
                "firestore_doc_id": "DocID",
                "sample_id": "DisplaySampleID",
                "owner": "Owner",
                "maturation_date": "MaturationDate",
                "status": "Status",
                "batch_id": "BatchID",
                "creation_date": "CreationDate"
            }, inplace=True)

            # Add missing columns with None to ensure DataFrame structure
            for col in ["DocID", "DisplaySampleID", "Owner", "MaturationDate", "Status", "BatchID", "CreationDate"]:
                if col not in df.columns:
                    df[col] = None
            
            # For pagination, we replace the data for the current page
            self.app.data = df

            for index, row in df.iterrows(): # Iterate over the newly loaded chunk for display
                mat_date_str = "N/A"
                creation_date_str = "N/A"

                mat_date = row.get('MaturationDate')
                # Robustly convert to datetime if it's a Firestore Timestamp or other date-like object
                if mat_date is not None:
                    if hasattr(mat_date, 'to_datetime'):
                        mat_date_dt = mat_date.to_datetime()
                    elif isinstance(mat_date, datetime):
                        mat_date_dt = mat_date
                    else: # Try parsing as string if not datetime or Timestamp
                        try:
                            mat_date_dt = datetime.strptime(str(mat_date).split(' ')[0], "%Y-%m-%d") # handle potential time part
                        except ValueError:
                            mat_date_dt = None

                    if mat_date_dt:
                        mat_date_str = mat_date_dt.strftime("%Y-%m-%d")

                creation_date = row.get('CreationDate')
                # Robustly convert to datetime if it's a Firestore Timestamp or other date-like object
                if creation_date is not None:
                    if hasattr(creation_date, 'to_datetime'):
                        creation_date_dt = creation_date.to_datetime()
                    elif isinstance(creation_date, datetime):
                        creation_date_dt = creation_date
                    else: # Try parsing as string if not datetime or Timestamp
                        try:
                            creation_date_dt = datetime.strptime(str(creation_date).split(' ')[0], "%Y-%m-%d") # handle potential time part
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
                                         '', '', '', '')) # Empty values for batch columns
            
            self.status_label.config(text=f"Loaded {len(self.app.data)} samples. Page {current_page} of {total_pages}.")
            self.page_info_label.config(text=f"Page {current_page} of {total_pages}")
        else:
            self.status_label.config(text="No samples found.")
            self.page_info_label.config(text="Page 0 of 0")
            logging.info("No samples to display.")

        # Update pagination button states
        self.prev_sample_page_btn.config(state=tk.NORMAL if current_page > 1 else tk.DISABLED)
        self.next_sample_page_btn.config(state=tk.NORMAL if current_page < total_pages else tk.DISABLED)
        logging.info("Samples treeview populated and pagination buttons updated.")

    def load_batches_to_treeview(self, batches_list):
        """Populates the Treeview widget with the given list of batches.
        Adjusts column visibility for batch display."""
        logging.info(f"Populating batches treeview with {len(batches_list)} batches.")
        self.tree.delete(*self.tree.get_children())
        self.app.data = pd.DataFrame() # Clear DataFrame for new data

        # Set batch-specific columns visible and sample-specific columns hidden
        sample_cols = ["DisplaySampleID", "Owner", "MaturationDate", "Status", "CreationDate"]
        batch_cols = ["BatchID", "ProductName", "Description", "SubmissionDate", "NumberOfSamples"]

        for col in sample_cols:
            self.tree.column(col, width=0, stretch=tk.NO) # Hide sample columns
        for col in batch_cols:
            self.tree.column(col, width=100, stretch=tk.YES) # Show batch columns
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
                                 values=(row.get('DocID', ''), # DocID still present but usually hidden
                                         '', '', '', '', # Empty for sample columns
                                         row.get('BatchID', 'N/A'),
                                         '', # Empty for sample CreationDate
                                         row.get('ProductName', 'N/A'),
                                         row.get('Description', 'N/A'),
                                         submission_date_str,
                                         row.get('NumberOfSamples', 0)))
            self.status_label.config(text=f"Loaded {len(self.app.data)} batches.")
        else:
            self.status_label.config(text="No batches found.")

        # Disable sample-specific buttons when showing batches
        self.add_single_sample_button.config(state=tk.DISABLED)
        # Disable pagination buttons when showing batches
        self.prev_sample_page_btn.config(state=tk.DISABLED)
        self.next_sample_page_btn.config(state=tk.DISABLED)
        self.page_info_label.config(text="Page 0 of 0")
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
        else:
            messagebox.showwarning("Navigation Error", "Cannot navigate pages for the current view type. Please load all samples or my samples first.")
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
            
            if query_type == 'all_samples':
                self.last_loaded_query_type = 'all_samples'
                if reset:
                    self.current_page_index = 0
                    self.all_samples_page_cursors = []
                
                query = samples_ref.order_by("creation_date").limit(self.samples_per_page)
                if self.current_page_index > 0 and len(self.all_samples_page_cursors) > self.current_page_index - 1:
                    # If we are navigating, use the cursor for the start of the current page
                    start_after_doc = self.all_samples_page_cursors[self.current_page_index - 1]
                    query = query.start_after(start_after_doc)
                logging.info(f"Building query for all samples. Current page index: {self.current_page_index}, Cursor count: {len(self.all_samples_page_cursors)}")

            elif query_type == 'my_samples':
                if not self.app.current_user or not self.app.current_user.get('employee_id'):
                    messagebox.showwarning("Warning", "User not logged in or employee ID not found.")
                    self.status_label.config(text="Cannot load my samples: User not identified.")
                    logging.warning("Attempted to load 'my_samples' without a logged-in user or employee ID.")
                    return
                
                self.last_loaded_query_type = 'my_samples'
                if reset:
                    self.current_page_index = 0
                    self.my_samples_page_cursors = []

                # Ensure 'submitted_by_employee_id' field exists in your 'samples' collection
                # And you have a composite index for (submitted_by_employee_id, creation_date)
                query = samples_ref.where("submitted_by_employee_id", "==", self.app.current_user['employee_id']).order_by("creation_date").limit(self.samples_per_page)
                if self.current_page_index > 0 and len(self.my_samples_page_cursors) > self.current_page_index - 1:
                    start_after_doc = self.my_samples_page_cursors[self.current_page_index - 1]
                    query = query.start_after(start_after_doc)
                logging.info(f"Building query for my samples (user: {self.app.current_user['employee_id']}). Current page index: {self.current_page_index}, Cursor count: {len(self.my_samples_page_cursors)}")
            else:
                logging.error(f"Invalid query_type passed to load_samples_paginated: {query_type}")
                return # Should not happen with valid query_type

            docs = list(query.stream())
            logging.info(f"Fetched {len(docs)} documents for page {self.current_page_index + 1}.")
            samples_list = []
            for doc in docs:
                data = doc.to_dict()
                data['firestore_doc_id'] = doc.id
                # Convert Firestore Timestamp to datetime objects
                if data.get('maturation_date') and hasattr(data['maturation_date'], 'to_datetime'):
                    data['maturation_date'] = data['maturation_date'].to_datetime()
                if data.get('creation_date') and hasattr(data['creation_date'], 'to_datetime'):
                    data['creation_date'] = data['creation_date'].to_datetime()
                samples_list.append(data)
            
            # Determine total count for page info
            total_count = 0
            if query_type == 'all_samples':
                aggregate_query = db.collection("samples").count()
                aggregate_query_snapshot = aggregate_query.get()
                
                if aggregate_query_snapshot:
                    try:
                        total_count = aggregate_query_snapshot[0].value
                    except IndexError:
                        logging.warning("AggregateQuerySnapshot was empty, cannot get count value via [0].")
                        total_count = 0 # No results, so count is 0
                    except AttributeError as ae:
                        logging.error(f"AggregateResult object at index 0 does not have 'value' attribute: {ae}", exc_info=True)
                        logging.error(f"Type of aggregate_query_snapshot[0]: {type(aggregate_query_snapshot[0])}")
                        total_count = 0 # Cannot get count, default to 0
                    except Exception as unexpected_e:
                        logging.error(f"Unexpected error when getting total count for all samples: {unexpected_e}", exc_info=True)
                        total_count = 0
                logging.info(f"Total count for all samples: {total_count}")
                
                if docs and len(docs) == self.samples_per_page:
                    if len(self.all_samples_page_cursors) == self.current_page_index:
                        self.all_samples_page_cursors.append(docs[-1])
                    else: 
                        self.all_samples_page_cursors[self.current_page_index] = docs[-1]
                elif not docs and self.current_page_index > 0: # If navigating next and no docs found, means end of data
                    logging.info("Reached end of 'all_samples' data during pagination.")

            elif query_type == 'my_samples':
                aggregate_query = db.collection("samples").where("submitted_by_employee_id", "==", self.app.current_user['employee_id']).count()
                aggregate_query_snapshot = aggregate_query.get()
                
                if aggregate_query_snapshot:
                    try:
                        total_count = aggregate_query_snapshot[0].value
                    except IndexError:
                        logging.warning("AggregateQuerySnapshot was empty, cannot get count value via [0].")
                        total_count = 0 # No results, so count is 0
                    except AttributeError as ae:
                        logging.error(f"AggregateResult object at index 0 does not have 'value' attribute: {ae}", exc_info=True)
                        logging.error(f"Type of aggregate_query_snapshot[0]: {type(aggregate_query_snapshot[0])}")
                        total_count = 0 # Cannot get count, default to 0
                    except Exception as unexpected_e:
                        logging.error(f"Unexpected error when getting total count for my samples: {unexpected_e}", exc_info=True)
                        total_count = 0
                logging.info(f"Total count for my samples: {total_count}")
                
                if docs and len(docs) == self.samples_per_page:
                    if len(self.my_samples_page_cursors) == self.current_page_index:
                        self.my_samples_page_cursors.append(docs[-1])
                    else:
                        self.my_samples_page_cursors[self.current_page_index] = docs[-1]
                elif not docs and self.current_page_index > 0: # If navigating next and no docs found, means end of data
                    logging.info("Reached end of 'my_samples' data during pagination.")

            total_pages = (total_count + self.samples_per_page - 1) // self.samples_per_page if total_count > 0 else 1
            logging.info(f"Calculated total pages: {total_pages}")
            
            self.load_samples_to_treeview(samples_list, is_pagination_load=True, current_page=self.current_page_index + 1, total_pages=total_pages)

        except Exception as e:
            logging.error(f"Failed to load samples paginated: {e}", exc_info=True) # exc_info to get full traceback
            messagebox.showerror("Error", f"Failed to load samples: {e}")
            self.status_label.config(text="Failed to load samples.")
            # Ensure buttons are disabled on error
            self.prev_sample_page_btn.config(state=tk.DISABLED)
            self.next_sample_page_btn.config(state=tk.DISABLED)
            self.page_info_label.config(text="Page 0 of 0")


    def load_all_batches_to_tree(self):
        """Loads all batches from Firestore and displays them in the Treeview."""
        logging.info("Loading all batches to tree.")
        # Reset sample pagination state when loading batches
        self.current_page_index = 0
        self.all_samples_page_cursors = []
        self.my_samples_page_cursors = []
        
        self.last_loaded_query_type = 'batches'

        try:
            batches_ref = db.collection("batches")
            batches_list = []
            for batch_doc in batches_ref.stream():
                data = batch_doc.to_dict()
                data['firestore_doc_id'] = batch_doc.id # Store Firestore document ID
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
        # Reset sample pagination state when loading batches
        self.current_page_index = 0
        self.all_samples_page_cursors = []
        self.my_samples_page_cursors = []

        self.last_loaded_query_type = 'my_batches'

        try:
            if not self.app.current_user or not self.app.current_user.get('employee_id'):
                messagebox.showwarning("Warning", "User not logged in or employee ID not found.")
                self.status_label.config(text="Cannot load my batches: User not identified.")
                logging.warning("Attempted to load 'my_batches' without a logged-in user or employee ID.")
                return

            batches_ref = db.collection("batches")
            batches_list = []
            # Make sure 'user_employee_id' field exists in your 'batches' collection
            # And you have an index for this field (or composite with submission_date if needed)
            for batch_doc in batches_ref.where("user_employee_id", "==", self.app.current_user['employee_id']).stream():
                data = batch_doc.to_dict()
                data['firestore_doc_id'] = batch_doc.id
                # Convert Firestore Timestamp to datetime object
                if data.get('submission_date') and hasattr(data['submission_date'], 'to_datetime'):
                    data['submission_date'] = data['submission_date'].to_datetime()
                batches_list.append(data)
            self.load_batches_to_treeview(batches_list)
            logging.info(f"Successfully loaded {len(batches_list)} my batches for user {self.app.current_user['employee_id']}.")
        except Exception as e:
            logging.error(f"Failed to load my batches: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load my batches: {e}")
            self.status_label.config(text="Failed to load my batches.")

    def load_todays_batches_to_tree(self):
        """Loads batches submitted today from Firestore."""
        logging.info("Loading today's batches to tree.")
        # Reset sample pagination state when loading batches
        self.current_page_index = 0
        self.all_samples_page_cursors = []
        self.my_samples_page_cursors = []

        self.last_loaded_query_type = 'todays_batches'

        try:
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
            logging.info(f"Fetching batches from {today_start} to {today_end}")

            batches_ref = db.collection("batches")
            batches_list = []
            # Firestore requires an index on 'submission_date' for range queries.
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


    def import_excel(self):
        """Imports data from an Excel file into the application's local DataFrame.
        This data is only for temporary local use and is not automatically linked to a batch in DB."""
        logging.info("Attempting to import Excel file.")
        filetypes = (("Excel files", "*.xlsx *.xls"), ("All files", "*.*"))
        filename = filedialog.askopenfilename(title="Open Excel file", filetypes=filetypes)
        if filename:
            try:
                self.app.data = pd.read_excel(filename)
                if 'Status' not in self.app.data.columns:
                    self.app.data['Status'] = 'pending'
                if 'BatchID' not in self.app.data.columns:
                    self.app.data['BatchID'] = 'N/A (Local)'
                if 'SampleID' in self.app.data.columns:
                    self.app.data.rename(columns={'SampleID': 'DisplaySampleID'}, inplace=True)
                if 'CreationDate' not in self.app.data.columns:
                    self.app.data['CreationDate'] = None
                self.app.data['DocID'] = 'N/A (Local)'

                # Reset sample pagination state when importing excel
                self.current_page_index = 0
                self.all_samples_page_cursors = []
                self.my_samples_page_cursors = []
                self.last_loaded_query_type = 'excel_import' # Indicate data source is local excel

                self.app.file_path = filename
                self.load_samples_to_treeview(self.app.data.to_dict('records'), is_pagination_load=True) # Use the refactored function
                self.status_label.config(text=f"Loaded data from {os.path.basename(filename)} (Local)")
                self.excel_imported = True

                self.current_selected_batch_id = None
                self.add_single_sample_button.config(state=tk.DISABLED)

                # Disable pagination controls for local excel
                self.prev_sample_page_btn.config(state=tk.DISABLED)
                self.next_sample_page_btn.config(state=tk.DISABLED)
                self.page_info_label.config(text="Page 0 of 0")
                logging.info(f"Successfully imported data from {filename}.")

            except Exception as e:
                logging.error(f"Failed to load Excel file: {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to load Excel file:\n{e}")

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
                df_to_export = self.app.data.copy()
                if 'BatchID' in df_to_export.columns:
                    df_to_export.rename(columns={'BatchID': 'batch_id'}, inplace=True)
                if 'DisplaySampleID' in df_to_export.columns:
                    df_to_export.rename(columns={'DisplaySampleID': 'SampleID'}, inplace=True)
                if 'DocID' in df_to_export.columns:
                    df_to_export = df_to_export.drop(columns=['DocID'])
                if 'CreationDate' in df_to_export.columns:
                    df_to_export.rename(columns={'CreationDate': 'creation_date'}, inplace=True)
                if 'MaturationDate' in df_to_export.columns: # Ensure maturation_date is handled correctly
                    df_to_export.rename(columns={'MaturationDate': 'maturation_date'}, inplace=True)

                for col in df_to_export.columns:
                    if pd.api.types.is_datetime64_any_dtype(df_to_export[col]):
                        if df_to_export[col].dt.tz is not None:
                            df_to_export[col] = df_to_export[col].dt.tz_localize(None)

                df_to_export.to_excel(filename, index=False)
                self.status_label.config(text=f"Data exported to {os.path.basename(filename)}")
                logging.info(f"Successfully exported data to {filename}.")
            except Exception as e:
                logging.error(f"Failed to export Excel file: {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to export Excel file:\n{e}")

    def refresh_tree(self):
        """Refreshes the Treeview widget with the current DataFrame data.
        This method is now a wrapper that calls `load_samples_to_treeview`
        or `load_batches_to_treeview` based on `last_loaded_query_type`."""
        logging.info(f"Refreshing tree. Last loaded query type: {self.last_loaded_query_type}")
        if self.last_loaded_query_type in ['all_samples', 'my_samples', 'filtered_samples', 'current_batch_samples', 'excel_import']:
            # For samples, simply reload the current DataFrame
            # For paginated sample views, call the paginated loader with current page
            if self.last_loaded_query_type in ['all_samples', 'my_samples']:
                self.load_samples_paginated(self.last_loaded_query_type, reset=False) # Reload current page
            else: # For filtered or current_batch samples (non-paginated views)
                self.load_samples_to_treeview(self.app.data.to_dict('records'))
        elif self.last_loaded_query_type in ['batches', 'my_batches', 'todays_batches']:
            # For batches, simply reload the current DataFrame
            self.load_batches_to_treeview(self.app.data.to_dict('records'))
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
        # Ensure that the item selected is a sample, not a batch, by checking if DisplaySampleID column is visible/used
        if self.tree.column("DisplaySampleID", option="width") == 0:
            messagebox.showwarning("Warning", "Please select a sample to generate a barcode (currently displaying batches).")
            logging.warning("Selected item is a batch, not a sample. Barcode generation aborted.")
            return

        sample_id_for_barcode = str(item['values'][1]) if len(item['values']) > 1 else ""

        if not sample_id_for_barcode:
            messagebox.showerror("Error", "Selected sample has no valid Sample ID for barcode generation.")
            logging.error("Selected sample has no valid Sample ID for barcode generation.")
            return

        try:
            EAN = barcode.get_barcode_class('code128')
            ean = EAN(sample_id_for_barcode, writer=ImageWriter())
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
        if self.last_loaded_query_type not in ['all_samples', 'my_samples', 'filtered_samples', 'current_batch_samples', 'excel_import'] and 'MaturationDate' not in self.app.data.columns:
             messagebox.showwarning("Warning", "Notifications are for samples only. Please load samples first.")
             logging.warning("Notification check attempted when batches are displayed or no MaturationDate column.")
             return

        today = datetime.now()
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
                    # Attempt to convert Firestore Timestamp if present, or string
                    if hasattr(mat_date, 'to_datetime'):
                        mat_date_dt = mat_date.to_datetime()
                    else:
                        mat_date_dt = datetime.strptime(str(mat_date).split(' ')[0], "%Y-%m-%d") # handle potential time part
                except (ValueError, TypeError):
                    logging.warning(f"Could not parse maturation date for sample: {row.get('DisplaySampleID', 'N/A')}. Value: {mat_date}")
                    continue

            if mat_date_dt:
                delta = mat_date_dt - today
                if 0 <= delta.days <= NOTIFICATION_DAYS_BEFORE:
                    notifications.append(f"Sample {row.get('DisplaySampleID', 'N/A')} owned by {row.get('Owner', 'N/A')} matures on {mat_date_dt.strftime('%Y-%m-%d')}.")

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
        batch_selection_form.geometry("500x320")
        batch_selection_form.grab_set()
        batch_selection_form.transient(self.root)

        frame = ttk.Frame(batch_selection_form, padding=10)
        frame.pack(expand=True, fill="both")

        self.batch_choice = tk.StringVar(value="existing")
        radio_existing = ttk.Radiobutton(frame, text="Select Existing Batch", variable=self.batch_choice, value="existing")
        radio_new = ttk.Radiobutton(frame, text="Create New Batch", variable=self.batch_choice, value="new")

        radio_existing.grid(row=0, column=0, columnspan=2, sticky="w", pady=5)
        radio_new.grid(row=1, column=0, columnspan=2, sticky="w", pady=5)

        ttk.Label(frame, text="Existing Batch ID:").grid(row=2, column=0, sticky="e", pady=5, padx=5)
        self.existing_batch_combobox = ttk.Combobox(frame, state="readonly", width=30)
        self.existing_batch_combobox.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
        self._load_existing_batches_into_combobox()

        ttk.Label(frame, text="New Product Name:").grid(row=3, column=0, sticky="e", pady=5, padx=5)
        self.new_batch_product_name = ttk.Entry(frame, width=30, state="disabled")
        self.new_batch_product_name.grid(row=3, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(frame, text="New Description:").grid(row=4, column=0, sticky="e", pady=5, padx=5)
        self.new_batch_description = ttk.Entry(frame, width=30, state="disabled")
        self.new_batch_description.grid(row=4, column=1, sticky="ew", pady=5, padx=5)

        radio_existing.config(command=lambda: self._toggle_batch_fields_on_selection(True))
        radio_new.config(command=lambda: self._toggle_batch_fields_on_selection(False))

        self._toggle_batch_fields_on_selection(True)

        ttk.Button(frame, text="Confirm Batch Selection", command=lambda: self._handle_batch_selection_confirmation(batch_selection_form)).grid(row=5, column=0, columnspan=2, pady=20)
        batch_selection_form.protocol("WM_DELETE_WINDOW", batch_selection_form.destroy)
        logging.info("Batch selection screen opened.")

    def _toggle_batch_fields_on_selection(self, is_existing_batch_selected):
        """Internal helper to toggle the visibility/state of new/existing batch fields."""
        logging.debug(f"Toggling batch fields. Is existing batch selected: {is_existing_batch_selected}")
        try:
            if self.existing_batch_combobox:
                self.existing_batch_combobox.config(state="readonly" if is_existing_batch_selected else "disabled")
                if not is_existing_batch_selected:
                    self.existing_batch_combobox.set('')
        except Exception as e:
            logging.warning(f"Error configuring existing_batch_combobox: {e}")

        try:
            if self.new_batch_product_name:
                self.new_batch_product_name.config(state="normal" if not is_existing_batch_selected else "disabled")
                if is_existing_batch_selected: # If switching to existing, clear and disable new batch fields
                    self.new_batch_product_name.delete(0, tk.END)
        except Exception as e:
            logging.warning(f"Error configuring new_batch_product_name: {e}")

        try:
            if self.new_batch_description:
                self.new_batch_description.config(state="normal" if not is_existing_batch_selected else "disabled")
                if is_existing_batch_selected: # If switching to existing, clear and disable new batch fields
                    self.new_batch_description.delete(0, tk.END)
        except Exception as e:
            logging.warning(f"Error configuring new_batch_description: {e}")
        logging.debug("Batch fields toggled.")


    def _load_existing_batches_into_combobox(self):
        """Loads batch IDs from Firestore into the combobox."""
        logging.info("Loading existing batches into combobox.")
        batches_ref = db.collection("batches")
        try:
            # Ensure 'user_employee_id' field exists in your 'batches' collection and is indexed.
            # Otherwise, this query will fail or be very slow.
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

            # Generating a unique batch ID. Using Firestore's auto-ID for documents is usually simpler.
            # If you want a human-readable prefix, you can combine it with Firestore auto-ID.
            # Example: selected_batch_id = f"BATCH_{db.collection('batches').document().id}"
            selected_batch_id = f"batch_{self.app.current_user['employee_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            # Check if generated ID exists (less likely with high-resolution timestamp, but good practice)
            if db.collection("batches").document(selected_batch_id).get().exists:
                messagebox.showerror("Error", "Generated Batch ID already exists. Please try again.")
                logging.error(f"Generated batch ID '{selected_batch_id}' already exists. Retrying generation might be needed.")
                return

            new_batch_data = {
                "batch_id": selected_batch_id, # This is a field, not the document ID
                "product_name": product_name,
                "description": description,
                "submission_date": creation_date_dt, # Storing datetime object
                "user_employee_id": self.app.current_user['employee_id'],
                "user_username": self.app.current_user['username'],
                "user_email": self.app.current_user['email'],
                "status": "pending approval", # Standardized status
                "number_of_samples": 0
            }
            try:
                # Use .set() with the custom ID you generated
                db.collection("batches").document(selected_batch_id).set(new_batch_data)
                messagebox.showinfo("Success", f"New batch '{selected_batch_id}' created successfully.")
                self.current_selected_batch_id = selected_batch_id
                self.load_samples_for_current_batch()
                if hasattr(self.app, 'admin_logic'):
                    self.app.admin_logic.load_batches()
                form_window.destroy()
                logging.info(f"New batch '{selected_batch_id}' created and samples loaded.")
            except Exception as e:
                logging.error(f"Failed to create new batch: {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to create new batch: {e}")
                return

        else: # Existing batch selected
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
                self.load_samples_for_current_batch()
                messagebox.showinfo("Batch Selected", f"Samples for batch '{selected_batch_id}' are now displayed.")
                form_window.destroy()
                logging.info(f"Existing batch '{selected_batch_id}' selected and samples loaded.")
            except Exception as e:
                logging.error(f"Failed to handle existing batch selection: {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to retrieve batch details: {e}")

    def load_samples_for_current_batch(self):
        """Loads samples only for the current_selected_batch_id and updates the Treeview."""
        logging.info(f"Loading samples for current batch: {self.current_selected_batch_id}")
        if not self.current_selected_batch_id:
            self.status_label.config(text="No batch selected to display samples.")
            logging.warning("load_samples_for_current_batch called with no current_selected_batch_id.")
            return

        # Reset sample pagination state when loading a specific batch
        self.current_page_index = 0
        self.all_samples_page_cursors = []
        self.my_samples_page_cursors = []
        
        self.last_loaded_query_type = 'current_batch_samples'

        self.tree.delete(*self.tree.get_children())
        samples_list = []
        try:
            samples_ref = db.collection("samples")
            # Ensure 'batch_id' field exists in your 'samples' collection and is indexed.
            samples = samples_ref.where("batch_id", "==", self.current_selected_batch_id).stream()

            for sample in samples:
                data = sample.to_dict()
                data['firestore_doc_id'] = sample.id
                # Convert Firestore Timestamp to datetime object
                if data.get('maturation_date') and hasattr(data['maturation_date'], 'to_datetime'):
                    data['maturation_date'] = data['maturation_date'].to_datetime()
                if data.get('creation_date') and hasattr(data['creation_date'], 'to_datetime'):
                    data['creation_date'] = data['creation_date'].to_datetime()
                samples_list.append(data)

            self.load_samples_to_treeview(samples_list) # Use the refactored function

            if samples_list:
                self.status_label.config(text=f"Loaded {len(self.app.data)} samples for Batch: {self.current_selected_batch_id}")
                logging.info(f"Loaded {len(samples_list)} samples for batch {self.current_selected_batch_id}.")
            else:
                self.status_label.config(text=f"No samples found for Batch: {self.current_selected_batch_id}")
                logging.info(f"No samples found for batch {self.current_selected_batch_id}.")

            self.add_single_sample_button.config(state=tk.NORMAL)
            # Disable pagination controls for specific batch load
            self.prev_sample_page_btn.config(state=tk.DISABLED)
            self.next_sample_page_btn.config(state=tk.DISABLED)
            self.page_info_label.config(text="Page 0 of 0")

        except Exception as e:
            logging.error(f"Failed to load samples for batch {self.current_selected_batch_id}: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load samples for batch: {e}")
            self.status_label.config(text="Failed to load samples for batch.")

    def open_single_sample_form(self):
        """Opens a form to add a single new sample to the currently selected batch."""
        logging.info(f"Opening single sample form for batch: {self.current_selected_batch_id}")
        if not self.current_selected_batch_id:
            messagebox.showwarning("Warning", "Please select or create a batch first using 'Add Sample to Batch' button.")
            logging.warning("open_single_sample_form called with no current_selected_batch_id.")
            return

        form = tk.Toplevel(self.root)
        form.title(f"Add Sample to Batch: {self.current_selected_batch_id}")
        form.geometry("400x300") # Adjusted height as checkbox is removed
        form.grab_set()
        form.transient(self.root)

        frame = ttk.Frame(form, padding=10)
        frame.pack(expand=True, fill="both")

        current_row = 0

        ttk.Label(frame, text="Batch ID:").grid(row=current_row, column=0, sticky="e", pady=5, padx=5)
        ttk.Label(frame, text=self.current_selected_batch_id, font=("Helvetica", 10, "bold")).grid(row=current_row, column=1, sticky="w", pady=5, padx=5)
        current_row += 1

        ttk.Label(frame, text="Sample ID (e.g., SMPL-001):").grid(row=current_row, column=0, sticky="e", pady=5, padx=5)
        self.entry_sample_display_id = ttk.Entry(frame, width=30)
        self.entry_sample_display_id.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        current_row += 1

        ttk.Label(frame, text="Sample Owner:").grid(row=current_row, column=0, sticky="e", pady=5, padx=5)
        self.entry_owner_combobox = ttk.Combobox(frame, state="readonly", width=27)
        self.entry_owner_combobox.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        self._load_users_into_owner_combobox(self.entry_owner_combobox)
        if self.app.current_user and self.app.current_user.get('username'):
            self.entry_owner_combobox.set(self.app.current_user['username'])
        current_row += 1

        # Maturation Date (no longer optional via checkbox here)
        ttk.Label(frame, text="Maturation Date (YYYY-MM-DD):").grid(row=current_row, column=0, sticky="e", pady=5, padx=5)
        self.entry_maturation_date_entry = DateEntry(frame, width=28, background='darkblue', foreground='white', borderwidth=2,
                                                     date_pattern='yyyy-mm-dd')
        self.entry_maturation_date_entry.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        self.entry_maturation_date_entry.set_date(datetime.now().date()) # Default to today
        current_row += 1

        ttk.Label(frame, text="Status:").grid(row=current_row, column=0, sticky="e", pady=5, padx=5)
        self.status_combobox = ttk.Combobox(frame, values=SAMPLE_STATUS_OPTIONS, state="readonly", width=27)
        self.status_combobox.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        self.status_combobox.set(SAMPLE_STATUS_OPTIONS[0]) # Default to "pending approval"
        current_row += 1

        ttk.Button(frame, text="Add Sample to Batch", command=lambda: self._submit_single_sample(form)).grid(row=current_row, column=0, columnspan=2, pady=15)
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

        # Maturation date is now always required and taken from the entry
        mat_date_from_entry = self.entry_maturation_date_entry.get_date()
        if not mat_date_from_entry or mat_date_from_entry == datetime(1,1,1).date():
            messagebox.showerror("Error", "Maturation Date is required.")
            logging.warning("Maturation Date is missing for single sample submission.")
            return
        mat_date_dt = datetime(mat_date_from_entry.year, mat_date_from_entry.month, mat_date_from_entry.day)

        sample_created_date_dt = datetime.now() # This remains automatic

        if not sample_display_id or not owner:
            messagebox.showerror("Error", "Sample ID and Owner are required.")
            logging.warning("Sample ID or Owner missing for single sample submission.")
            return

        try:
            # Checking for duplicate sample_id across the entire 'samples' collection
            # You might need an index on 'sample_id' for this query.
            existing_samples_with_display_id = db.collection("samples").where("sample_id", "==", sample_display_id).limit(1).get()
            if list(existing_samples_with_display_id): # Convert to list to check if it's empty
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
            "creation_date": sample_created_date_dt, # Storing datetime object
            "status": sample_status,
            "batch_id": self.current_selected_batch_id,
            "submitted_by_employee_id": self.app.current_user['employee_id'],
            "maturation_date": mat_date_dt # Storing datetime object
        }
        logging.debug(f"Sample data prepared: {sample_data}")

        try:
            batch_write = db.batch()

            # Let Firestore generate the document ID for the sample for true uniqueness
            sample_doc_ref = db.collection("samples").document()
            batch_write.set(sample_doc_ref, sample_data)
            logging.info(f"Prepared to add sample with auto-generated doc ID: {sample_doc_ref.id}")

            batch_doc_ref = db.collection("batches").document(self.current_selected_batch_id)
            if not batch_doc_ref.get().exists:
                messagebox.showwarning("Warning", f"Batch '{self.current_selected_batch_id}' not found. Sample added, but batch count not updated.")
                logging.warning(f"Batch '{self.current_selected_batch_id}' not found when adding sample. Batch count not updated.")
            else:
                batch_write.update(batch_doc_ref, {"number_of_samples": firebase_admin.firestore.Increment(1)})
                logging.info(f"Prepared to increment sample count for batch: {self.current_selected_batch_id}")

            batch_write.commit()
            logging.info("Firestore batch committed successfully.")

            messagebox.showinfo("Success", f"Sample '{sample_display_id}' added successfully to Batch '{self.current_selected_batch_id}'.")

            self.load_samples_for_current_batch()

            if hasattr(self.app, 'admin_logic'):
                self.app.admin_logic.load_batches()

            form_window.destroy()
            logging.info("Single sample submission complete.")

        except Exception as e:
            logging.error(f"Failed to add sample: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to add sample: {e}")

    def delete_sample(self):
        """Deletes a selected sample from Firestore."""
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

        logging.info(f"Extracted values for deletion: DocID='{firestore_doc_id}', DisplaySampleID='{display_sample_id}', BatchID='{batch_id}'")

        if not firestore_doc_id or firestore_doc_id == 'N/A (Local)':
            messagebox.showerror("Error", "Cannot delete a locally imported sample directly from the database. Please export and re-import if needed.")
            logging.error("Attempted to delete a local-only sample from the database.")
            return

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete sample '{display_sample_id}' from Batch '{batch_id}'?")
        if not confirm:
            logging.info("Delete sample aborted: User cancelled.")
            return

        try:
            logging.info("Attempting Firestore batch write operations for deletion...")
            batch_write = db.batch()

            sample_doc_ref = db.collection("samples").document(firestore_doc_id)
            logging.info(f"Prepared to delete sample document: {firestore_doc_id}")
            batch_write.delete(sample_doc_ref)

            if batch_id and batch_id != 'N/A':
                batch_doc_ref = db.collection("batches").document(batch_id)
                logging.info(f"Checking existence of batch document: {batch_id}")
                # Fetch batch document to ensure it exists before attempting update
                if batch_doc_ref.get().exists:
                    logging.info(f"Batch document '{batch_id}' exists. Preparing to decrement sample count.")
                    batch_write.update(batch_doc_ref, {"number_of_samples": firebase_admin.firestore.Increment(-1)})
                else:
                    logging.warning(f"Batch '{batch_id}' not found for sample '{display_sample_id}'. Cannot update sample count.")
            else:
                logging.warning(f"No valid Batch ID found for sample '{display_sample_id}' (BatchID was '{batch_id}'). Cannot update sample count.")

            logging.info("Committing batch write to Firestore...")
            batch_write.commit()
            logging.info("Firestore batch write committed successfully.")

            messagebox.showinfo("Success", f"Sample '{display_sample_id}' deleted successfully.")
            logging.info("Success message displayed.")

            # Refresh based on the last loaded query type
            if self.last_loaded_query_type in ['all_samples', 'my_samples']:
                # For paginated views, re-load the current page
                self.load_samples_paginated(self.last_loaded_query_type, reset=False)
            elif self.current_selected_batch_id:
                self.load_samples_for_current_batch()
            else:
                self.load_samples_paginated(query_type='all_samples', reset=True) # Default to all samples
            logging.info("Sample data reloaded and tree refreshed.")

            if hasattr(self.app, 'admin_logic'):
                logging.info("Updating admin_logic batches...")
                self.app.admin_logic.load_batches()
                logging.info("Admin_logic batches updated.")

            logging.info("Delete_sample process completed successfully.")

        except Exception as e:
            logging.error(f"Error during delete_sample: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to delete sample: {e}\nSample might have been deleted, but an issue occurred during UI update or batch count adjustment.")
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

        if not firestore_doc_id or firestore_doc_id == 'N/A (Local)':
            messagebox.showwarning("Warning", "Cannot edit locally imported samples directly. Please add them to a batch first.")
            logging.warning("Attempted to edit a local-only sample.")
            return

        row = {} # Initialize row dictionary
        try:
            sample_doc = db.collection("samples").document(firestore_doc_id).get()
            if not sample_doc.exists:
                messagebox.showerror("Error", "Selected sample not found in database.")
                logging.error(f"Sample with doc ID {firestore_doc_id} not found for editing.")
                if self.current_selected_batch_id:
                    self.load_samples_for_current_batch()
                else:
                    self.load_samples_paginated(query_type='all_samples', reset=True) # Default to all samples
                return
            row = sample_doc.to_dict()
            logging.info(f"Fetched sample data for editing (DocID: {firestore_doc_id}).")
        except Exception as e:
            logging.error(f"Failed to retrieve sample data for editing: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to retrieve sample data: {e}")
            return

        form = tk.Toplevel(self.root)
        form.title(f"Edit Sample {display_sample_id}")
        form.geometry("300x250") # Adjusted height as checkbox is removed
        form.grab_set()
        form.transient(self.root)

        current_row = 0

        tk.Label(form, text="Sample ID:").grid(row=current_row, column=0, sticky="e", pady=5, padx=5)
        entry_sample_display_id = ttk.Entry(form)
        entry_sample_display_id.insert(0, row.get('sample_id', ''))
        entry_sample_display_id.config(state='disabled') # Sample ID is usually not editable
        entry_sample_display_id.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        current_row += 1

        tk.Label(form, text="Sample Owner:").grid(row=current_row, column=0, sticky="e", pady=5, padx=5)
        edit_owner_combobox = ttk.Combobox(form, state="readonly")
        self._load_users_into_owner_combobox(edit_owner_combobox)
        edit_owner_combobox.set(row.get('owner', ''))
        edit_owner_combobox.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        current_row += 1

        # Maturation Date (no longer optional via checkbox here)
        tk.Label(form, text="Maturation Date (YYYY-MM-DD):").grid(row=current_row, column=0, sticky="e", pady=5, padx=5)
        self.edit_mat_date_entry = DateEntry(form, width=28, background='darkblue', foreground='white', borderwidth=2,
                                         date_pattern='yyyy-mm-dd')
        self.edit_mat_date_entry.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        
        # Set the current maturation date if available, otherwise default to a recognizable "empty" date
        mat_date_for_entry = None
        if isinstance(row.get('maturation_date'), datetime):
            mat_date_for_entry = row['maturation_date']
        elif row.get('maturation_date') and hasattr(row['maturation_date'], 'to_datetime'):
            try:
                mat_date_for_entry = row['maturation_date'].to_datetime()
            except Exception:
                pass # mat_date_for_entry remains None
        
        if mat_date_for_entry:
            self.edit_mat_date_entry.set_date(mat_date_for_entry)
        else:
            self.edit_mat_date_entry.set_date(datetime(1,1,1).date()) # Default to empty if no valid date
        current_row += 1

        tk.Label(form, text="Creation Date (YYYY-MM-DD):").grid(row=current_row, column=0, sticky="e", pady=5, padx=5)
        display_sample_created_date = DateEntry(form, width=28, background='lightgray', foreground='black', borderwidth=2,
                                         date_pattern='yyyy-mm-dd', state="disabled") # Disabled as it's typically fixed
        
        created_date_for_entry = None
        if isinstance(row.get('creation_date'), datetime):
            created_date_for_entry = row['creation_date']
        elif row.get('creation_date') and hasattr(row['creation_date'], 'to_datetime'):
            try:
                created_date_for_entry = row['creation_date'].to_datetime()
            except Exception:
                pass # created_date_for_entry remains None

        if created_date_for_entry:
            display_sample_created_date.set_date(created_date_for_entry)
        else:
            display_sample_created_date.set_date(datetime.now()) # Default to today if no valid date
        
        display_sample_created_date.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        current_row += 1

        tk.Label(form, text="Status:").grid(row=current_row, column=0, sticky="e", pady=5, padx=5)
        status_combobox_edit = ttk.Combobox(form, values=SAMPLE_STATUS_OPTIONS, state="readonly")
        status_combobox_edit.set(row.get('status', SAMPLE_STATUS_OPTIONS[0])) # Default to "pending approval"
        status_combobox_edit.grid(row=current_row, column=1, sticky="ew", pady=5, padx=5)
        current_row += 1

        ttk.Button(form, text="Save Changes", command=lambda: self._submit_edit_sample(
            form, firestore_doc_id, edit_owner_combobox.get(), self.edit_mat_date_entry.get_date(), status_combobox_edit.get()
        )).grid(row=current_row, column=0, columnspan=2, pady=15)
        form.protocol("WM_DELETE_WINDOW", form.destroy)
        logging.info("Edit sample form opened and populated.")

    def _submit_edit_sample(self, form_window, firestore_doc_id, new_owner, new_mat_date_dt, new_status):
        """Submits the edited sample data to Firestore."""
        logging.info(f"Submitting edited sample (DocID: {firestore_doc_id}).")
        if not new_owner or not new_status:
            messagebox.showerror("Error", "Owner and Status fields are required.")
            logging.warning("Owner or Status missing for sample edit.")
            return

        updated_data = {
            "owner": new_owner,
            "status": new_status
        }
        
        # Maturation date is now always updated and required
        if new_mat_date_dt and new_mat_date_dt != datetime(1,1,1).date():
            updated_data["maturation_date"] = datetime(new_mat_date_dt.year, new_mat_date_dt.month, new_mat_date_dt.day)
        else:
            # If maturation date is empty or default, consider it an error as it's now required
            messagebox.showerror("Error", "Maturation Date is required.")
            logging.warning("Maturation Date is empty/default after edit, but is required.")
            return

        logging.debug(f"Updated data for sample {firestore_doc_id}: {updated_data}")
        try:
            db.collection("samples").document(firestore_doc_id).update(updated_data)
            messagebox.showinfo("Success", "Sample updated successfully.")
            logging.info(f"Sample {firestore_doc_id} updated successfully in Firestore.")

            # Refresh based on the last loaded query type
            if self.last_loaded_query_type in ['all_samples', 'my_samples']:
                self.load_samples_paginated(self.last_loaded_query_type, reset=False) # Reload current page
            elif self.current_selected_batch_id:
                self.load_samples_for_current_batch()
            else:
                self.load_samples_paginated(query_type='all_samples', reset=True) # Default to all samples

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
        filter_form.geometry("350x500")
        filter_form.grab_set()
        filter_form.transient(self.root)

        # Radio buttons to choose mode
        radio_frame = ttk.Frame(filter_form, padding=10)
        radio_frame.pack(fill="x")

        ttk.Radiobutton(radio_frame, text="Filter Samples (by Sample/Batch/Product name)",
                        variable=self.filter_mode, value="samples",
                        command=self._toggle_filter_frames).pack(anchor="w", pady=5)
        ttk.Radiobutton(radio_frame, text="Find Batch Details (by Batch ID)",
                        variable=self.filter_mode, value="batch_search",
                        command=self._toggle_filter_frames).pack(anchor="w", pady=5)

        # Frame for Sample Filtering Options
        self.sample_filters_frame = ttk.Frame(filter_form, padding=10)
        # Frame for Batch Search Option
        self.batch_search_frame = ttk.Frame(filter_form, padding=10)

        # Maturation Date Filter widgets within its own frame
        self.maturation_date_filter_frame = ttk.Frame(self.sample_filters_frame)
        ttk.Checkbutton(self.sample_filters_frame, text="Enable Maturation Date Filter",
                        variable=self.filter_maturation_date_var,
                        command=self._toggle_maturation_filter_state).grid(row=0, column=0, sticky="w", pady=5, padx=5, columnspan=2)

        ttk.Label(self.maturation_date_filter_frame, text="From (YYYY-MM-DD):").grid(row=0, column=0, sticky="e", pady=5, padx=5)
        self.filter_start_date_entry = DateEntry(self.maturation_date_filter_frame, width=28, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.filter_start_date_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
        self.filter_start_date_entry.set_date(datetime.now().date()) # Set to today's date

        ttk.Label(self.maturation_date_filter_frame, text="To (YYYY-MM-DD):").grid(row=1, column=0, sticky="e", pady=5, padx=5)
        self.filter_end_date_entry = DateEntry(self.maturation_date_filter_frame, width=28, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.filter_end_date_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
        self.filter_end_date_entry.set_date(datetime.now().date()) # Set to today's date

        # Creation Date Filter widgets within its own frame
        self.creation_date_filter_frame = ttk.Frame(self.sample_filters_frame)
        ttk.Checkbutton(self.sample_filters_frame, text="Enable Creation Date Filter",
                        variable=self.filter_creation_date_var,
                        command=self._toggle_creation_filter_state).grid(row=2, column=0, sticky="w", pady=5, padx=5, columnspan=2) # Row 2 after mat date checkbox

        ttk.Label(self.creation_date_filter_frame, text="From (YYYY-MM-DD):").grid(row=0, column=0, sticky="e", pady=5, padx=5)
        self.filter_creation_start_date_entry = DateEntry(self.creation_date_filter_frame, width=28, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.filter_creation_start_date_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)
        self.filter_creation_start_date_entry.set_date(datetime.now().date()) # Set to today's date

        ttk.Label(self.creation_date_filter_frame, text="To (YYYY-MM-DD):").grid(row=1, column=0, sticky="e", pady=5, padx=5)
        self.filter_creation_end_date_entry = DateEntry(self.creation_date_filter_frame, width=28, background='darkblue', foreground='white', borderwidth=2, date_pattern='yyyy-mm-dd')
        self.filter_creation_end_date_entry.grid(row=1, column=1, sticky="ew", pady=5, padx=5)
        self.filter_creation_end_date_entry.set_date(datetime.now().date()) # Set to today's date

        # Initial state of date filter frames (hidden by default)
        self._toggle_maturation_filter_state()
        self._toggle_creation_filter_state()

        # Other filters always visible, positioned after date filter frames
        # Use .grid() and explicitly manage row/column to place them correctly
        current_filter_row = 4 # Start after date filters (row 0-1 for mat date frame, row 2-3 for creation date frame, leaving gap if un-toggled)

        ttk.Label(self.sample_filters_frame, text="Sample ID (similar/contains):").grid(row=current_filter_row, column=0, sticky="e", pady=5, padx=5)
        self.filter_sample_id_entry = ttk.Entry(self.sample_filters_frame, width=30)
        self.filter_sample_id_entry.grid(row=current_filter_row, column=1, sticky="ew", pady=5, padx=5)
        current_filter_row += 1

        ttk.Label(self.sample_filters_frame, text="Batch ID (similar/contains):").grid(row=current_filter_row, column=0, sticky="e", pady=5, padx=5)
        self.filter_batch_id_entry = ttk.Entry(self.sample_filters_frame, width=30)
        self.filter_batch_id_entry.grid(row=current_filter_row, column=1, sticky="ew", pady=5, padx=5)
        current_filter_row += 1

        ttk.Label(self.sample_filters_frame, text="Product Name (similar/contains):").grid(row=current_filter_row, column=0, sticky="e", pady=5, padx=5)
        self.filter_product_name_entry = ttk.Entry(self.sample_filters_frame, width=30)
        self.filter_product_name_entry.grid(row=current_filter_row, column=1, sticky="ew", pady=5, padx=5)
        current_filter_row += 1

        # Populate batch_search_frame
        ttk.Label(self.batch_search_frame, text="Enter Batch ID:").grid(row=0, column=0, sticky="e", pady=5, padx=5)
        self.find_batch_id_entry = ttk.Entry(self.batch_search_frame, width=30)
        self.find_batch_id_entry.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        # Buttons common to both modes
        button_frame = ttk.Frame(filter_form, padding=10)
        button_frame.pack(fill="x", side="bottom")

        ttk.Button(button_frame, text="Apply", command=lambda: self.apply_filters(filter_form)).pack(side=tk.LEFT, padx=5, pady=10)
        ttk.Button(button_frame, text="Clear Filters", command=lambda: self.clear_filters(filter_form)).pack(side=tk.LEFT, padx=5, pady=10)

        # Initial display
        self._toggle_filter_frames()

        filter_form.protocol("WM_DELETE_WINDOW", filter_form.destroy)
        logging.info("Filter form opened.")

    def _toggle_maturation_filter_state(self):
        """Toggles the visibility and state of maturation date filter entries."""
        logging.debug(f"Toggling maturation filter state: {self.filter_maturation_date_var.get()}")
        if self.filter_maturation_date_var.get():
            self.maturation_date_filter_frame.grid(row=1, column=0, columnspan=2, sticky="ew") # Place it below its checkbox
        else:
            self.maturation_date_filter_frame.grid_forget()
            self.filter_start_date_entry.set_date(datetime.now().date()) # Reset to current date when hidden
            self.filter_end_date_entry.set_date(datetime.now().date())   # Reset to current date when hidden
        logging.debug("Maturation filter state toggled.")

    def _toggle_creation_filter_state(self):
        """Toggles the visibility and state of creation date filter entries."""
        logging.debug(f"Toggling creation filter state: {self.filter_creation_date_var.get()}")
        if self.filter_creation_date_var.get():
            self.creation_date_filter_frame.grid(row=3, column=0, columnspan=2, sticky="ew") # Place it below its checkbox
        else:
            self.creation_date_filter_frame.grid_forget()
            self.filter_creation_start_date_entry.set_date(datetime.now().date()) # Reset to current date when hidden
            self.filter_creation_end_date_entry.set_date(datetime.now().date())   # Reset to current date when hidden
        logging.debug("Creation filter state toggled.")

    def _toggle_filter_frames(self):
        """Toggles visibility of filter frames based on radio button selection."""
        logging.info(f"Toggling filter frames. Current mode: {self.filter_mode.get()}")
        if self.filter_mode.get() == "samples":
            self.batch_search_frame.pack_forget()
            self.sample_filters_frame.pack(fill="both", expand=True)
            # Re-apply states for date filter frames when switching back to samples
            self._toggle_maturation_filter_state()
            self._toggle_creation_filter_state()
            logging.info("Switched to Sample Filter mode.")
        elif self.filter_mode.get() == "batch_search":
            self.sample_filters_frame.pack_forget()
            self.maturation_date_filter_frame.grid_forget() # Ensure date frames are hidden
            self.creation_date_filter_frame.grid_forget()
            self.batch_search_frame.pack(fill="both", expand=True)
            logging.info("Switched to Batch Search mode.")

    def apply_filters(self, form_window):
        """Applies the filters based on the selected mode (sample filter or batch search)."""
        logging.info(f"Apply Filters called. Mode: {self.filter_mode.get()}")
        if self.filter_mode.get() == "samples":
            filters = {}
            
            # Maturation Date Filters
            if self.filter_maturation_date_var.get():
                start_date_obj = self.filter_start_date_entry.get_date()
                end_date_obj = self.filter_end_date_entry.get_date()
                if start_date_obj and start_date_obj != datetime(1,1,1).date():
                    filters['start_date'] = datetime(start_date_obj.year, start_date_obj.month, start_date_obj.day)
                if end_date_obj and end_date_obj != datetime(1,1,1).date():
                    filters['end_date'] = datetime(end_date_obj.year, end_date_obj.month, end_date_obj.day, 23, 59, 59)
                if filters.get('start_date') and filters.get('end_date') and filters['start_date'] > filters['end_date']:
                    messagebox.showerror("Error", "'Maturation Date From' cannot be after 'Maturation Date To'.")
                    logging.warning("Maturation date 'From' is after 'To' date.")
                    return
            
            # Creation Date Filters
            if self.filter_creation_date_var.get():
                creation_start_date_obj = self.filter_creation_start_date_entry.get_date()
                creation_end_date_obj = self.filter_creation_end_date_entry.get_date()
                if creation_start_date_obj and creation_start_date_obj != datetime(1,1,1).date():
                    filters['creation_start_date'] = datetime(creation_start_date_obj.year, creation_start_date_obj.month, creation_start_date_obj.day)
                if creation_end_date_obj and creation_end_date_obj != datetime(1,1,1).date():
                    filters['creation_end_date'] = datetime(creation_end_date_obj.year, creation_end_date_obj.month, creation_end_date_obj.day, 23, 59, 59)
                if filters.get('creation_start_date') and filters.get('creation_end_date') and filters['creation_start_date'] > filters['creation_end_date']:
                    messagebox.showerror("Error", "'Creation Date From' cannot be after 'Creation Date To'.")
                    logging.warning("Creation date 'From' is after 'To' date.")
                    return

            logging.info(f"Maturation Date Filters processed: Start={filters.get('start_date')}, End={filters.get('end_date')}")
            logging.info(f"Creation Date Filters processed: Start={filters.get('creation_start_date')}, End={filters.get('creation_end_date')}")

            sample_id = self.filter_sample_id_entry.get().strip()
            batch_id = self.filter_batch_id_entry.get().strip()
            product_name = self.filter_product_name_entry.get().strip()

            if sample_id:
                filters['sample_id'] = sample_id
            if batch_id:
                filters['batch_id'] = batch_id
            if product_name:
                filters['product_name'] = product_name
            
            logging.info(f"Applying sample filters: {filters}")
            # This will load all samples first, then apply local filtering
            self.load_all_user_samples_from_db_with_filters(filters) # A new method to handle combined DB and local filtering
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
                    logging.info("Batch not found.")
                    messagebox.showinfo("Batch Not Found", f"Batch with ID '{batch_id_to_find}' does not exist.")
            except Exception as e:
                logging.error(f"Error retrieving batch details for '{batch_id_to_find}': {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to retrieve batch details: {e}")

    def load_all_user_samples_from_db_with_filters(self, filters=None):
        """Loads all sample data from Firestore and populates the local DataFrame and Treeview,
        applying filters directly."""
        logging.info(f"Loading all user samples from DB with filters: {filters}")
        # Reset sample pagination state when loading filtered samples
        self.current_page_index = 0
        self.all_samples_page_cursors = []
        self.my_samples_page_cursors = []
        self.last_loaded_query_type = 'filtered_samples' # Set query type for filter results


        self.tree.delete(*self.tree.get_children())
        samples_list = []
        try:
            samples_ref = db.collection("samples")
            query = samples_ref

            firestore_query_applied = False # Flag to track if a date range query was applied on Firestore

            if filters:
                # Prioritize maturation_date for Firestore range query if both date filters enabled
                if 'start_date' in filters and 'end_date' in filters:
                    query = query.where("maturation_date", ">=", filters['start_date'])
                    query = query.where("maturation_date", "<=", filters['end_date'])
                    firestore_query_applied = True
                    logging.info("Applied Firestore maturation_date range filter.")
                # If maturation_date not used, try creation_date for Firestore range query
                elif 'creation_start_date' in filters and 'creation_end_date' in filters:
                    query = query.where("creation_date", ">=", filters['creation_start_date'])
                    query = query.where("creation_date", "<=", filters['creation_end_date'])
                    firestore_query_applied = True
                    logging.info("Applied Firestore creation_date range filter.")
                
            samples = query.stream()

            for sample in samples:
                data = sample.to_dict()
                data['firestore_doc_id'] = sample.id
                # Convert Firestore Timestamp to datetime object if necessary
                if data.get('maturation_date') and hasattr(data['maturation_date'], 'to_datetime'):
                    data['maturation_date'] = data['maturation_date'].to_datetime()
                # Convert Firestore Timestamp for creation_date if exists
                if data.get('creation_date') and hasattr(data['creation_date'], 'to_datetime'):
                    data['creation_date'] = data['creation_date'].to_datetime()

                samples_list.append(data)
            logging.info(f"Initial fetch for filtered samples returned {len(samples_list)} results.")

            df = pd.DataFrame(samples_list)

            # Apply local filters for 'similar or close' matching and secondary date filters
            if filters:
                if filters.get('sample_id'):
                    if 'sample_id' in df.columns:
                         df = df[df['sample_id'].astype(str).str.contains(filters['sample_id'], case=False, na=False)]
                    elif 'DisplaySampleID' in df.columns:
                        df = df[df['DisplaySampleID'].astype(str).str.contains(filters['sample_id'], case=False, na=False)]
                    logging.debug(f"Filtered by sample_id, {len(df)} remaining.")

                if filters.get('batch_id'):
                    if 'batch_id' in df.columns:
                        df = df[df['batch_id'].astype(str).str.contains(filters['batch_id'], case=False, na=False)]
                    elif 'BatchID' in df.columns:
                        df = df[df['BatchID'].astype(str).str.contains(filters['BatchID'], case=False, na=False)]
                    logging.debug(f"Filtered by batch_id, {len(df)} remaining.")

                if filters.get('product_name'):
                    product_name_filter_val = filters['product_name'].lower()
                    # Need to fetch product names for associated batches
                    valid_batch_ids = df['batch_id'].dropna().unique() if 'batch_id' in df.columns else []
                    batch_product_names = {}
                    for b_id in valid_batch_ids:
                        if b_id and b_id != 'N/A' and pd.notna(b_id):
                            batch_doc = db.collection("batches").document(b_id).get()
                            if batch_doc.exists:
                                batch_product_names[b_id] = batch_doc.to_dict().get('product_name', '').lower()
                    df = df[df['batch_id'].apply(lambda x: product_name_filter_val in batch_product_names.get(x, '') if pd.notna(x) else False)]
                    logging.debug(f"Filtered by product_name, {len(df)} remaining.")

                # Apply secondary date filters locally if a Firestore range query was already applied for another date
                # This ensures that if maturation date was used for the Firestore query, creation date can still be filtered locally.
                # And vice-versa.
                if firestore_query_applied: # If a date filter was pushed to Firestore
                    if 'start_date' in filters and 'end_date' in filters and not ('maturation_date' in [f.field_path for f in query._field_filters]): # Check if mat date was NOT the Firestore filter
                        df = df[df['MaturationDate'].apply(lambda x: x and filters['start_date'] <= x)]
                        df = df[df['MaturationDate'].apply(lambda x: x and x <= filters['end_date'])]
                        logging.debug(f"Applied local maturation_date filter, {len(df)} remaining.")
                    
                    if 'creation_start_date' in filters and 'creation_end_date' in filters and not ('creation_date' in [f.field_path for f in query._field_filters]): # Check if creation date was NOT the Firestore filter
                        df = df[df['CreationDate'].apply(lambda x: x and filters['creation_start_date'] <= x)]
                        df = df[df['CreationDate'].apply(lambda x: x and x <= filters['creation_end_date'])]
                        logging.debug(f"Applied local creation_date filter, {len(df)} remaining.")
                
                # If no Firestore query was applied for date, and date filters are enabled, apply locally
                if not firestore_query_applied:
                    if 'start_date' in filters and 'end_date' in filters:
                        df = df[df['MaturationDate'].apply(lambda x: x and filters['start_date'] <= x)]
                        df = df[df['MaturationDate'].apply(lambda x: x and x <= filters['end_date'])]
                        logging.debug(f"Applied local maturation_date filter (no Firestore date filter), {len(df)} remaining.")
                    if 'creation_start_date' in filters and 'creation_end_date' in filters:
                        df = df[df['CreationDate'].apply(lambda x: x and filters['creation_start_date'] <= x)]
                        df = df[df['CreationDate'].apply(lambda x: x and x <= filters['creation_end_date'])]
                        logging.debug(f"Applied local creation_date filter (no Firestore date filter), {len(df)} remaining.")


            self.load_samples_to_treeview(df.to_dict('records')) # Use the refactored function
            
            if not df.empty:
                self.status_label.config(text=f"Loaded {len(self.app.data)} samples from database matching filters.")
                logging.info(f"Finished loading filtered samples. Displaying {len(self.app.data)} samples.")
            else:
                self.status_label.config(text="No samples found in the database matching filters.")
                logging.info("No samples found matching filters.")
            
            self.current_selected_batch_id = None
            self.add_single_sample_button.config(state=tk.DISABLED)

            # Disable pagination controls for filtered samples (as it's a specific search result)
            self.prev_sample_page_btn.config(state=tk.DISABLED)
            self.next_sample_page_btn.config(state=tk.DISABLED)
            self.page_info_label.config(text="Page 0 of 0")


        except Exception as e:
            logging.error(f"Failed to load samples from database with filters: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to load samples from database: {e}")
            self.status_label.config(text="Failed to load samples from database.")


    def _display_batch_details_window(self, batch_data):
        """Displays batch details in a new window with copyable text."""
        logging.info(f"Displaying batch details for batch: {batch_data.get('batch_id', 'N/A')}")
        details_window = tk.Toplevel(self.root)
        details_window.title(f"Batch Details: {batch_data.get('batch_id', 'N/A')}")
        details_window.geometry("500x300")
        details_window.grab_set()
        details_window.transient(self.root)

        text_frame = ttk.Frame(details_window, padding=10)
        text_frame.pack(expand=True, fill="both")

        text_widget = tk.Text(text_frame, wrap='word', font=('Consolas', 10),
                              bg=details_window.cget('bg'), bd=0, highlightthickness=0)
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
        text_widget.config(state='disabled')

        ttk.Button(details_window, text="Close", command=details_window.destroy).pack(pady=10)
        details_window.protocol("WM_DELETE_WINDOW", details_window.destroy)
        logging.info(f"Batch details window displayed for {batch_data.get('batch_id', 'N/A')}.")

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

            # Now clear the actual entry widgets
            self.filter_sample_id_entry.delete(0, tk.END)
            self.filter_batch_id_entry.delete(0, tk.END)
            self.filter_product_name_entry.delete(0, tk.END)
            logging.info("Sample filters cleared.")
        elif self.filter_mode.get() == "batch_search" and self.find_batch_id_entry:
            self.find_batch_id_entry.delete(0, tk.END)
            logging.info("Batch search filter cleared.")

        self.load_samples_paginated(query_type='all_samples', reset=True) # Reload all samples after clearing filters
        form_window.destroy()
        logging.info("Filters cleared and all samples reloaded.")
