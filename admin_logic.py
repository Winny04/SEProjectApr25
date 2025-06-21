# admin_logic.py
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import pandas as pd
from datetime import datetime
import os
from firebase_setup import db
import firebase_admin


class AdminLogic:
    def __init__(self, root, app_instance):
        self.root = root
        self.app = app_instance
        self.users_tree = None
        self.batches_tree = None

    def admin_dashboard(self):
        """Displays the admin dashboard with user and batch management."""
        print("\n--- Initializing Admin Dashboard ---")
        self.app.clear_root()
        self.root.geometry("1200x700")

        # Top frame for Logout button and Welcome message
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(top_frame, text="Logout", command=self.app.logout).pack(side="right")
        ttk.Label(top_frame, text=f"Welcome, Admin {self.app.current_user.get('username')}!",
                  font=("Helvetica", 16)).pack(side="left", expand=True)

        # Users Section
        ttk.Label(self.root, text="User Management", font=("Helvetica", 14, "bold")).pack(pady=(20, 5))
        self.users_tree = ttk.Treeview(self.root, columns=("EmployeeID", "Username", "Email", "Role", "Status"),
                                       show='headings')
        self.users_tree.heading("EmployeeID", text="Employee ID")
        self.users_tree.heading("Username", text="Username")
        self.users_tree.heading("Email", text="Email")
        self.users_tree.heading("Role", text="Role")
        self.users_tree.heading("Status", text="Status")  # New: Status heading

        self.users_tree.column("EmployeeID", width=120, anchor="center")
        self.users_tree.column("Username", width=120, anchor="center")
        self.users_tree.column("Email", width=200, anchor="center")
        self.users_tree.column("Role", width=80, anchor="center")
        self.users_tree.column("Status", width=80, anchor="center")

        self.users_tree.pack(expand=True, fill="both", padx=10, pady=10)

        btn_user_frame = ttk.Frame(self.root)
        btn_user_frame.pack(pady=5)

        ttk.Button(btn_user_frame, text="Add User", command=self.admin_add_user).pack(side="left", padx=5)
        ttk.Button(btn_user_frame, text="Edit User", command=self.admin_edit_user).pack(side="left", padx=5)
        ttk.Button(btn_user_frame, text="Delete User", command=self.admin_delete_user).pack(side="left", padx=5)
        ttk.Button(btn_user_frame, text="Approve User", command=self.admin_approve_user).pack(side="left",
                                                                                              padx=5)

        self.load_users()

        # Batches Section
        ttk.Label(self.root, text="Batch Approval", font=("Helvetica", 14, "bold")).pack(pady=(20, 5))
        self.batches_tree = ttk.Treeview(self.root,
                                         columns=(
                                             "BatchID", "Product Name", "Description", "Submission Date", "User",
                                             "Status",
                                             "Sample Count"),
                                         show='headings')
        # Updated heading for the date column to 'Submission Date'
        self.batches_tree.heading("Submission Date", text="Submission Date")  # Changed heading text
        # Ensure all other columns are also correctly configured
        for col_name in ["BatchID", "Product Name", "Description", "User", "Status", "Sample Count"]:
            self.batches_tree.heading(col_name, text=col_name)
            self.batches_tree.column(col_name, width=100, anchor="center")
        # Adjust column width for Submission Date if necessary
        self.batches_tree.column("Submission Date", width=120, anchor="center")

        self.batches_tree.pack(expand=True, fill="both", padx=10, pady=10)

        btn_batch_frame = ttk.Frame(self.root)
        btn_batch_frame.pack(pady=5)

        ttk.Button(btn_batch_frame, text="View Samples", command=self.admin_view_samples_for_batch).pack(side="left", padx=5) # New button
        ttk.Button(btn_batch_frame, text="Export Approved Batches", command=self.export_user_batches).pack(side="left",
                                                                                                           padx=5)

        self.load_batches()
        print("--- Admin Dashboard Initialized ---")

    def load_users(self):
        """Loads user data from Firestore and populates the users treeview."""
        print("--- AdminLogic: Attempting to load users ---")
        if self.users_tree is None:
            print("AdminLogic: users_tree is None. Admin dashboard not initialized. Skipping user load.")
            return

        self.users_tree.delete(*self.users_tree.get_children())
        users = db.collection("users").stream()
        for user in users:
            data = user.to_dict()
            self.users_tree.insert("", "end", iid=user.id,
                                   values=(data.get("employee_id"), data.get("username", ""),
                                           data.get("email"), data.get("role"),
                                           data.get("status", "active" if data.get("role") == "admin" else "pending")))
        print("--- AdminLogic: Users loaded ---")

    def admin_add_user(self):
        """Opens a form to add a new user by delegating to AuthManager."""
        self.app.auth_manager.user_form_window()

    def admin_edit_user(self):
        """Opens a form to edit an existing user by delegating to AuthManager."""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a user to edit.")
            return
        user_id = selected[0]
        user_doc = db.collection("users").document(user_id).get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            self.app.auth_manager.user_form_window(user_id=user_id, user_data=user_data)

    def admin_delete_user(self):
        """Deletes a selected user from Firestore."""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a user to delete.")
            return
        user_id = selected[0]
        confirm = messagebox.askyesno("Confirm Delete",
                                      f"Are you sure you want to delete user with Employee ID '{user_id}'?")
        if confirm:
            try:
                db.collection("users").document(user_id).delete()
                messagebox.showinfo("Success", "User deleted successfully.")
                self.load_users()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to delete user: {e}")

    def admin_approve_user(self):
        """Approves a selected user by changing their status to 'active'."""
        selected = self.users_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a user to approve.")
            return
        user_id = selected[0]
        user_doc = db.collection("users").document(user_id).get()

        if not user_doc.exists:
            messagebox.showerror("Error", "User not found.")
            return

        user_data = user_doc.to_dict()
        if user_data.get("status") == "active":
            messagebox.showinfo("Info", "User is already active.")
            return

        confirm = messagebox.askyesno("Confirm Approval",
                                      f"Are you sure you want to approve user '{user_data.get('username')}'?")
        if confirm:
            try:
                db.collection("users").document(user_id).update({"status": "active"})
                messagebox.showinfo("Success", f"User '{user_data.get('username')}' approved successfully.")
                self.load_users()  # Refresh the user list
            except Exception as e:
                messagebox.showerror("Error", f"Failed to approve user: {e}")

    def load_batches(self):
        """Loads batch data from Firestore and populates the batches treeview."""
        print("--- AdminLogic: Attempting to load batches ---")
        if self.batches_tree is None:
            print("AdminLogic: batches_tree is None. Admin dashboard not initialized. Skipping batch load.")
            return

        self.batches_tree.delete(*self.batches_tree.get_children())
        # Query for batches with status "pending"
        batches = db.collection("batches").where("status", "==", "pending approval").stream()
        for batch in batches:
            data = batch.to_dict()
            # Get submission_date instead of maturation_date for batches
            submission_date_str = data.get("submission_date", "")

            # Check if it's already a datetime object (which it should be if from Firestore Timestamp)
            if isinstance(submission_date_str, datetime):
                submission_date_str = submission_date_str.strftime("%Y-%m-%d")
            else:
                # Fallback for anything else (e.g., if it's a string or None initially)
                submission_date_str = str(submission_date_str) if submission_date_str is not None else ''

            self.batches_tree.insert("", "end", iid=batch.id,
                                     values=(data.get("batch_id", ""),
                                             data.get("product_name", ""),
                                             data.get("description", ""),
                                             submission_date_str,  # Using the formatted submission_date_str
                                             data.get("user_email", ""),
                                             data.get("status", "pending approval"),
                                             data.get("number_of_samples", 0)))
        print("--- AdminLogic: Batches loaded ---")

    def admin_view_samples_for_batch(self):
        """Opens a new window to display samples associated with the selected batch."""
        selected = self.batches_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a batch to view its samples.")
            return

        batch_doc_id = selected[0]
        batch_doc = db.collection("batches").document(batch_doc_id).get()

        if not batch_doc.exists:
            messagebox.showerror("Error", "Selected batch not found.")
            return

        batch_data = batch_doc.to_dict()
        batch_id_from_doc = batch_data.get("batch_id")  # Get the 'batch_id' field from the batch document
        product_name = batch_data.get("product_name")
        user_employee_id = batch_data.get("user_employee_id", "")  # Get user_employee_id from batch

        if not batch_id_from_doc:
            messagebox.showerror("Error", "Batch ID not found for the selected batch.")
            return

        samples_window = tk.Toplevel(self.root)
        samples_window.title(f"Samples for Batch: {product_name} ({batch_id_from_doc})")  # Use the actual batch_id
        samples_window.geometry("800x550")  # Slightly increased height for new button

        ttk.Label(samples_window, text=f"Samples for Batch: {product_name} (ID: {batch_id_from_doc})",
                  font=("Helvetica", 14, "bold")).pack(pady=10)

        samples_tree = ttk.Treeview(samples_window,
                                    columns=(
                                        "SampleID", "Owner", "Maturation Date", "Status", "Creation Date"),
                                    show='headings')

        samples_tree.heading("SampleID", text="Sample ID")
        samples_tree.heading("Owner", text="Owner")
        samples_tree.heading("Maturation Date", text="Maturation Date")
        samples_tree.heading("Status", text="Status")
        samples_tree.heading("Creation Date", text="Creation Date")

        samples_tree.column("SampleID", width=100, anchor="center")
        samples_tree.column("Owner", width=100, anchor="center")
        samples_tree.column("Maturation Date", width=120, anchor="center")
        samples_tree.column("Status", width=100, anchor="center")
        samples_tree.column("Creation Date", width=120, anchor="center")

        samples_tree.pack(expand=True, fill="both", padx=10, pady=10)

        # Frame for buttons below the samples tree
        btn_sample_frame = ttk.Frame(samples_window)
        btn_sample_frame.pack(pady=5)

        ttk.Button(btn_sample_frame, text="Add Sample to Batch",
                   command=lambda: self.sample_form_window(batch_id_from_doc, user_employee_id, samples_tree,
                                                           product_name)).pack(side="left", padx=5)
        # New "Approve Sample" button
        ttk.Button(btn_sample_frame, text="Approve Sample",
                   command=lambda: self.admin_approve_sample(samples_tree, batch_doc_id)).pack(side="left", padx=5)

        self._load_samples_into_tree(batch_id_from_doc, samples_tree)  # Initial load using the actual batch_id

    def admin_approve_sample(self, samples_tree_ref, batch_doc_id):
        """Approves a selected sample and checks/updates the parent batch status."""
        selected_sample_iid = samples_tree_ref.selection()
        if not selected_sample_iid:
            messagebox.showinfo("Info", "Please select a sample to approve.")
            return

        sample_tree_data = samples_tree_ref.item(selected_sample_iid[0], 'values')
        sample_id_from_tree = sample_tree_data[0]  # Assuming Sample ID is the first column

        # Find the Firestore document ID for the selected sample using its sample_id and batch_id
        sample_query = db.collection("samples").where("sample_id", "==", sample_id_from_tree).where("batch_id", "==",
                                                                                                    batch_doc_id).limit(
            1).get()

        if not sample_query:
            messagebox.showerror("Error", "Selected sample not found in database.")
            return

        sample_doc_ref = sample_query[0].reference
        sample_doc = sample_query[0].to_dict()

        if sample_doc.get("status") == "approved":
            messagebox.showinfo("Info", "Sample is already approved.")
            return

        confirm = messagebox.askyesno("Confirm Approve Sample",
                                      f"Approve sample '{sample_doc.get('sample_id')}'?")
        if confirm:
            try:
                # Update sample status
                sample_doc_ref.update({"status": "approved"})
                messagebox.showinfo("Success", f"Sample '{sample_doc.get('sample_id')}' approved successfully.")

                # Reload samples for the current batch view
                self._load_samples_into_tree(batch_doc_id, samples_tree_ref)

                # Now, check if all samples in the batch are approved
                all_samples_approved = True
                associated_samples_in_batch = db.collection("samples").where("batch_id", "==", batch_doc_id).stream()

                # Check for samples in the generator before iterating
                samples_exist = False
                for s in associated_samples_in_batch:
                    samples_exist = True
                    s_data = s.to_dict()
                    if s_data.get("status") != "approved":
                        all_samples_approved = False
                        break  # Found a pending sample, no need to check further

                if all_samples_approved and samples_exist:  # Only set batch to approved if there are samples and all are approved
                    batch_ref = db.collection("batches").document(batch_doc_id)
                    current_batch_status = batch_ref.get().to_dict().get("status")
                    if current_batch_status != "approved":
                        batch_ref.update({"status": "approved"})
                        messagebox.showinfo("Batch Status Update",
                                            f"Batch '{batch_doc_id}' status updated to 'approved' as all samples are approved.")
                        self.load_batches()  # Refresh the main batches tree
                elif not all_samples_approved:
                    # If any sample is not approved, ensure batch status is not 'approved'
                    batch_ref = db.collection("batches").document(batch_doc_id)
                    current_batch_status = batch_ref.get().to_dict().get("status")
                    if current_batch_status == "approved" and not all_samples_approved:
                        # This case handles if a sample was rejected after batch was approved.
                        # Or if a batch was manually approved but then a sample status reverted.
                        # For this scenario, we might want to revert the batch to pending.
                        # However, the user request states "if one sample still pending batch show pending".
                        # So, we only need to act if it's currently 'approved' and should be 'pending'.
                        # If it's already pending, no action needed.
                        batch_ref.update({"status": "pending"})
                        messagebox.showinfo("Batch Status Update",
                                            f"Batch '{batch_doc_id}' status updated to 'pending approval' as some samples are not yet approved.")
                        self.load_batches()  # Refresh the main batches tree
                # If no samples exist in the batch, the batch remains as it is or can be handled as a special case.
                # Currently, it won't be set to 'approved' if there are no samples.

            except Exception as e:
                messagebox.showerror("Error", f"Failed to approve sample or update batch status: {e}")

    def _load_samples_into_tree(self, batch_id, samples_tree):
        """Helper method to load samples into the provided treeview."""
        samples_tree.delete(*samples_tree.get_children())
        print(f"--- Loading samples for batch_id: {batch_id} ---")
        try:
            # The query should be against the 'batch_id' field in the samples collection
            associated_samples = db.collection("samples").where("batch_id", "==", batch_id).stream()
            samples_found = 0
            for sample in associated_samples:
                samples_found += 1
                sample_data = sample.to_dict()
                print(f"  Found sample: {sample_data.get('sample_id')}, batch_id: {sample_data.get('batch_id')}")

                maturation_date_str = ""
                if isinstance(sample_data.get('maturation_date'), datetime):
                    maturation_date_str = sample_data['maturation_date'].strftime("%Y-%m-%d")
                elif isinstance(sample_data.get('maturation_date'), firebase_admin.firestore.Timestamp):
                    maturation_date_str = sample_data['maturation_date'].to_datetime().strftime("%Y-%m-%d")
                else:
                    maturation_date_str = str(sample_data.get('maturation_date', ''))

                creation_date_str = ""
                if isinstance(sample_data.get('creation_date'), datetime):
                    creation_date_str = sample_data['creation_date'].strftime("%Y-%m-%d %H:%M:%S")
                elif isinstance(sample_data.get('creation_date'), firebase_admin.firestore.Timestamp):
                    creation_date_str = sample_data['creation_date'].to_datetime().strftime("%Y-%m-%d %H:%M:%S")
                else:
                    creation_date_str = str(sample_data.get('creation_date', ''))

                samples_tree.insert("", "end", iid=sample.id,  # Store document ID for easy reference
                                    values=(sample_data.get("sample_id", ""),
                                            sample_data.get("owner", ""),
                                            maturation_date_str,
                                            sample_data.get("status", ""),
                                            creation_date_str))
            if samples_found == 0:
                print(f"--- No samples found for batch_id: {batch_id} ---")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load samples for batch: {e}")
            print(f"Error loading samples: {e}")

    def sample_form_window(self, batch_id, user_employee_id_from_batch, samples_tree_ref, product_name):
        """Opens a form to add a new sample to a specified batch."""
        form_window = tk.Toplevel(self.root)
        form_window.title(f"Add Sample to {product_name} ({batch_id})")
        form_window.geometry("400x350")
        form_window.transient(self.root)  # Make it appear on top of main window
        form_window.grab_set()  # Make it modal

        form_frame = ttk.Frame(form_window, padding="15")
        form_frame.pack(fill="both", expand=True)

        # Labels and Entry fields for sample details
        ttk.Label(form_frame, text="Sample ID:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        sample_id_entry = ttk.Entry(form_frame, width=30)
        sample_id_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(form_frame, text="Owner:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        owner_entry = ttk.Entry(form_frame, width=30)
        # Prefer pre-filling owner with the batch's user's username if available, otherwise current admin's username
        if self.app.current_user:
            if user_employee_id_from_batch:
                user_doc = db.collection("users").where("employee_id", "==", user_employee_id_from_batch).limit(1).get()
                if user_doc:
                    owner_entry.insert(0, user_doc[0].to_dict().get("username", ""))
                else:
                    owner_entry.insert(0, self.app.current_user.get("username", ""))
            else:
                owner_entry.insert(0, self.app.current_user.get("username", ""))
        owner_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(form_frame, text="Maturation Date (YYYY-MM-DD):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        maturation_date_entry = ttk.Entry(form_frame, width=30)
        maturation_date_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        ttk.Label(form_frame, text="Status:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        status_combobox = ttk.Combobox(form_frame, values=["pending approval", "approved", "rejected"],
                                       state="readonly", width=28)
        status_combobox.set("pending approval")  # Default status
        status_combobox.grid(row=3, column=1, padx=5, pady=5, sticky="ew")

        # Save Button
        def save_sample_data():
            s_id = sample_id_entry.get().strip()
            owner = owner_entry.get().strip()
            mat_date_str = maturation_date_entry.get().strip()
            status = status_combobox.get().strip()

            if not s_id or not owner or not mat_date_str:
                messagebox.showerror("Input Error", "All fields are required.", parent=form_window)
                return

            try:
                maturation_date = datetime.strptime(mat_date_str, "%Y-%m-%d")
            except ValueError:
                messagebox.showerror("Input Error", "Invalid Maturation Date format. Please use YYYY-MM-DD.",
                                     parent=form_window)
                return

            # Determine submitted_by_employee_id
            # Prefer the employee_id from the batch, otherwise use the current admin's employee_id
            submitted_by_id = user_employee_id_from_batch
            if not submitted_by_id and self.app.current_user:
                submitted_by_id = self.app.current_user.get('employee_id', '')

            if not submitted_by_id:
                messagebox.showwarning("Warning",
                                       "Could not determine employee ID for submission. Sample will be added without it.",
                                       parent=form_window)

            new_sample_data = {
                "batch_id": batch_id,  # This is the crucial link to the batch
                "sample_id": s_id,
                "owner": owner,
                "maturation_date": maturation_date,
                "status": status,
                "creation_date": datetime.now(),
                "submitted_by_employee_id": submitted_by_id
            }

            try:
                db.collection("samples").add(new_sample_data)
                messagebox.showinfo("Success", "Sample added successfully!", parent=form_window)
                self._load_samples_into_tree(batch_id, samples_tree_ref)  # Refresh the samples tree
                # After adding a new sample, the batch status might need to be re-evaluated
                # If adding a 'pending' sample, the batch should go to 'pending' if it was 'approved'
                batch_ref = db.collection("batches").document(batch_id)
                current_batch_status = batch_ref.get().to_dict().get("status")
                if status == "pending approval" and current_batch_status == "approved":
                    batch_ref.update({"status": "pending"})
                    self.load_batches()  # Refresh main batches tree
                form_window.destroy()  # Close the form window
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add sample: {e}", parent=form_window)

        save_button = ttk.Button(form_frame, text="Save Sample", command=save_sample_data)
        save_button.grid(row=4, column=0, columnspan=2, pady=10)

        form_window.wait_window()  # Wait for the form window to close

    def export_user_batches(self):
        """Exports approved batches and their associated samples to an Excel file."""
        approved_batches_data = []
        batches_ref = db.collection("batches")
        samples_ref = db.collection("samples")

        approved_batches = batches_ref.where("status", "==", "approved").get()

        if not approved_batches:
            messagebox.showwarning("Warning", "No approved batches to export.")
            return

        for batch in approved_batches:
            batch_data = batch.to_dict()
            actual_batch_id_field = batch_data.get("batch_id")

            # Handle batch_test_date_str
            batch_test_date_str = ""
            test_date_obj = batch_data.get('test_date')
            if isinstance(test_date_obj, datetime):
                batch_test_date_str = test_date_obj.strftime("%Y-%m-%d")
            elif isinstance(test_date_obj, firebase_admin.firestore.Timestamp):
                batch_test_date_str = test_date_obj.to_datetime().strftime("%Y-%m-%d")

            # Handle batch_maturation_date_str
            batch_maturation_date_str = ""
            maturation_date_obj = batch_data.get('maturation_date')
            if isinstance(maturation_date_obj, datetime):
                batch_maturation_date_str = maturation_date_obj.strftime("%Y-%m-%d")
            elif isinstance(maturation_date_obj, firebase_admin.firestore.Timestamp):
                batch_maturation_date_str = maturation_date_obj.to_datetime().strftime("%Y-%m-%d")

            # Query samples using the 'batch_id' field from the batch document
            associated_samples = samples_ref.where("batch_id", "==", actual_batch_id_field).get()

            # It's important to have at least one entry even if no samples, so batch data is exported
            if not associated_samples:
                combined_data = {
                    "BatchID": batch_data.get("batch_id"),
                    "Product_Name": batch_data.get("product_name"),
                    "Batch_Description": batch_data.get("description"),
                    "Batch_MaturationDate": batch_maturation_date_str,
                    "Batch_Test_Date": batch_test_date_str,
                    "Batch_Status": batch_data.get("status"),
                    "User_Email": batch_data.get("user_email"),
                    "SampleID": "",
                    "Sample_Owner": "",
                    "Sample_MaturationDate": "",
                    "Sample_Status": ""
                }
                approved_batches_data.append(combined_data)

            for sample in associated_samples:
                sample_data = sample.to_dict()
                mat_date_str = ""
                sample_mat_date_obj = sample_data.get('maturation_date')
                if isinstance(sample_mat_date_obj, datetime):
                    mat_date_str = sample_mat_date_obj.strftime("%Y-%m-%d")
                elif isinstance(sample_mat_date_obj, firebase_admin.firestore.Timestamp):
                    mat_date_str = sample_mat_date_obj.to_datetime().strftime("%Y-%m-%d")
                else:
                    mat_date_str = str(sample_data.get('maturation_date', ''))

                combined_data = {
                    "BatchID": batch_data.get("batch_id"),
                    "Product_Name": batch_data.get("product_name"),
                    "Batch_Description": batch_data.get("description"),
                    "Batch_MaturationDate": batch_maturation_date_str,
                    "Batch_Test_Date": batch_test_date_str,
                    "Batch_Status": batch_data.get("status"),
                    "User_Email": batch_data.get("user_email"),
                    "SampleID": sample_data.get("sample_id"),
                    "Sample_Owner": sample_data.get("owner"),
                    "Sample_MaturationDate": mat_date_str,
                    "Sample_Status": sample_data.get("status")
                }
                approved_batches_data.append(combined_data)

        if not approved_batches_data:
            messagebox.showwarning("Warning", "No approved batches with samples to export.")
            return

        df_approved_with_samples = pd.DataFrame(approved_batches_data)

        filetypes = (("Excel files", "*.xlsx"),)
        filename = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                                filetypes=filetypes,
                                                initialfile="Approved_Batches_and_Samples.xlsx")
        if filename:
            try:
                df_approved_with_samples.to_excel(filename, index=False)
                messagebox.showinfo("Success",
                                    f"Approved batches and their samples exported to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export Excel file:\n{e}")