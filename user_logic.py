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

class UserLogic:
    def __init__(self, root, app_instance):
        self.root = root
        self.app = app_instance
        self.tree = None # Treeview widget
        self.status_label = None # Status bar label
        self.excel_imported = False # Flag to track if data was imported from local Excel

        # Elements for the add_sample form
        self.batch_choice = None
        self.existing_batch_combobox = None
        self.new_batch_product_name = None
        self.new_batch_description = None
        self.new_batch_test_date = None
        self.entry_sample_id = None
        self.entry_owner = None
        self.entry_date = None
        self.status_combobox = None

    def user_dashboard(self):
        """Displays the user dashboard with sample management features."""
        self.app.clear_root()
        self.root.geometry("1000x600")
        self.excel_imported = False

        # === Menu Bar ===
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Import Excel (Local)", command=self.import_excel)
        filemenu.add_command(label="Export Excel (Local)", command=self.export_excel)
        filemenu.add_separator()
        filemenu.add_command(label="Logout", command=self.app.logout) # Use app's logout
        menubar.add_cascade(label="File", menu=filemenu)
        self.root.config(menu=menubar)

        # === Toolbar Frame for Buttons ===
        toolbar = tk.Frame(self.root, pady=10)
        toolbar.pack(fill="x", padx=10)

        ttk.Button(toolbar, text="Load Samples from DB", command=self.load_samples_from_db).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Generate Barcode", command=self.generate_barcode).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Check Notifications", command=self.check_notifications).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Add Sample", command=self.add_sample).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Edit Sample", command=self.edit_sample).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Delete Sample", command=self.delete_sample).pack(side=tk.LEFT, padx=5)

        # === Treeview for Data Display ===
        self.tree = ttk.Treeview(self.root, columns=("SampleID", "Owner", "MaturationDate", "Status", "BatchID"), show='headings')
        self.tree.heading("SampleID", text="Sample ID")
        self.tree.heading("Owner", text="Sample Owner")
        self.tree.heading("MaturationDate", text="Maturation Date")
        self.tree.heading("Status", text="Status")
        self.tree.heading("BatchID", text="Batch ID")
        
        self.tree.column("SampleID", width=100, anchor="center")
        self.tree.column("Owner", width=100, anchor="center")
        self.tree.column("MaturationDate", width=120, anchor="center")
        self.tree.column("Status", width=80, anchor="center")
        self.tree.column("BatchID", width=120, anchor="center")

        self.tree.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # === Status Bar ===
        self.status_label = tk.Label(self.root, text="Load samples from DB or import Excel.", anchor='w', bd=1, relief=tk.SUNKEN)
        self.status_label.pack(fill=tk.X, padx=10, pady=5)
        
        # Load samples from DB on dashboard start for user
        self.load_samples_from_db()

    def load_samples_from_db(self):
        """Loads sample data from Firestore and populates the local DataFrame and Treeview."""
        self.tree.delete(*self.tree.get_children())
        samples_list = []
        try:
            samples_ref = db.collection("samples")
            # Query for samples submitted by the current user
            # Use standard .where() method
            samples = samples_ref.where("submitted_by_employee_id", "==", self.app.current_user['employee_id']).stream()
            
            for sample in samples:
                data = sample.to_dict()
                if isinstance(data.get('maturation_date'), datetime):
                    data['maturation_date'] = data['maturation_date']
                else: # Convert Firestore Timestamp to datetime object for consistency
                    data['maturation_date'] = data['maturation_date'].to_datetime()
                samples_list.append(data)
            
            if samples_list:
                self.app.data = pd.DataFrame(samples_list)
                # Ensure all required columns are present in the DataFrame for display
                for col in ["sample_id", "owner", "maturation_date", "status", "batch_id"]:
                    if col not in self.app.data.columns:
                        self.app.data[col] = None 
                # Rename columns for Treeview display
                self.app.data.rename(columns={
                    'sample_id': 'SampleID', 
                    'owner': 'Owner', 
                    'maturation_date': 'MaturationDate', 
                    'status': 'Status', 
                    'batch_id': 'BatchID'
                }, inplace=True)
                self.refresh_tree()
                self.status_label.config(text=f"Loaded {len(self.app.data)} samples from database.")
            else:
                self.app.data = pd.DataFrame(columns=["SampleID", "Owner", "MaturationDate", "Status", "BatchID"])
                self.refresh_tree()
                self.status_label.config(text="No samples found in the database for this user.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load samples from database: {e}")
            self.status_label.config(text="Failed to load samples from database.")

    def import_excel(self):
        """Imports data from an Excel file into the application's local DataFrame."""
        filetypes = (("Excel files", "*.xlsx *.xls"), ("All files", "*.*"))
        filename = filedialog.askopenfilename(title="Open Excel file", filetypes=filetypes)
        if filename:
            try:
                self.app.data = pd.read_excel(filename)
                # Ensure required columns for display, including a placeholder for BatchID
                if 'Status' not in self.app.data.columns:
                    self.app.data['Status'] = 'pending'
                if 'BatchID' not in self.app.data.columns: 
                    self.app.data['BatchID'] = 'N/A (Local)' 
                self.app.file_path = filename
                self.refresh_tree()
                self.status_label.config(text=f"Loaded data from {os.path.basename(filename)} (Local)")
                self.excel_imported = True
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
            self.tree.insert("", tk.END, values=(row['SampleID'], row['Owner'], mat_date_str, row['Status'], row.get('BatchID', 'N/A')))

    def generate_barcode(self):
        """Generates a barcode for the selected sample ID."""
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample from the list.")
            return
        item = self.tree.item(selected[0])
        sample_id = str(item['values'][0]) 

        try:
            EAN = barcode.get_barcode_class('code128') 
            ean = EAN(sample_id, writer=ImageWriter())
            save_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                     filetypes=[("PNG files", "*.png")],
                                                     initialfile=f"{sample_id}_barcode.png")
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
                notifications.append(f"Sample {row['SampleID']} owned by {row['Owner']} matures on {mat_date_dt.strftime('%Y-%m-%d')}.")

        if notifications:
            messagebox.showinfo("Notifications", "\n".join(notifications))
        else:
            messagebox.showinfo("Notifications", f"No samples maturing within {NOTIFICATION_DAYS_BEFORE} days.")

    def add_sample(self):
        """Opens a form to add a new sample, with option to create new batch or select existing."""
        form = tk.Toplevel(self.root)
        form.title("Add New Sample")
        form.geometry("500x550") 
        form.grab_set()
        form.transient(self.root)

        notebook = ttk.Notebook(form)
        notebook.pack(expand=True, fill="both", padx=10, pady=10)

        # --- Batch Selection/Creation Tab ---
        batch_frame = ttk.Frame(notebook, padding=10)
        notebook.add(batch_frame, text="Select/Create Batch")

        self.batch_choice = tk.StringVar(value="existing")
        ttk.Radiobutton(batch_frame, text="Select Existing Batch", variable=self.batch_choice, value="existing",
                        command=lambda: self.toggle_batch_fields(batch_frame, True)).grid(row=0, column=0, columnspan=2, sticky="w", pady=5)
        ttk.Radiobutton(batch_frame, text="Create New Batch", variable=self.batch_choice, value="new",
                        command=lambda: self.toggle_batch_fields(batch_frame, False)).grid(row=1, column=0, columnspan=2, sticky="w", pady=5)

        ttk.Label(batch_frame, text="Existing Batch ID:").grid(row=2, column=0, sticky="e", pady=5, padx=5)
        self.existing_batch_combobox = ttk.Combobox(batch_frame, state="readonly", width=30)
        self.existing_batch_combobox.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
        self.load_existing_batches_into_combobox() 

        ttk.Label(batch_frame, text="New Product Name:").grid(row=3, column=0, sticky="e", pady=5, padx=5)
        self.new_batch_product_name = ttk.Entry(batch_frame, width=30)
        self.new_batch_product_name.grid(row=3, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(batch_frame, text="New Description:").grid(row=4, column=0, sticky="e", pady=5, padx=5)
        self.new_batch_description = ttk.Entry(batch_frame, width=30)
        self.new_batch_description.grid(row=4, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(batch_frame, text="New Batch Test Date (YYYY-MM-DD):").grid(row=5, column=0, sticky="e", pady=5, padx=5)
        self.new_batch_test_date = ttk.Entry(batch_frame, width=30)
        self.new_batch_test_date.grid(row=5, column=1, sticky="ew", pady=5, padx=5)
        
        self.toggle_batch_fields(batch_frame, True) 

        # --- Sample Details Tab ---
        sample_frame = ttk.Frame(notebook, padding=10)
        notebook.add(sample_frame, text="Sample Details")

        ttk.Label(sample_frame, text="Sample ID:").grid(row=0, column=0, sticky="e", pady=5, padx=5)
        self.entry_sample_id = ttk.Entry(sample_frame, width=30)
        self.entry_sample_id.grid(row=0, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(sample_frame, text="Sample Owner:").grid(row=1, column=0, sticky="e", pady=5, padx=5)
        self.entry_owner = ttk.Entry(sample_frame, width=30)
        self.entry_owner.grid(row=1, column=1, sticky="ew", pady=5, padx=5)

        ttk.Label(sample_frame, text="Maturation Date (YYYY-MM-DD):").grid(row=2, column=0, sticky="e", pady=5, padx=5)
        self.entry_date = ttk.Entry(sample_frame, width=30)
        self.entry_date.grid(row=2, column=1, sticky="ew", pady=5, padx=5)
        
        ttk.Label(sample_frame, text="Status:").grid(row=3, column=0, sticky="e", pady=5, padx=5)
        self.status_combobox = ttk.Combobox(sample_frame, values=["pending", "approved", "rejected"], state="readonly", width=27)
        self.status_combobox.grid(row=3, column=1, sticky="ew", pady=5, padx=5)
        self.status_combobox.current(0) 

        ttk.Button(form, text="Submit Sample", command=lambda: self.submit_new_sample(form)).pack(pady=10) # Pass form to close it
        form.protocol("WM_DELETE_WINDOW", form.destroy)

    def toggle_batch_fields(self, parent_frame, is_existing_batch_selected):
        """Toggles the visibility/state of new/existing batch fields."""
        if is_existing_batch_selected:
            self.existing_batch_combobox.config(state="readonly")
            self.new_batch_product_name.config(state="disabled")
            self.new_batch_description.config(state="disabled")
            self.new_batch_test_date.config(state="disabled")
            self.new_batch_product_name.delete(0, tk.END)
            self.new_batch_description.delete(0, tk.END)
            self.new_batch_test_date.delete(0, tk.END)
        else:
            self.existing_batch_combobox.config(state="disabled")
            self.new_batch_product_name.config(state="normal")
            self.new_batch_description.config(state="normal")
            self.new_batch_test_date.config(state="normal")
            self.existing_batch_combobox.set('') 

    def load_existing_batches_into_combobox(self):
        """Loads batch IDs from Firestore into the combobox."""
        batches_ref = db.collection("batches")
        try:
            batches = batches_ref.stream()
            batch_ids = [batch.id for batch in batches]
            self.existing_batch_combobox['values'] = batch_ids
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load existing batches: {e}")
            self.existing_batch_combobox['values'] = []

    def submit_new_sample(self, form_window):
        """Handles submission of a new sample, creating a batch if necessary."""
        sample_id = self.entry_sample_id.get().strip()
        owner = self.entry_owner.get().strip()
        date_str = self.entry_date.get().strip()
        sample_status = self.status_combobox.get().strip()

        if not sample_id or not owner or not date_str:
            messagebox.showerror("Error", "All sample fields are required.")
            return

        try:
            mat_date = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Error", "Invalid maturation date format. UseYYYY-MM-DD.")
            return

        try:
            existing_sample = db.collection("samples").document(sample_id).get()
            if existing_sample.exists:
                messagebox.showerror("Error", "Sample ID already exists in the database. Please use a unique ID.")
                return
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to check existing sample ID: {e}")
            return

        selected_batch_id = None
        new_batch_data = None
        
        if self.batch_choice.get() == "new":
            product_name = self.new_batch_product_name.get().strip()
            description = self.new_batch_description.get().strip()
            test_date_str = self.new_batch_test_date.get().strip()

            if not product_name:
                messagebox.showerror("Error", "New Batch Product Name is required.")
                return
            if not test_date_str:
                messagebox.showerror("Error", "New Batch Test Date is required.")
                return
            try:
                batch_test_date = datetime.strptime(test_date_str, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Error", "Invalid New Batch Test Date format. UseYYYY-MM-DD.")
                return

            selected_batch_id = f"batch_{self.app.current_user['employee_id']}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            new_batch_data = {
                "batch_id": selected_batch_id,
                "product_name": product_name,
                "description": description,
                "test_date": batch_test_date,
                "user_employee_id": self.app.current_user['employee_id'],
                "user_username": self.app.current_user['username'],
                "user_email": self.app.current_user['email'],
                "submission_date": datetime.now(), # Use current datetime for submission
                "status": "pending", 
                "number_of_samples": 0 
            }
        else: 
            selected_batch_id = self.existing_batch_combobox.get().strip()
            if not selected_batch_id:
                messagebox.showerror("Error", "Please select an existing batch.")
                return
            existing_batch_doc = db.collection("batches").document(selected_batch_id).get()
            if not existing_batch_doc.exists:
                messagebox.showerror("Error", "Selected batch does not exist in the database.")
                return

        sample_data = {
            "sample_id": sample_id,
            "owner": owner,
            "maturation_date": mat_date,
            "status": sample_status,
            "batch_id": selected_batch_id, 
            "submitted_by_employee_id": self.app.current_user['employee_id']
        }

        try:
            batch_write = db.batch()

            if new_batch_data:
                batch_write.set(db.collection("batches").document(selected_batch_id), new_batch_data)
            
            sample_doc_ref = db.collection("samples").document(sample_id)
            batch_write.set(sample_doc_ref, sample_data)

            batch_doc_ref = db.collection("batches").document(selected_batch_id)
            current_batch_doc = batch_doc_ref.get()
            if current_batch_doc.exists:
                current_sample_count = current_batch_doc.to_dict().get("number_of_samples", 0)
                batch_write.update(batch_doc_ref, {"number_of_samples": current_sample_count + 1})
            else:
                batch_write.set(batch_doc_ref, {"number_of_samples": 1}, merge=True) 

            batch_write.commit()

            messagebox.showinfo("Success", f"Sample '{sample_id}' added successfully to Batch '{selected_batch_id}'.")
            
            self.load_samples_from_db()
            self.app.admin_logic.load_batches() # Refresh admin batch list via app instance

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
        sample_id = item['values'][0]
        batch_id = item['values'][4] 

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete sample '{sample_id}' from Batch '{batch_id}'?")
        if not confirm:
            return

        try:
            batch_write = db.batch()

            sample_doc_ref = db.collection("samples").document(sample_id)
            batch_write.delete(sample_doc_ref)

            batch_doc_ref = db.collection("batches").document(batch_id)
            current_batch_doc = batch_doc_ref.get()
            if current_batch_doc.exists:
                current_sample_count = current_batch_doc.to_dict().get("number_of_samples", 0)
                if current_sample_count > 0:
                    batch_write.update(batch_doc_ref, {"number_of_samples": current_sample_count - 1})
            
            batch_write.commit()

            messagebox.showinfo("Success", f"Sample '{sample_id}' deleted successfully.")
            self.load_samples_from_db() 
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
        sample_id = item['values'][0]

        try:
            sample_doc = db.collection("samples").document(sample_id).get()
            if not sample_doc.exists:
                messagebox.showerror("Error", "Selected sample not found in database.")
                self.load_samples_from_db() 
                return
            row = sample_doc.to_dict()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to retrieve sample data: {e}")
            return

        form = tk.Toplevel(self.root)
        form.title(f"Edit Sample {sample_id}")
        form.geometry("300x250") 
        form.grab_set()
        form.transient(self.root)

        tk.Label(form, text="Sample ID:").pack(pady=5)
        entry_sample_id = tk.Entry(form)
        entry_sample_id.insert(0, row.get('sample_id', ''))
        entry_sample_id.config(state='disabled') 
        entry_sample_id.pack()

        tk.Label(form, text="Sample Owner:").pack(pady=5)
        entry_owner = tk.Entry(form)
        entry_owner.insert(0, row.get('owner', ''))
        entry_owner.pack()

        tk.Label(form, text="Maturation Date (YYYY-MM-DD):").pack(pady=5)
        entry_date = tk.Entry(form)
        mat_date_val = row.get('maturation_date')
        if isinstance(mat_date_val, datetime):
            entry_date.insert(0, mat_date_val.strftime('%Y-%m-%d'))
        elif isinstance(mat_date_val, pd.Timestamp): # In case it's a Pandas Timestamp
            entry_date.insert(0, mat_date_val.strftime('%Y-%m-%d'))
        else:
            entry_date.insert(0, str(mat_date_val if mat_date_val else ''))
        entry_date.pack()

        tk.Label(form, text="Status:").pack(pady=5)
        status_combobox = ttk.Combobox(form, values=["pending", "approved", "rejected"], state="readonly", width=27)
        status_combobox.pack()
        status_combobox.set(row.get('status', 'pending')) 

        def submit_edit():
            owner = entry_owner.get().strip()
            date_str = entry_date.get().strip()
            status = status_combobox.get().strip()

            if not owner or not date_str:
                messagebox.showerror("Error", "All fields are required.")
                return
            try:
                mat_date = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception:
                messagebox.showerror("Error", "Invalid date format. UseYYYY-MM-DD.")
                return

            confirm = messagebox.askyesno("Confirm Edit", f"Are you sure you want to save changes to sample '{sample_id}'?")
            if not confirm:
                return
            
            updated_data = {
                'owner': owner,
                'maturation_date': mat_date,
                'status': status
            }

            try:
                db.collection("samples").document(sample_id).update(updated_data)
                messagebox.showinfo("Success", f"Sample '{sample_id}' updated successfully.")
                self.load_samples_from_db() 
                form.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to update sample: {e}")

        tk.Button(form, text="Save Changes", command=submit_edit).pack(pady=10)
        form.protocol("WM_DELETE_WINDOW", form.destroy)
