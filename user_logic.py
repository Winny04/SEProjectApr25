# user_logic.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
from datetime import datetime, timedelta
import barcode
from barcode.writer import ImageWriter
import os
from firebase_setup import db
from constants import NOTIFICATION_DAYS_BEFORE, COLUMNS
from tkcalendar import DateEntry 
import firebase_admin 

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
        self.new_batch_test_date_entry = None 
        self.entry_sample_display_id = None 
        self.entry_owner = None
        self.entry_maturation_date_entry = None 
        self.status_combobox = None

    def user_dashboard(self):
        """Displays the user dashboard with sample management features."""
        self.app.clear_root()
        self.root.geometry("1000x600")
        self.excel_imported = False
        self.current_selected_batch_id = None 

        # === Menu Bar ===
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Import Excel (Local)", command=self.import_excel)
        filemenu.add_command(label="Export Excel (Local)", command=self.export_excel)
        filemenu.add_separator()
        filemenu.add_command(label="Logout", command=self.app.logout) 
        menubar.add_cascade(label="File", menu=filemenu)
        self.root.config(menu=menubar)

        # === Toolbar Frame for Buttons ===
        toolbar = tk.Frame(self.root, pady=10)
        toolbar.pack(fill="x", padx=10)

        ttk.Button(toolbar, text="Load All My Samples", command=self.load_all_user_samples_from_db).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(toolbar, text="Generate Barcode", command=self.generate_barcode).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Check Notifications", command=self.check_notifications).pack(side=tk.LEFT, padx=5)
        
        self.add_sample_main_button = ttk.Button(toolbar, text="Add Sample to Batch", command=self.open_batch_selection_screen)
        self.add_sample_main_button.pack(side=tk.LEFT, padx=5)

        self.add_single_sample_button = ttk.Button(toolbar, text="Add Single Sample to Current Batch", command=self.open_single_sample_form, state=tk.DISABLED)
        self.add_single_sample_button.pack(side=tk.LEFT, padx=5)


        ttk.Button(toolbar, text="Edit Sample", command=self.edit_sample).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Delete Sample", command=self.delete_sample).pack(side=tk.LEFT, padx=5)

        # === Treeview for Data Display ===
        self.tree = ttk.Treeview(self.root, columns=("DocID", "DisplaySampleID", "Owner", "MaturationDate", "Status", "BatchID"), show='headings')
        self.tree.heading("DocID", text="Doc ID") 
        self.tree.heading("DisplaySampleID", text="Sample ID") 
        self.tree.heading("Owner", text="Sample Owner")
        self.tree.heading("MaturationDate", text="Maturation Date")
        self.tree.heading("Status", text="Status")
        self.tree.heading("BatchID", text="Batch ID")
        
        self.tree.column("DocID", width=0, stretch=tk.NO) 
        self.tree.column("DisplaySampleID", width=100, anchor="center")
        self.tree.column("Owner", width=100, anchor="center")
        self.tree.column("MaturationDate", width=120, anchor="center")
        self.tree.column("Status", width=80, anchor="center")
        self.tree.column("BatchID", width=120, anchor="center")

        self.tree.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # === Status Bar ===
        self.status_label = tk.Label(self.root, text="Load samples from DB or import Excel.", anchor='w', bd=1, relief=tk.SUNKEN)
        self.status_label.pack(fill=tk.X, padx=10, pady=5)
        
        self.load_all_user_samples_from_db()

    def load_all_user_samples_from_db(self):
        """Loads all sample data submitted by the current user from Firestore and populates the local DataFrame and Treeview."""
        self.tree.delete(*self.tree.get_children())
        samples_list = []
        try:
            samples_ref = db.collection("samples")
            samples = samples_ref.where("submitted_by_employee_id", "==", self.app.current_user['employee_id']).stream()
            
            for sample in samples:
                data = sample.to_dict()
                data['firestore_doc_id'] = sample.id 
                if isinstance(data.get('maturation_date'), datetime):
                    data['maturation_date'] = data['maturation_date']
                else: 
                    data['maturation_date'] = data['maturation_date'].to_datetime()
                samples_list.append(data)
            
            if samples_list:
                self.app.data = pd.DataFrame(samples_list)
                for col_name_db, col_name_display in [("firestore_doc_id", "DocID"), 
                                                       ("sample_id", "DisplaySampleID"), 
                                                       ("owner", "Owner"), 
                                                       ("maturation_date", "MaturationDate"), 
                                                       ("status", "Status"), 
                                                       ("batch_id", "BatchID")]:
                    if col_name_db not in self.app.data.columns:
                        self.app.data[col_name_db] = None 
                    self.app.data.rename(columns={col_name_db: col_name_display}, inplace=True)
                
                self.refresh_tree()
                self.status_label.config(text=f"Loaded {len(self.app.data)} samples from database (All User Samples).")
            else:
                self.app.data = pd.DataFrame(columns=["DocID", "DisplaySampleID", "Owner", "MaturationDate", "Status", "BatchID"])
                self.refresh_tree()
                self.status_label.config(text="No samples found in the database for this user.")
            
            self.current_selected_batch_id = None
            self.add_single_sample_button.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load samples from database: {e}")
            self.status_label.config(text="Failed to load samples from database.")

    def load_samples_for_current_batch(self):
        """Loads samples only for the current_selected_batch_id and updates the Treeview."""
        if not self.current_selected_batch_id:
            self.status_label.config(text="No batch selected to display samples.")
            return

        self.tree.delete(*self.tree.get_children())
        samples_list = []
        try:
            samples_ref = db.collection("samples")
            samples = samples_ref.where("batch_id", "==", self.current_selected_batch_id).stream()
            
            for sample in samples:
                data = sample.to_dict()
                data['firestore_doc_id'] = sample.id 
                if isinstance(data.get('maturation_date'), datetime):
                    data['maturation_date'] = data['maturation_date']
                else:
                    data['maturation_date'] = data['maturation_date'].to_datetime()
                samples_list.append(data)
            
            if samples_list:
                self.app.data = pd.DataFrame(samples_list)
                for col_name_db, col_name_display in [("firestore_doc_id", "DocID"), 
                                                       ("sample_id", "DisplaySampleID"), 
                                                       ("owner", "Owner"), 
                                                       ("maturation_date", "MaturationDate"), 
                                                       ("status", "Status"), 
                                                       ("batch_id", "BatchID")]:
                    if col_name_db not in self.app.data.columns:
                        self.app.data[col_name_db] = None 
                    self.app.data.rename(columns={col_name_db: col_name_display}, inplace=True)

                self.refresh_tree()
                self.status_label.config(text=f"Loaded {len(self.app.data)} samples for Batch: {self.current_selected_batch_id}")
            else:
                self.app.data = pd.DataFrame(columns=["DocID", "DisplaySampleID", "Owner", "MaturationDate", "Status", "BatchID"])
                self.refresh_tree()
                self.status_label.config(text=f"No samples found for Batch: {self.current_selected_batch_id}")
            
            self.add_single_sample_button.config(state=tk.NORMAL)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load samples for batch: {e}")
            self.status_label.config(text="Failed to load samples for batch.")


    def import_excel(self):
        """Imports data from an Excel file into the application's local DataFrame.
        This data is only for temporary local use and is not automatically linked to a batch in DB."""
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
                self.app.data['DocID'] = 'N/A (Local)' 

                self.app.file_path = filename
                self.refresh_tree()
                self.status_label.config(text=f"Loaded data from {os.path.basename(filename)} (Local)")
                self.excel_imported = True
                
                self.current_selected_batch_id = None
                self.add_single_sample_button.config(state=tk.DISABLED)

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load Excel file:\n{e}")

    def export_excel(self):
        """Exports current data in the local DataFrame to an Excel file."""
        if self.app.data.empty:
            messagebox.showwarning("Warning", "No data to export.")
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
                
                df_to_export.to_excel(filename, index=False)
                self.status_label.config(text=f"Data exported to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export Excel file:\n{e}")

    def refresh_tree(self):
        """Refreshes the Treeview widget with the current DataFrame data."""
        self.tree.delete(*self.tree.get_children())
        for _, row in self.app.data.iterrows():
            mat_date = row['MaturationDate']
            if isinstance(mat_date, pd.Timestamp) or isinstance(mat_date, datetime):
                mat_date_str = mat_date.strftime("%Y-%m-%d")
            else:
                mat_date_str = str(mat_date) 
            self.tree.insert("", tk.END, 
                             values=(row['DocID'], row['DisplaySampleID'], row['Owner'], mat_date_str, row['Status'], row.get('BatchID', 'N/A')))

    def generate_barcode(self):
        """Generates a barcode for the selected sample ID (user-facing ID)."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample from the list.")
            return
        item = self.tree.item(selected[0])
        sample_id_for_barcode = str(item['values'][1]) 

        try:
            EAN = barcode.get_barcode_class('code128') 
            ean = EAN(sample_id_for_barcode, writer=ImageWriter())
            save_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                     filetypes=[("PNG files", "*.png")],
                                                     initialfile=f"{sample_id_for_barcode}_barcode.png")
            if save_path:
                ean.save(save_path)
                messagebox.showinfo("Success", f"Barcode saved at {save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Barcode generation failed:\n{e}")

    def check_notifications(self):
        """Checks for samples maturing within the defined notification period."""
        if self.app.data.empty:
            messagebox.showwarning("Warning", "No data loaded.")
            return

        today = datetime.now()
        notifications = []

        for _, row in self.app.data.iterrows():
            mat_date = row['MaturationDate']
            if pd.isna(mat_date): 
                continue

            if isinstance(mat_date, pd.Timestamp):
                mat_date_dt = mat_date.to_pydatetime()
            elif isinstance(mat_date, datetime):
                mat_date_dt = mat_date
            else:
                try: 
                    mat_date_dt = datetime.strptime(str(mat_date), "%Y-%m-%d")
                except ValueError:
                    continue 

            delta = mat_date_dt - today
            if 0 <= delta.days <= NOTIFICATION_DAYS_BEFORE:
                notifications.append(f"Sample {row['DisplaySampleID']} owned by {row['Owner']} matures on {mat_date_dt.strftime('%Y-%m-%d')}.") 

        if notifications:
            messagebox.showinfo("Notifications", "\n".join(notifications))
        else:
            messagebox.showinfo("Notifications", f"No samples maturing within {NOTIFICATION_DAYS_BEFORE} days.")


    def open_batch_selection_screen(self):
        """Opens a Toplevel window for selecting an existing batch or creating a new one."""
        batch_selection_form = tk.Toplevel(self.root)
        batch_selection_form.title("Select or Create Batch")
        batch_selection_form.geometry("500x350")
        batch_selection_form.grab_set()
        batch_selection_form.transient(self.root)

        frame = ttk.Frame(batch_selection_form, padding=10)
        frame.pack(expand=True, fill="both")

        self.batch_choice = tk.StringVar(value="existing")
        # Radio buttons are created first, then the command is assigned
        radio_existing = ttk.Radiobutton(frame, text="Select Existing Batch", variable=self.batch_choice, value="existing")
        radio_new = ttk.Radiobutton(frame, text="Create New Batch", variable=self.batch_choice, value="new")

        radio_existing.grid(row=0, column=0, columnspan=2, sticky="w", pady=5)
        radio_new.grid(row=1, column=0, columnspan=2, sticky="w", pady=5)

        ttk.Label(frame, text="Existing Batch ID:").grid(row=2, column=0, sticky="e", pady=5, padx=5)
        self.existing_batch_combobox = ttk.Combobox(frame, state="readonly", width=30)
        self.existing_batch_combobox.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
        self._load_existing_batches_into_combobox() 

        ttk.Label(frame, text="New Product Name:").grid(row=3, column=0, sticky="e", pady=5, padx=5)
        # Set initial state to disabled as "existing" is default selected
        self.new_batch_product_name = ttk.Entry(frame, width=30, state="disabled")
        self.new_batch_product_name.grid(row=3, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(frame, text="New Description:").grid(row=4, column=0, sticky="e", pady=5, padx=5)
        # Set initial state to disabled
        self.new_batch_description = ttk.Entry(frame, width=30, state="disabled")
        self.new_batch_description.grid(row=4, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(frame, text="New Batch Test Date (YYYY-MM-DD):").grid(row=5, column=0, sticky="e", pady=5, padx=5)
        # Set initial state to disabled
        self.new_batch_test_date_entry = DateEntry(frame, width=28, background='darkblue', foreground='white', borderwidth=2,
                                                    date_pattern='yyyy-mm-dd', state="disabled")
        self.new_batch_test_date_entry.grid(row=5, column=1, sticky="ew", pady=5, padx=5)
        
        # Now, assign the command to the radio buttons after all widgets are created
        radio_existing.config(command=lambda: self._toggle_batch_fields_on_selection(True))
        radio_new.config(command=lambda: self._toggle_batch_fields_on_selection(False))

        # Explicitly call _toggle_batch_fields_on_selection to set initial states correctly
        self._toggle_batch_fields_on_selection(True)

        ttk.Button(frame, text="Confirm Batch Selection", command=lambda: self._handle_batch_selection_confirmation(batch_selection_form)).grid(row=6, column=0, columnspan=2, pady=20)
        batch_selection_form.protocol("WM_DELETE_WINDOW", batch_selection_form.destroy)

    def _toggle_batch_fields_on_selection(self, is_existing_batch_selected):
        """Internal helper to toggle the visibility/state of new/existing batch fields."""
        try:
            if self.existing_batch_combobox:
                self.existing_batch_combobox.config(state="readonly" if is_existing_batch_selected else "disabled")
                if not is_existing_batch_selected:
                    self.existing_batch_combobox.set('') 
        except Exception as e:
            print(f"Warning: Error configuring existing_batch_combobox: {e}") # Log error, but don't crash

        try:
            if self.new_batch_product_name:
                self.new_batch_product_name.config(state="normal" if not is_existing_batch_selected else "disabled")
                if is_existing_batch_selected: 
                    # If switching to 'existing', clear the new batch field values
                    self.new_batch_product_name.config(state="normal") # Temporarily enable to clear
                    self.new_batch_product_name.delete(0, tk.END)
                    self.new_batch_product_name.config(state="disabled") # Re-disable
        except Exception as e:
            print(f"Warning: Error configuring new_batch_product_name: {e}") # Log error, but don't crash
        
        try:
            if self.new_batch_description:
                self.new_batch_description.config(state="normal" if not is_existing_batch_selected else "disabled")
                if is_existing_batch_selected:
                    self.new_batch_description.config(state="normal")
                    self.new_batch_description.delete(0, tk.END)
                    self.new_batch_description.config(state="disabled")
        except Exception as e:
            print(f"Warning: Error configuring new_batch_description: {e}") # Log error, but don't crash
        
        try:
            if self.new_batch_test_date_entry:
                self.new_batch_test_date_entry.config(state="normal" if not is_existing_batch_selected else "disabled")
                if is_existing_batch_selected:
                    self.new_batch_test_date_entry.config(state="normal")
                    self.new_batch_test_date_entry.set_date(datetime.now()) 
                    self.new_batch_test_date_entry.config(state="disabled")
        except Exception as e:
            print(f"Warning: Error configuring new_batch_test_date_entry: {e}") # Log error, but don't crash

    def _load_existing_batches_into_combobox(self):
        """Loads batch IDs from Firestore into the combobox."""
        batches_ref = db.collection("batches")
        try:
            batches = batches_ref.where("user_employee_id", "==", self.app.current_user['employee_id']).stream()
            batch_ids = [batch.id for batch in batches]
            self.existing_batch_combobox['values'] = batch_ids
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load existing batches: {e}")
            self.existing_batch_combobox['values'] = []

    def _handle_batch_selection_confirmation(self, form_window):
        """Handles the confirmation of batch selection or creation."""
        selected_batch_id = None
        
        if self.batch_choice.get() == "new":
            product_name = self.new_batch_product_name.get().strip()
            description = self.new_batch_description.get().strip()
            test_date_dt = self.new_batch_test_date_entry.get_date() 

            if not product_name:
                messagebox.showerror("Error", "New Batch Product Name is required.")
                return
            if not test_date_dt: 
                messagebox.showerror("Error", "New Batch Test Date is required.")
                return
            
            selected_batch_id = f"batch_{self.app.current_user['employee_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            if db.collection("batches").document(selected_batch_id).get().exists:
                messagebox.showerror("Error", "Generated Batch ID already exists. Please try again.")
                return

            new_batch_data = {
                "batch_id": selected_batch_id,
                "product_name": product_name,
                "description": description,
                "test_date": datetime(test_date_dt.year, test_date_dt.month, test_date_dt.day), 
                "user_employee_id": self.app.current_user['employee_id'],
                "user_username": self.app.current_user['username'],
                "user_email": self.app.current_user['email'],
                "submission_date": datetime.now(), 
                "status": "pending", 
                "number_of_samples": 0 
            }
            try:
                db.collection("batches").document(selected_batch_id).set(new_batch_data)
                messagebox.showinfo("Success", f"New batch '{selected_batch_id}' created successfully.")
                self.current_selected_batch_id = selected_batch_id
                self.load_samples_for_current_batch() 
                if hasattr(self.app, 'admin_logic'): 
                    self.app.admin_logic.load_batches() 
                form_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create new batch: {e}")
                return

        else: 
            selected_batch_id = self.existing_batch_combobox.get().strip()
            if not selected_batch_id:
                messagebox.showerror("Error", "Please select an existing batch.")
                return
            
            existing_batch_doc = db.collection("batches").document(selected_batch_id).get()
            if not existing_batch_doc.exists:
                messagebox.showerror("Error", "Selected batch does not exist in the database.")
                return
            
            self.current_selected_batch_id = selected_batch_id
            self.load_samples_for_current_batch() 
            messagebox.showinfo("Batch Selected", f"Samples for batch '{selected_batch_id}' are now displayed.")
            form_window.destroy()

    def open_single_sample_form(self):
        """Opens a form to add a single new sample to the currently selected batch."""
        if not self.current_selected_batch_id:
            messagebox.showwarning("Warning", "Please select or create a batch first using 'Add Sample to Batch' button.")
            return

        form = tk.Toplevel(self.root)
        form.title(f"Add Sample to Batch: {self.current_selected_batch_id}")
        form.geometry("400x350") 
        form.grab_set()
        form.transient(self.root)

        frame = ttk.Frame(form, padding=10)
        frame.pack(expand=True, fill="both")

        ttk.Label(frame, text="Batch ID:").grid(row=0, column=0, sticky="e", pady=5, padx=5)
        ttk.Label(frame, text=self.current_selected_batch_id, font=("Helvetica", 10, "bold")).grid(row=0, column=1, sticky="w", pady=5, padx=5)

        ttk.Label(frame, text="Sample ID (e.g., SMPL-001):").grid(row=1, column=0, sticky="e", pady=5, padx=5)
        self.entry_sample_display_id = ttk.Entry(frame, width=30) 
        self.entry_sample_display_id.grid(row=1, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(frame, text="Sample Owner:").grid(row=2, column=0, sticky="e", pady=5, padx=5)
        self.entry_owner = ttk.Entry(frame, width=30)
        self.entry_owner.grid(row=2, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(frame, text="Maturation Date (YYYY-MM-DD):").grid(row=3, column=0, sticky="e", pady=5, padx=5)
        self.entry_maturation_date_entry = DateEntry(frame, width=28, background='darkblue', foreground='white', borderwidth=2,
                                                     date_pattern='yyyy-mm-dd')
        self.entry_maturation_date_entry.grid(row=3, column=1, sticky="ew", pady=5, padx=5)
        
        ttk.Label(frame, text="Status:").grid(row=4, column=0, sticky="e", pady=5, padx=5)
        self.status_combobox = ttk.Combobox(frame, values=["pending", "approved", "rejected"], state="readonly", width=27)
        self.status_combobox.grid(row=4, column=1, sticky="ew", pady=5, padx=5)
        self.status_combobox.current(0) 

        ttk.Button(frame, text="Add Sample to Batch", command=lambda: self._submit_single_sample(form)).grid(row=5, column=0, columnspan=2, pady=15) 
        form.protocol("WM_DELETE_WINDOW", form.destroy)

    def _submit_single_sample(self, form_window):
        """Handles submission of a single new sample to the current batch."""
        sample_display_id = self.entry_sample_display_id.get().strip() 
        owner = self.entry_owner.get().strip()
        mat_date_dt = self.entry_maturation_date_entry.get_date() 
        sample_status = self.status_combobox.get().strip()

        if not sample_display_id or not owner or not mat_date_dt:
            messagebox.showerror("Error", "All sample fields are required.")
            return

        try:
            existing_samples_with_display_id = db.collection("samples").where("sample_id", "==", sample_display_id).limit(1).get()
            if existing_samples_with_display_id: 
                messagebox.showerror("Error", "Sample ID already exists in the database. Please use a unique ID.")
                return
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to check existing sample ID: {e}")
            return

        sample_data = {
            "sample_id": sample_display_id, 
            "owner": owner,
            "maturation_date": datetime(mat_date_dt.year, mat_date_dt.month, mat_date_dt.day), 
            "status": sample_status,
            "batch_id": self.current_selected_batch_id, 
            "submitted_by_employee_id": self.app.current_user['employee_id']
        }

        try:
            batch_write = db.batch()
            
            sample_doc_ref = db.collection("samples").document() 
            batch_write.set(sample_doc_ref, sample_data)

            batch_doc_ref = db.collection("batches").document(self.current_selected_batch_id)
            batch_write.update(batch_doc_ref, {"number_of_samples": firebase_admin.firestore.Increment(1)})

            batch_write.commit()

            messagebox.showinfo("Success", f"Sample '{sample_display_id}' added successfully to Batch '{self.current_selected_batch_id}'.")
            
            self.load_samples_for_current_batch() 
            
            if hasattr(self.app, 'admin_logic'): 
                self.app.admin_logic.load_batches() 

            form_window.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add sample: {e}")

    def delete_sample(self):
        """Deletes a selected sample from Firestore."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample to delete.")
            return

        item = self.tree.item(selected[0])
        firestore_doc_id = item['values'][0] 
        display_sample_id = item['values'][1] 
        batch_id = item['values'][4] 

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete sample '{display_sample_id}' from Batch '{batch_id}'?")
        if not confirm:
            return

        try:
            batch_write = db.batch()

            sample_doc_ref = db.collection("samples").document(firestore_doc_id)
            batch_write.delete(sample_doc_ref)

            batch_doc_ref = db.collection("batches").document(batch_id)
            batch_write.update(batch_doc_ref, {"number_of_samples": firebase_admin.firestore.Increment(-1)})
            
            batch_write.commit()

            messagebox.showinfo("Success", f"Sample '{display_sample_id}' deleted successfully.")
            if self.current_selected_batch_id:
                self.load_samples_for_current_batch() 
            else:
                self.load_all_user_samples_from_db()

            if hasattr(self.app, 'admin_logic'): 
                self.app.admin_logic.load_batches() 
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete sample: {e}")


    def edit_sample(self):
        """Opens a form to edit details of a selected sample from Firestore."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample to edit.")
            return

        item = self.tree.item(selected[0])
        firestore_doc_id = item['values'][0] 
        display_sample_id = item['values'][1] 

        try:
            sample_doc = db.collection("samples").document(firestore_doc_id).get()
            if not sample_doc.exists:
                messagebox.showerror("Error", "Selected sample not found in database.")
                if self.current_selected_batch_id:
                    self.load_samples_for_current_batch()
                else:
                    self.load_all_user_samples_from_db()
                return
            row = sample_doc.to_dict()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to retrieve sample data: {e}")
            return

        form = tk.Toplevel(self.root)
        form.title(f"Edit Sample {display_sample_id}") 
        form.geometry("300x250") 
        form.grab_set()
        form.transient(self.root)

        tk.Label(form, text="Sample ID:").pack(pady=5)
        entry_sample_display_id = ttk.Entry(form) 
        entry_sample_display_id.insert(0, row.get('sample_id', '')) 
        entry_sample_display_id.config(state='disabled') 
        entry_sample_display_id.pack()

        tk.Label(form, text="Sample Owner:").pack(pady=5)
        entry_owner = ttk.Entry(form)
        entry_owner.insert(0, row.get('owner', ''))
        entry_owner.pack()

        tk.Label(form, text="Maturation Date (YYYY-MM-DD):").pack(pady=5)
        edit_mat_date_entry = DateEntry(form, width=28, background='darkblue', foreground='white', borderwidth=2,
                                         date_pattern='yyyy-mm-dd')
        mat_date_val = row.get('maturation_date')
        if isinstance(mat_date_val, datetime):
            edit_mat_date_entry.set_date(mat_date_val)
        elif isinstance(mat_date_val, pd.Timestamp): 
            edit_mat_date_entry.set_date(mat_date_val.to_pydatetime())
        edit_mat_date_entry.pack()

        tk.Label(form, text="Status:").pack(pady=5)
        status_combobox = ttk.Combobox(form, values=["pending", "approved", "rejected"], state="readonly", width=27)
        status_combobox.pack()
        status_combobox.set(row.get('status', 'pending')) 

        def submit_edit():
            owner = entry_owner.get().strip()
            mat_date = edit_mat_date_entry.get_date()
            status = status_combobox.get().strip()

            if not owner or not mat_date:
                messagebox.showerror("Error", "All fields are required.")
                return

            confirm = messagebox.askyesno("Confirm Edit", f"Are you sure you want to save changes to sample '{display_sample_id}'?")
            if not confirm:
                return
            
            updated_data = {
                'owner': owner,
                'maturation_date': datetime(mat_date.year, mat_date.month, mat_date.day), 
                'status': status
            }

            try:
                db.collection("samples").document(firestore_doc_id).update(updated_data)
                messagebox.showinfo("Success", f"Sample '{display_sample_id}' updated successfully.")
                if self.current_selected_batch_id:
                    self.load_samples_for_current_batch()
                else:
                    self.load_all_user_samples_from_db()
                form.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update sample: {e}")

        ttk.Button(form, text="Save Changes", command=submit_edit).pack(pady=10)
        form.protocol("WM_DELETE_WINDOW", form.destroy)
