import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
from datetime import datetime
import barcode
from barcode.writer import ImageWriter
import os

# Constants
NOTIFICATION_DAYS_BEFORE = 60  # 2 months approx.

class ShelfLifeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Shelf-life Study Management System")
        self.root.geometry("900x650")

        self.file_path = ""
        self.pending_data = pd.DataFrame(columns=["SampleID", "Owner", "MaturationDate"])
        self.approved_data = pd.DataFrame(columns=["SampleID", "Owner", "MaturationDate"])

        self.role = None  # "Product Owner" or "Admin"
        self.current_view = "Approved"  # default view for Admin; for Product Owner always Pending

        # UI Elements that need to be accessed outside
        self.tree = None
        self.status_label = None
        self.frame_btn = None
        self.role_label = None
        self.role_var = tk.StringVar()

        self.setup_role_selection_ui()

    def setup_role_selection_ui(self):
        # Clear root
        for widget in self.root.winfo_children():
            widget.destroy()

        tk.Label(self.root, text="Select User Role:", font=("Arial", 16)).pack(pady=20)

        roles = [("Product Owner", "Product Owner"), ("Admin", "Admin")]
        for text, mode in roles:
            tk.Radiobutton(self.root, text=text, variable=self.role_var, value=mode, font=("Arial", 14)).pack(pady=5)

        tk.Button(self.root, text="Confirm Role", font=("Arial", 14), command=self.confirm_role).pack(pady=20)

    def confirm_role(self):
        selected_role = self.role_var.get()
        if selected_role not in ["Product Owner", "Admin"]:
            messagebox.showwarning("Warning", "Please select a role to continue.")
            return
        self.role = selected_role
        self.setup_main_ui()

    def setup_main_ui(self):
        # Clear root for main UI
        for widget in self.root.winfo_children():
            widget.destroy()

        # Role label + File import button
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill=tk.X, pady=5)

        self.role_label = tk.Label(top_frame, text=f"Logged in as: {self.role}", font=("Arial", 12))
        self.role_label.pack(side=tk.LEFT, padx=10)

        tk.Button(top_frame, text="Import Excel", command=self.import_excel).pack(side=tk.RIGHT, padx=10)

        # Frame for buttons based on role
        self.frame_btn = tk.Frame(self.root)
        self.frame_btn.pack(pady=10)

        # Treeview for data display
        self.tree = ttk.Treeview(self.root, columns=("SampleID", "Owner", "MaturationDate"), show='headings')
        self.tree.heading("SampleID", text="Sample ID")
        self.tree.heading("Owner", text="Sample Owner")
        self.tree.heading("MaturationDate", text="Maturation Date")
        self.tree.pack(expand=True, fill=tk.BOTH, pady=10)

        # Status Label
        self.status_label = tk.Label(self.root, text="Please import an Excel file to get started.", anchor='w')
        self.status_label.pack(fill=tk.X, padx=10, pady=5)

        # Setup buttons based on role (initially disabled until file imported)
        self.setup_buttons_by_role()
        self.update_buttons_state(state='disabled')

    def setup_buttons_by_role(self):
        # Clear frame buttons first
        for widget in self.frame_btn.winfo_children():
            widget.destroy()

        if self.role == "Product Owner":
            # Only Add Sample to Pending, View Pending samples
            tk.Button(self.frame_btn, text="Add Sample (Pending)", command=self.add_sample).pack(side=tk.LEFT, padx=5)
            tk.Button(self.frame_btn, text="View Pending Samples", command=self.view_pending).pack(side=tk.LEFT, padx=5)
            tk.Button(self.frame_btn, text="View Approved Samples", command=self.view_approved).pack(side=tk.LEFT, padx=5)
            tk.Button(self.frame_btn, text="Check Notifications (Approved only)", command=self.check_notifications).pack(side=tk.LEFT, padx=5)
            tk.Button(self.frame_btn, text="Generate Barcode (Approved only)", command=self.generate_barcode).pack(side=tk.LEFT, padx=5)

        elif self.role == "Admin":
            # Admin: View Approved, View Pending, Approve, Reject, Edit, Delete on Approved, Generate Barcode
            tk.Button(self.frame_btn, text="View Approved Samples", command=self.view_approved).pack(side=tk.LEFT, padx=5)
            tk.Button(self.frame_btn, text="View Pending Samples", command=self.view_pending).pack(side=tk.LEFT, padx=5)
            tk.Button(self.frame_btn, text="Approve Selected Pending", command=self.approve_sample).pack(side=tk.LEFT, padx=5)
            tk.Button(self.frame_btn, text="Reject Selected Pending", command=self.reject_sample).pack(side=tk.LEFT, padx=5)
            tk.Button(self.frame_btn, text="Edit Approved Sample", command=self.edit_sample).pack(side=tk.LEFT, padx=5)
            tk.Button(self.frame_btn, text="Delete Approved Sample", command=self.delete_sample).pack(side=tk.LEFT, padx=5)
            tk.Button(self.frame_btn, text="Generate Barcode (Approved only)", command=self.generate_barcode).pack(side=tk.LEFT, padx=5)
            tk.Button(self.frame_btn, text="Check Notifications (Approved only)", command=self.check_notifications).pack(side=tk.LEFT, padx=5)

    def update_buttons_state(self, state='normal'):
        # Enable/disable buttons except Import Excel and role label
        for widget in self.frame_btn.winfo_children():
            widget.config(state=state)

    def import_excel(self):
        filetypes = (("Excel files", "*.xlsx *.xls"), ("All files", "*.*"))
        filename = filedialog.askopenfilename(title="Open Excel file", filetypes=filetypes)
        if filename:
            try:
                # Read Pending and Approved sheets if exist
                xls = pd.ExcelFile(filename)
                if "Pending" in xls.sheet_names:
                    self.pending_data = pd.read_excel(xls, sheet_name="Pending")
                    # Ensure columns
                    self.pending_data = self.pending_data[["SampleID", "Owner", "MaturationDate"]]
                else:
                    self.pending_data = pd.DataFrame(columns=["SampleID", "Owner", "MaturationDate"])

                if "Approved" in xls.sheet_names:
                    self.approved_data = pd.read_excel(xls, sheet_name="Approved")
                    self.approved_data = self.approved_data[["SampleID", "Owner", "MaturationDate"]]
                else:
                    self.approved_data = pd.DataFrame(columns=["SampleID", "Owner", "MaturationDate"])

                # Convert MaturationDate to datetime
                for df in [self.pending_data, self.approved_data]:
                    if not df.empty:
                        df["MaturationDate"] = pd.to_datetime(df["MaturationDate"], errors='coerce')

                self.file_path = filename
                self.status_label.config(text=f"Loaded data from {os.path.basename(filename)}")

                # Show default view:
                if self.role == "Product Owner":
                    self.current_view = "Pending"
                    self.view_pending()
                elif self.role == "Admin":
                    self.current_view = "Approved"
                    self.view_approved()

                self.update_buttons_state(state='normal')

            except Exception as e:
                messagebox.showerror("Error", f"Failed to load Excel file:\n{e}")

    def save_to_excel(self):
        # Save pending and approved sheets back to Excel file
        if not self.file_path:
            messagebox.showwarning("Warning", "No Excel file loaded to save data.")
            return
        try:
            with pd.ExcelWriter(self.file_path, engine='openpyxl', mode='w') as writer:
                self.pending_data.to_excel(writer, sheet_name="Pending", index=False)
                self.approved_data.to_excel(writer, sheet_name="Approved", index=False)
            self.status_label.config(text=f"Data saved to {os.path.basename(self.file_path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save Excel file:\n{e}")

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        data = self.pending_data if self.current_view == "Pending" else self.approved_data
        for _, row in data.iterrows():
            mat_date = row['MaturationDate']
            if pd.isnull(mat_date):
                mat_date_str = ""
            elif isinstance(mat_date, pd.Timestamp):
                mat_date_str = mat_date.strftime("%Y-%m-%d")
            else:
                mat_date_str = str(mat_date)
            self.tree.insert("", tk.END, values=(row['SampleID'], row['Owner'], mat_date_str))

        self.status_label.config(text=f"Viewing {self.current_view} samples. Total: {len(data)}")

    def view_pending(self):
        self.current_view = "Pending"
        self.refresh_tree()

    def view_approved(self):
        self.current_view = "Approved"
        self.refresh_tree()

    def add_sample(self):
        if not self.file_path:
            messagebox.showwarning("Warning", "Please import data before adding samples.")
            return

        # Product Owner can only add to Pending
        if self.role != "Product Owner":
            messagebox.showinfo("Info", "Only Product Owners can add new samples.")
            return

        form = tk.Toplevel(self.root)
        form.title("Add New Sample (Pending)")
        form.geometry("320x220")

        tk.Label(form, text="Sample ID:").pack(pady=5)
        entry_sample_id = tk.Entry(form)
        entry_sample_id.pack()

        tk.Label(form, text="Sample Owner:").pack(pady=5)
        entry_owner = tk.Entry(form)
        entry_owner.pack()

        tk.Label(form, text="Maturation Date (YYYY-MM-DD):").pack(pady=5)
        entry_date = tk.Entry(form)
        entry_date.pack()

        def submit():
            sample_id = entry_sample_id.get().strip()
            owner = entry_owner.get().strip()
            date_str = entry_date.get().strip()

            if not sample_id or not owner or not date_str:
                messagebox.showerror("Error", "All fields are required.")
                return
            try:
                mat_date = pd.to_datetime(date_str)
            except Exception:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
                return

            # Check if sample_id exists in either pending or approved
            if sample_id in self.pending_data['SampleID'].values or sample_id in self.approved_data['SampleID'].values:
                messagebox.showerror("Error", "Sample ID already exists in system.")
                return

            new_row = {'SampleID': sample_id, 'Owner': owner, 'MaturationDate': mat_date}
            self.pending_data = pd.concat([self.pending_data, pd.DataFrame([new_row])], ignore_index=True)
            self.refresh_tree()

            self.save_to_excel()
            self.status_label.config(text=f"Sample '{sample_id}' added to Pending.")
            form.destroy()

        tk.Button(form, text="Submit", command=submit).pack(pady=10)

    def get_selected_sample(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a sample from the table.")
            return None
        sample = self.tree.item(selected[0])['values']
        # sample: [SampleID, Owner, MaturationDate]
        return sample

    def approve_sample(self):
        if self.role != "Admin":
            messagebox.showinfo("Info", "Only Admin can approve samples.")
            return
        if self.current_view != "Pending":
            messagebox.showinfo("Info", "Switch to Pending samples view to approve.")
            return

        sample = self.get_selected_sample()
        if not sample:
            return

        sample_id = sample[0]
        idx = self.pending_data.index[self.pending_data['SampleID'] == sample_id].tolist()
        if not idx:
            messagebox.showerror("Error", "Selected sample not found in Pending data.")
            return
        idx = idx[0]

        # Move sample from pending to approved
        sample_row = self.pending_data.loc[idx]
        self.approved_data = pd.concat([self.approved_data, pd.DataFrame([sample_row])], ignore_index=True)
        self.pending_data = self.pending_data.drop(idx).reset_index(drop=True)

        self.save_to_excel()
        self.refresh_tree()
        self.status_label.config(text=f"Sample '{sample_id}' approved.")

    def reject_sample(self):
        if self.role != "Admin":
            messagebox.showinfo("Info", "Only Admin can reject samples.")
            return
        if self.current_view != "Pending":
            messagebox.showinfo("Info", "Switch to Pending samples view to reject.")
            return

        sample = self.get_selected_sample()
        if not sample:
            return

        sample_id = sample[0]
        idx = self.pending_data.index[self.pending_data['SampleID'] == sample_id].tolist()
        if not idx:
            messagebox.showerror("Error", "Selected sample not found in Pending data.")
            return
        idx = idx[0]

        # Remove sample from pending
        confirm = messagebox.askyesno("Confirm", f"Reject sample '{sample_id}'? It will be removed from Pending.")
        if confirm:
            self.pending_data = self.pending_data.drop(idx).reset_index(drop=True)
            self.save_to_excel()
            self.refresh_tree()
            self.status_label.config(text=f"Sample '{sample_id}' rejected and removed from Pending.")

    def edit_sample(self):
        if self.role != "Admin":
            messagebox.showinfo("Info", "Only Admin can edit samples.")
            return
        if self.current_view != "Approved":
            messagebox.showinfo("Info", "Switch to Approved samples view to edit.")
            return

        sample = self.get_selected_sample()
        if not sample:
            return

        sample_id = sample[0]
        idx = self.approved_data.index[self.approved_data['SampleID'] == sample_id].tolist()
        if not idx:
            messagebox.showerror("Error", "Selected sample not found in Approved data.")
            return
        idx = idx[0]

        form = tk.Toplevel(self.root)
        form.title(f"Edit Sample '{sample_id}'")
        form.geometry("320x220")

        tk.Label(form, text="Sample ID (cannot edit):").pack(pady=5)
        tk.Label(form, text=sample_id).pack()

        tk.Label(form, text="Sample Owner:").pack(pady=5)
        entry_owner = tk.Entry(form)
        entry_owner.insert(0, self.approved_data.at[idx, 'Owner'])
        entry_owner.pack()

        tk.Label(form, text="Maturation Date (YYYY-MM-DD):").pack(pady=5)
        mat_date = self.approved_data.at[idx, 'MaturationDate']
        date_str = mat_date.strftime("%Y-%m-%d") if not pd.isnull(mat_date) else ""
        entry_date = tk.Entry(form)
        entry_date.insert(0, date_str)
        entry_date.pack()

        def submit_edit():
            owner = entry_owner.get().strip()
            date_str = entry_date.get().strip()

            if not owner or not date_str:
                messagebox.showerror("Error", "All fields are required.")
                return
            try:
                mat_date_new = pd.to_datetime(date_str)
            except Exception:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
                return

            self.approved_data.at[idx, 'Owner'] = owner
            self.approved_data.at[idx, 'MaturationDate'] = mat_date_new
            self.save_to_excel()
            self.refresh_tree()
            self.status_label.config(text=f"Sample '{sample_id}' updated.")
            form.destroy()

        tk.Button(form, text="Submit", command=submit_edit).pack(pady=10)

    def delete_sample(self):
        if self.role != "Admin":
            messagebox.showinfo("Info", "Only Admin can delete samples.")
            return
        if self.current_view != "Approved":
            messagebox.showinfo("Info", "Switch to Approved samples view to delete.")
            return

        sample = self.get_selected_sample()
        if not sample:
            return

        sample_id = sample[0]
        confirm = messagebox.askyesno("Confirm", f"Are you sure to delete sample '{sample_id}'?")
        if confirm:
            idx = self.approved_data.index[self.approved_data['SampleID'] == sample_id].tolist()
            if idx:
                idx = idx[0]
                self.approved_data = self.approved_data.drop(idx).reset_index(drop=True)
                self.save_to_excel()
                self.refresh_tree()
                self.status_label.config(text=f"Sample '{sample_id}' deleted.")

    def generate_barcode(self):
        if self.current_view != "Approved":
            messagebox.showinfo("Info", "Barcode generation only allowed for Approved samples view.")
            return

        sample = self.get_selected_sample()
        if not sample:
            return

        sample_id = sample[0]

        # Generate barcode for the Sample ID
        try:
            EAN = barcode.get_barcode_class('code128')
            ean = EAN(sample_id, writer=ImageWriter())
            filename = f"{sample_id}_barcode"
            saved_path = ean.save(filename)
            messagebox.showinfo("Barcode Generated", f"Barcode image saved as:\n{saved_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate barcode:\n{e}")

    def check_notifications(self):
        if self.current_view != "Approved":
            messagebox.showinfo("Info", "Notifications only checked for Approved samples view.")
            return

        today = datetime.now()
        notify_list = []

        for _, row in self.approved_data.iterrows():
            mat_date = row['MaturationDate']
            if pd.isnull(mat_date):
                continue
            days_left = (mat_date - today).days
            if 0 <= days_left <= NOTIFICATION_DAYS_BEFORE:
                notify_list.append(f"SampleID: {row['SampleID']}, Owner: {row['Owner']}, Maturation in {days_left} days")

        if notify_list:
            msg = "Samples nearing maturation (within 2 months):\n\n" + "\n".join(notify_list)
            messagebox.showinfo("Notifications", msg)
        else:
            messagebox.showinfo("Notifications", "No samples nearing maturation within 2 months.")

def main():
    root = tk.Tk()
    app = ShelfLifeApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()

