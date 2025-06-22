# admin_logic.py
import tkinter as tk
from tkinter import messagebox, ttk, filedialog
import pandas as pd
from datetime import datetime
import os
from firebase_setup import db
import firebase_admin
import logging  # Import logging module for better debugging

# Configure logging (optional, but good practice)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class AdminLogic:
    def __init__(self, root, app_instance):
        self.root = root
        self.app = app_instance
        self.users_tree = None
        self.batches_tree = None
        # self.approved_batches_tree = None # Removed this as it's no longer a separate treeview for approved batches
        self.batch_filter_var = None  # Variable to hold the selected batch filter (All, Pending, Approved)

    def admin_dashboard(self):
        """Displays the admin dashboard with user and batch management."""
        logging.info("\n--- Initializing Admin Dashboard ---")  # Changed print to logging
        self.app.clear_root()
        self.root.geometry("1200x700")

        # Top frame for Logout button and Welcome message
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill="x", padx=10, pady=10)

        ttk.Button(top_frame, text="Logout", command=self.app.logout).pack(side="right")
        ttk.Label(top_frame, text=f"Welcome, Admin {self.app.current_user.get('username')}!",
                  font=("Helvetica", 16)).pack(side="left", expand=True)

        # Main content frame to hold sidebar and central content
        main_content_frame = ttk.Frame(self.root)
        main_content_frame.pack(expand=True, fill="both", padx=10, pady=10)

        # Sidebar Frame
        sidebar_frame = ttk.Frame(main_content_frame, width=180, relief="raised", borderwidth=1)
        sidebar_frame.pack(side="left", fill="y", padx=(0, 10))
        sidebar_frame.pack_propagate(False)  # Prevent sidebar from resizing based on content

        ttk.Label(sidebar_frame, text="Navigation", font=("Helvetica", 12, "bold")).pack(pady=10)

        # Sidebar buttons
        ttk.Button(sidebar_frame, text="User Management", command=self.show_user_management).pack(fill="x", pady=5,
                                                                                                  padx=10)
        ttk.Button(sidebar_frame, text="Batch Management", command=self.show_batch_management).pack(fill="x", pady=5,
                                                                                                    padx=10)
        ttk.Button(sidebar_frame, text="Export Approved Data", command=self.export_user_batches).pack(fill="x", pady=5, padx=10)

        # Central content area
        self.central_content_frame = ttk.Frame(main_content_frame)
        self.central_content_frame.pack(side="right", expand=True, fill="both")

        # Initially show user management
        self.show_user_management()
        logging.info("--- Admin Dashboard Initialized ---")  # Changed print to logging

    def clear_central_content(self):
        """Clears all widgets from the central content frame."""
        for widget in self.central_content_frame.winfo_children():
            widget.destroy()

    def show_user_management(self):
        """Displays the user management section in the central content frame."""
        self.clear_central_content()
        # Users Section
        ttk.Label(self.central_content_frame, text="User Management", font=("Helvetica", 14, "bold")).pack(pady=(20, 5))
        self.users_tree = ttk.Treeview(self.central_content_frame,
                                       columns=("EmployeeID", "Username", "Email", "Role", "Status"),
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

        btn_user_frame = ttk.Frame(self.central_content_frame)
        btn_user_frame.pack(pady=5)

        ttk.Button(btn_user_frame, text="Add User", command=self.admin_add_user).pack(side="left", padx=5)
        ttk.Button(btn_user_frame, text="Edit User", command=self.admin_edit_user).pack(side="left", padx=5)
        ttk.Button(btn_user_frame, text="Delete User", command=self.admin_delete_user).pack(side="left", padx=5)
        ttk.Button(btn_user_frame, text="Approve User", command=self.admin_approve_user).pack(side="left",
                                                                                              padx=5)
        self.load_users()

    def show_batch_management(self):
        """Displays the batch management section in the central content frame, with a filter for status."""
        self.clear_central_content()
        ttk.Label(self.central_content_frame, text="Batch Management", font=("Helvetica", 14, "bold")).pack(
            pady=(20, 5))

        # Filter controls
        filter_frame = ttk.Frame(self.central_content_frame)
        filter_frame.pack(pady=5)

        ttk.Label(filter_frame, text="Filter by Status:").pack(side="left", padx=5)
        self.batch_filter_var = tk.StringVar(value="pending approval")  # Default to pending approval
        filter_combobox = ttk.Combobox(filter_frame, textvariable=self.batch_filter_var,
                                       values=["pending approval", "approved", "all"],
                                       state="readonly")
        filter_combobox.pack(side="left", padx=5)
        filter_combobox.bind("<<ComboboxSelected>>", lambda event: self.load_batches(self.batch_filter_var.get()))

        self.batches_tree = ttk.Treeview(self.central_content_frame,
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

        btn_batch_frame = ttk.Frame(self.central_content_frame)
        btn_batch_frame.pack(pady=5)

        ttk.Button(btn_batch_frame, text="Approve Selected Batch", command=self.admin_approve_selected_batch).pack(
            side="left", padx=5)
        ttk.Button(btn_batch_frame, text="Reject Selected Batch", command=self.admin_reject_selected_batch).pack(
            side="left", padx=5)
        ttk.Button(btn_batch_frame, text="View Samples", command=self.admin_view_samples_for_batch).pack(side="left",
                                                                                                         padx=5)
        ttk.Button(btn_batch_frame, text="Delete Batch", command=self.delete_batch).pack(side="left", padx=5)

        # Removed the "View Approved Batches" button here as well
        self.load_batches(self.batch_filter_var.get())  # Load batches based on initial filter value

    def load_users(self):
        """Loads user data from Firestore and populates the users treeview."""
        logging.info("--- AdminLogic: Attempting to load users ---")  # Changed print to logging
        if self.users_tree is None:
            logging.info(
                "AdminLogic: users_tree is None. Admin dashboard not initialized. Skipping user load.")  # Changed print to logging
            return

        self.users_tree.delete(*self.users_tree.get_children())
        users = db.collection("users").stream()
        for user in users:
            data = user.to_dict()
            self.users_tree.insert("", "end", iid=user.id,
                                   values=(data.get("employee_id"), data.get("username", ""),
                                           data.get("email"), data.get("role"),
                                           data.get("status", "active" if data.get("role") == "admin" else "pending")))
        logging.info("--- AdminLogic: Users loaded ---")  # Changed print to logging

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

    def load_batches(self, status_filter="pending approval"):
        """Loads batch data from Firestore and populates the batches treeview.
           Can filter by status: "pending approval", "approved", or "all"."""
        logging.info(f"--- AdminLogic: Attempting to load batches with filter: {status_filter} ---")
        if self.batches_tree is None:
            logging.info("AdminLogic: batches_tree is None. Admin dashboard not initialized. Skipping batch load.")
            return

        self.batches_tree.delete(*self.batches_tree.get_children())

        batches_query = db.collection("batches")
        if status_filter and status_filter != "all":
            batches_query = batches_query.where("status", "==", status_filter)

        batches = batches_query.stream()

        for batch in batches:
            data = batch.to_dict()
            submission_date_str = data.get("submission_date", "")

            if isinstance(submission_date_str, datetime):
                submission_date_str = submission_date_str.strftime("%Y-%m-%d")
            elif isinstance(submission_date_str, firebase_admin.firestore.Timestamp):
                submission_date_str = submission_date_str.to_datetime().strftime("%Y-%m-%d")
            else:
                submission_date_str = str(submission_date_str) if submission_date_str is not None else ''

            self.batches_tree.insert("", "end", iid=batch.id,
                                     values=(data.get("batch_id", ""),
                                             data.get("product_name", ""),
                                             data.get("description", ""),
                                             submission_date_str,
                                             data.get("user_email", ""),
                                             data.get("status", "pending approval"),
                                             data.get("number_of_samples", 0)))
        logging.info(f"--- AdminLogic: Batches loaded with filter: {status_filter} ---")

    def admin_approve_selected_batch(self):
        """Approves the selected batch and all its associated samples."""
        selected = self.batches_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a batch to approve.")
            return

        batch_doc_id = selected[0]
        batch_doc = db.collection("batches").document(batch_doc_id).get()

        if not batch_doc.exists:
            messagebox.showerror("Error", "Selected batch not found.")
            return

        batch_data = batch_doc.to_dict()
        if batch_data.get("status") == "approved":
            messagebox.showinfo("Info", "Batch is already approved.")
            return

        confirm = messagebox.askyesno("Confirm Batch Approval",
                                      f"Are you sure you want to approve batch '{batch_data.get('product_name')}' (ID: {batch_data.get('batch_id')}) and all its samples?")
        if confirm:
            try:
                # Update batch status to approved
                db.collection("batches").document(batch_doc_id).update({"status": "approved"})

                # Also approve all samples associated with this batch
                associated_samples = db.collection("samples").where("batch_id", "==", batch_doc_id).stream()
                for sample in associated_samples:
                    sample.reference.update({"status": "approved"})

                messagebox.showinfo("Success",
                                    f"Batch '{batch_data.get('product_name')}' and all its samples approved successfully.")
                self.load_batches(self.batch_filter_var.get())  # Refresh the batches tree with current filter
            except Exception as e:
                messagebox.showerror("Error", f"Failed to approve batch and samples: {e}")

    def admin_reject_selected_batch(self):
        """Rejects the selected batch and all its associated samples."""
        selected = self.batches_tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a batch to reject.")
            return

        batch_doc_id = selected[0]
        batch_doc = db.collection("batches").document(batch_doc_id).get()

        if not batch_doc.exists:
            messagebox.showerror("Error", "Selected batch not found.")
            return

        batch_data = batch_doc.to_dict()
        if batch_data.get("status") == "rejected":
            messagebox.showinfo("Info", "Batch is already rejected.")
            return

        confirm = messagebox.askyesno("Confirm Batch Rejection",
                                      f"Are you sure you want to reject batch '{batch_data.get('product_name')}' (ID: {batch_data.get('batch_id')}) and all its samples?")
        if confirm:
            try:
                # Update batch status to rejected
                db.collection("batches").document(batch_doc_id).update({"status": "rejected"})

                # Also reject all samples associated with this batch
                associated_samples = db.collection("samples").where("batch_id", "==", batch_doc_id).stream()
                for sample in associated_samples:
                    sample.reference.update({"status": "rejected"})

                messagebox.showinfo("Success",
                                    f"Batch '{batch_data.get('product_name')}' and all its samples rejected successfully.")
                self.load_batches(self.batch_filter_var.get())  # Refresh the batches tree with current filter
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reject batch and samples: {e}")

    def admin_view_samples_for_batch(self):
        """Opens a new window to display samples associated with the selected batch with pagination."""
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
        samples_window.geometry("800x550")
        samples_window.current_page = 1  # Initialize current page for this window
        samples_window.items_per_page = 20  # Samples per page

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

        # Pagination controls frame
        pagination_frame = ttk.Frame(samples_window)
        pagination_frame.pack(pady=5)

        prev_button = ttk.Button(pagination_frame, text="Previous Page")
        prev_button.pack(side="left", padx=5)

        page_label = ttk.Label(pagination_frame, text="Page X of Y")
        page_label.pack(side="left", padx=10)

        next_button = ttk.Button(pagination_frame, text="Next Page")
        next_button.pack(side="left", padx=5)

        # Frame for buttons below the samples tree
        btn_sample_frame = ttk.Frame(samples_window)
        btn_sample_frame.pack(pady=5)

        ttk.Button(btn_sample_frame, text="Add Sample to Batch",
                   command=lambda: self.sample_form_window(batch_id_from_doc, user_employee_id, samples_tree,
                                                           product_name)).pack(side="left", padx=5)
        # New "Approve Sample" button
        ttk.Button(btn_sample_frame, text="Approve Sample",
                   command=lambda: self.admin_approve_sample(samples_tree, batch_doc_id)).pack(side="left", padx=5)
        ttk.Button(btn_sample_frame, text="Reject Sample",  # New button
                   command=lambda: self.admin_reject_sample(samples_tree, batch_doc_id)).pack(side="left", padx=5)

        def go_to_page(page_num):
            samples_window.current_page = page_num
            self._load_samples_into_tree(batch_id_from_doc, samples_tree, page_label,
                                         samples_window.current_page, samples_window.items_per_page)
            # Enable/disable buttons based on current page
            prev_button.config(state="normal" if samples_window.current_page > 1 else "disabled")
            next_button.config(
                state="normal" if samples_window.current_page < samples_window.total_pages else "disabled")

        prev_button.config(command=lambda: go_to_page(samples_window.current_page - 1))
        next_button.config(command=lambda: go_to_page(samples_window.current_page + 1))

        # Initial load of samples for the first page
        go_to_page(1)  # Load first page

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

                # Reload samples for the current batch view - need to get current page and items per page
                # This needs to be adapted to fetch the current page context if this method can be called from multiple places
                # For simplicity here, we'll assume it needs to reload the first page or the current page if context is available.
                # Since this method is called from admin_view_samples_for_batch via lambda,
                # we don't have direct access to page_label, current_page, items_per_page here.
                # A robust solution would pass these down or manage state centrally.
                # For now, a full reload of the main batch list is the safest side effect.
                self.load_batches(self.batch_filter_var.get())

                # Now, check if all samples in the batch are approved
                all_samples_approved = True
                associated_samples_in_batch = db.collection("samples").where("batch_id", "==", batch_doc_id).stream()

                # Check for samples in the generator before iterating
                samples_exist = False
                temp_samples_list = []
                for s in associated_samples_in_batch:
                    samples_exist = True
                    temp_samples_list.append(s)  # Store to iterate again if needed

                if samples_exist:
                    for s in temp_samples_list:
                        s_data = s.to_dict()
                        if s_data.get("status") != "approved":
                            all_samples_approved = False
                            break  # Found a pending or rejected sample, no need to check further
                else:  # If no samples exist, it cannot be 'all approved'
                    all_samples_approved = False

                if all_samples_approved and samples_exist:  # Only set batch to approved if there are samples and all are approved
                    batch_ref = db.collection("batches").document(batch_doc_id)
                    current_batch_status = batch_ref.get().to_dict().get("status")
                    if current_batch_status != "approved":
                        batch_ref.update({"status": "approved"})
                        messagebox.showinfo("Batch Status Update",
                                            f"Batch '{batch_doc_id}' status updated to 'approved' as all samples are approved.")
                        self.load_batches(self.batch_filter_var.get())  # Refresh the main batches tree
                elif not all_samples_approved:
                    # If any sample is not approved, ensure batch status is not 'approved'
                    batch_ref = db.collection("batches").document(batch_doc_id)
                    current_batch_status = batch_ref.get().to_dict().get("status")
                    if current_batch_status == "approved" or current_batch_status == "rejected":  # If it was approved or rejected, revert to pending approval
                        batch_ref.update({"status": "pending approval"})  # Changed to "pending approval"
                        messagebox.showinfo("Batch Status Update",
                                            f"Batch '{batch_doc_id}' status updated to 'pending approval' as some samples are not yet approved.")
                        self.load_batches(self.batch_filter_var.get())  # Refresh the main batches tree
                # If no samples exist in the batch, the batch remains as it is or can be handled as a special case.
                # Currently, it won't be set to 'approved' if there are no samples.

            except Exception as e:
                messagebox.showerror("Error", f"Failed to approve sample or update batch status: {e}")

    def admin_reject_sample(self, samples_tree_ref, batch_doc_id):
        """Rejects a selected sample and updates the parent batch status if necessary."""
        selected_sample_iid = samples_tree_ref.selection()
        if not selected_sample_iid:
            messagebox.showinfo("Info", "Please select a sample to reject.")
            return

        sample_tree_data = samples_tree_ref.item(selected_sample_iid[0], 'values')
        sample_id_from_tree = sample_tree_data[0]

        sample_query = db.collection("samples").where("sample_id", "==", sample_id_from_tree).where("batch_id", "==",
                                                                                                    batch_doc_id).limit(
            1).get()

        if not sample_query:
            messagebox.showerror("Error", "Selected sample not found in database.")
            return

        sample_doc_ref = sample_query[0].reference
        sample_doc = sample_query[0].to_dict()

        if sample_doc.get("status") == "rejected":
            messagebox.showinfo("Info", "Sample is already rejected.")
            return

        confirm = messagebox.askyesno("Confirm Reject Sample",
                                      f"Reject sample '{sample_doc.get('sample_id')}'?")
        if confirm:
            try:
                sample_doc_ref.update({"status": "rejected"})
                messagebox.showinfo("Success", f"Sample '{sample_doc.get('sample_id')}' rejected successfully.")
                self.load_batches(self.batch_filter_var.get())  # Reload the main batches tree

                # If a sample is rejected, the batch status should definitely revert to "pending approval"
                batch_ref = db.collection("batches").document(batch_doc_id)
                current_batch_status = batch_ref.get().to_dict().get("status")
                if current_batch_status != "pending approval":
                    batch_ref.update({"status": "pending approval"})
                    messagebox.showinfo("Batch Status Update",
                                        f"Batch '{batch_doc_id}' status updated to 'pending approval' as a sample was rejected.")
                    self.load_batches(self.batch_filter_var.get())
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reject sample or update batch status: {e}")

    def _load_samples_into_tree(self, batch_id, samples_tree, page_label_ref, page_number, items_per_page):
        """Helper method to load samples into the provided treeview with pagination."""
        samples_tree.delete(*samples_tree.get_children())
        logging.info(f"--- Loading samples for batch_id: {batch_id}, page: {page_number} ---")

        try:
            # First, get the total count of samples for this batch
            all_samples_query = db.collection("samples").where("batch_id", "==", batch_id).stream()
            all_samples = list(all_samples_query)  # Convert stream to list to count
            total_samples = len(all_samples)
            total_pages = (total_samples + items_per_page - 1) // items_per_page
            if total_pages == 0:
                total_pages = 1  # At least one page even if no samples

            # Update the page label in the UI
            page_label_ref.master.master.total_pages = total_pages  # Store total_pages on the samples_window
            page_label_ref.config(text=f"Page {page_number} of {total_pages}")

            # Calculate offset for Firestore query
            offset = (page_number - 1) * items_per_page

            # Fetch samples for the current page
            paginated_samples_query = db.collection("samples").where("batch_id", "==", batch_id).limit(
                items_per_page).offset(offset).stream()

            samples_found_on_page = 0
            for sample in paginated_samples_query:
                samples_found_on_page += 1
                sample_data = sample.to_dict()
                logging.info(f"  Found sample: {sample_data.get('sample_id')}, batch_id: {sample_data.get('batch_id')}")

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
            if samples_found_on_page == 0 and total_samples > 0 and page_number > 1:
                # This can happen if the last sample of a page was deleted, and the current page became empty.
                # Or if navigated to an empty page (e.g. page 3 when only 2 pages exist).
                # In such a case, navigate back to the last available page.
                logging.info("No samples on current page, navigating to previous valid page.")
                # Recursively call to go back one page. This needs careful handling to avoid infinite loops if no samples.
                # The logic for total_pages and prev/next button state should prevent this for most cases.
                page_label_ref.master.master.current_page = max(1, page_number - 1)
                self._load_samples_into_tree(batch_id, samples_tree, page_label_ref,
                                             page_label_ref.master.master.current_page, items_per_page)
            elif samples_found_on_page == 0:
                logging.info(f"--- No samples found for batch_id: {batch_id} ---")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load samples for batch: {e}")
            logging.error(f"Error loading samples: {e}", exc_info=True)

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
                messagebox.showerror("Input Error", "Invalid Maturation Date format. Please useYYYY-MM-DD.",
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
                # After adding a sample, need to reload the samples on the current page
                # This requires passing the pagination context to this method or managing it globally
                # For now, it will simply close the form and rely on a subsequent refresh if the user navigates
                # If we want to refresh the *specific* samples window, we need to pass its page_label_ref, current_page etc.
                # Simplest is to just reload the main batches tree if a sample is added/modified.
                self.load_batches(self.batch_filter_var.get())
                form_window.destroy()  # Close the form window
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add sample: {e}", parent=form_window)

        save_button = ttk.Button(form_frame, text="Save Sample", command=save_sample_data)
        save_button.grid(row=4, column=0, columnspan=2, pady=10)

        form_window.wait_window()  # Wait for the form window to close

    def delete_batch(self):
        """Deletes a selected batch and all its associated samples from Firestore."""
        logging.info("Starting delete_batch process.")
        selected = self.batches_tree.selection()  # Changed self.tree to self.batches_tree
        if not selected:
            messagebox.showinfo("Info", "Please select a batch to delete.")
            logging.warning("Delete batch aborted: No batch selected.")
            return

        item = self.batches_tree.item(selected[0])  # Changed self.tree to self.batches_tree
        # Ensure the selected item is actually a batch. Check if BatchID column is visible.
        # This is a heuristic; a more robust way would be to check self.last_loaded_query_type
        # Assuming that the first item in values is the document ID and the fifth is the visible BatchID.
        # This part requires careful alignment with how batches are loaded into the treeview.
        # The column check for "BatchID" option="width" == 0 might not be reliable here,
        # it's better to rely on the context of which treeview is being displayed.
        # Since this is in admin_logic and targets batches_tree, it's safer to assume it's a batch.

        # DocID for batches is in item['values'][0] if that's how it's inserted.
        # In current load_batches, item.id is the firestore document ID.
        firestore_batch_doc_id = selected[0]  # Use the iid from selection as Firestore document ID
        # The displayed BatchID is typically the first value in the treeview's values tuple
        batch_id_display = item['values'][0]  # Assuming BatchID is the first column in batches_tree

        logging.info(f"Attempting to delete batch: DocID='{firestore_batch_doc_id}', BatchID='{batch_id_display}'")

        confirm = messagebox.askyesno("Confirm Delete Batch",
                                      f"Are you sure you want to delete Batch '{batch_id_display}'?\n\n"
                                      "This will PERMANENTLY DELETE ALL SAMPLES associated with this batch as well. This action cannot be undone.")
        if not confirm:
            logging.info("Delete batch aborted: User cancelled.")
            return

        try:
            batch_write = db.batch()

            # 1. Delete all samples associated with this batch
            # Use 'batch_id' field in samples collection, which stores the human-readable batch_id_display
            samples_to_delete = db.collection("samples").where("batch_id", "==", batch_id_display).stream()
            deleted_samples_count = 0
            for sample_doc in samples_to_delete:
                batch_write.delete(sample_doc.reference)
                deleted_samples_count += 1
            logging.info(f"Prepared to delete {deleted_samples_count} samples for batch '{batch_id_display}'.")

            # 2. Delete the batch document itself
            batch_doc_ref = db.collection("batches").document(firestore_batch_doc_id)
            batch_write.delete(batch_doc_ref)
            logging.info(f"Prepared to delete batch document: {firestore_batch_doc_id}.")

            # Commit the batch operation
            batch_write.commit()
            logging.info("Firestore batch committed successfully (batch and samples deleted).")

            messagebox.showinfo("Success",
                                f"Batch '{batch_id_display}' and its {deleted_samples_count} associated samples deleted successfully.")
            logging.info(f"Batch '{batch_id_display}' and its samples deleted.")

            # Refresh the Treeview to reflect the deletion
            # The current AdminLogic loads batches based on a filter. Reload with the active filter.
            self.load_batches(self.batch_filter_var.get())

            if hasattr(self.app, 'admin_logic'):
                # Ensure admin_logic's load_batches is called if this class is not 'admin_logic' itself
                # (Though it is, this check is redundant here but good for general robustness)
                self.app.admin_logic.load_batches(self.batch_filter_var.get())

            logging.info("Batch data reloaded and tree refreshed after deletion.")

        except Exception as e:
            logging.error(f"Failed to delete batch '{batch_id_display}': {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to delete batch and its samples:\n{e}")

    def export_user_batches(self):
        """Exports approved batches and their associated samples to an Excel file."""
        logging.info("Attempting to export approved batches and samples to Excel.")
        approved_batches_data = []
        batches_ref = db.collection("batches")
        samples_ref = db.collection("samples")

        approved_batches = batches_ref.where("status", "==", "approved").get()

        if not approved_batches:
            messagebox.showwarning("Warning", "No approved batches to export.")
            logging.warning("No approved batches found to export.")
            return

        for batch in approved_batches:
            batch_data = batch.to_dict()
            actual_batch_id_field = batch_data.get("batch_id")

            # Query samples using the 'batch_id' field from the batch document
            associated_samples = samples_ref.where("batch_id", "==", actual_batch_id_field).get()

            # Ensure batch data is always included, even if no samples
            if not associated_samples:
                logging.info(f"Batch {actual_batch_id_field} has no samples. Exporting batch data only.")
                combined_data = {
                    "batch_id": batch_data.get("batch_id", ""),
                    "product_name": batch_data.get("product_name", ""),
                    "batch_description": batch_data.get("description", ""),
                    "batch_status": batch_data.get("status", ""),
                    "user_email": batch_data.get("user_email", ""),
                    "sample_id": "",
                    "sample_owner": "",
                    "sample_maturation_date": "",
                    "sample_status": ""
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
                    mat_date_str = str(sample_mat_date_obj) if sample_mat_date_obj is not None else ''

                combined_data = {
                    "batch_id": batch_data.get("batch_id", ""),
                    "product_name": batch_data.get("product_name", ""),
                    "batch_description": batch_data.get("description", ""),
                    "batch_status": batch_data.get("status", ""),
                    "user_email": batch_data.get("user_email", ""),
                    "sample_id": sample_data.get("sample_id", ""),
                    "sample_owner": sample_data.get("owner", ""),
                    "sample_maturation_date": mat_date_str,
                    "sample_status": sample_data.get("status", "")
                }
                approved_batches_data.append(combined_data)

        if not approved_batches_data:
            messagebox.showwarning("Warning", "No approved batches with data to export.")
            logging.warning("No data collected for approved batches, nothing to export.")
            return

        df_approved_with_samples = pd.DataFrame(approved_batches_data)

        filetypes = (("Excel files", "*.xlsx"),)
        filename = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                                filetypes=filetypes,
                                                initialfile="Approved_Batches_and_Samples.xlsx")
        if filename:
            try:
                for col in df_approved_with_samples.columns:
                    if pd.api.types.is_datetime64_any_dtype(df_approved_with_samples[col]):
                        if df_approved_with_samples[col].dt.tz is not None:
                            df_approved_with_samples[col] = df_approved_with_samples[col].dt.tz_localize(None)

                df_approved_with_samples.to_excel(filename, index=False)
                messagebox.showinfo("Success",
                                    f"Approved batches and their samples exported to {os.path.basename(filename)}")
                logging.info(f"Successfully exported approved batches and samples to {filename}.")
            except Exception as e:
                logging.error(f"Failed to export Excel file for approved batches: {e}", exc_info=True)
                messagebox.showerror("Error", f"Failed to export Excel file:\n{e}")
