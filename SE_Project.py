import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
from datetime import datetime, timedelta
import barcode
from barcode.writer import ImageWriter
import os

# Constants
NOTIFICATION_DAYS_BEFORE = 60  # 2 months approx.

USERS = {
    "admin": {"password": "admin123", "role": "Admin"},
    "owner": {"password": "owner123", "role": "ProductOwner"},
    "bob": {"password": "bob123", "role": "ProductOwner"}
}

COLUMNS = ["SampleID", "Owner", "MaturationDate", "Status"]

# --- Login Window ---
class LoginScreen:
    def __init__(self, root, on_login):
        self.root = root
        self.on_login = on_login
        self.root.title("Login - Shelf-life Study System")
        self.root.geometry("320x180")
        self.root.resizable(False, False)

        # Create and place username label and entry
        tk.Label(root, text="Username:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.username_entry = tk.Entry(root)
        self.username_entry.grid(row=0, column=1, padx=10, pady=10)

        # Create and place password label and entry
        tk.Label(root, text="Password:").grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.password_entry = tk.Entry(root, show="*")
        self.password_entry.grid(row=1, column=1, padx=10, pady=10)

        # Create and place login button
        tk.Button(root, text="Login", width=10, command=self.login).grid(row=2, column=1, pady=10, sticky="e")

        # Label to show login status (e.g., error messages)
        self.status_label = tk.Label(root, text="", fg="red")
        self.status_label.grid(row=3, column=0, columnspan=2)

        def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        # Check if username or password is empty
        if not username and not password:
            self.status_label.config(text="Please enter username and password.")
            return
        elif username and not password:
            self.status_label.config(text="Please enter your password.")
            return
        elif not username and password:
            self.status_label.config(text="Please enter your username.")
            return

        user = USERS.get(username)

        if user:
            if user["password"] == password:
                self.on_login(username, user["role"])
            else:
                self.status_label.config(text="Incorrect password. Please try again.")
        else:
            self.status_label.config(text="Invalid username or password.")

# --- Main Application ---
class ShelfLifeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Shelf-life Study Management System")
        self.root.geometry("800x600")

        self.data = pd.DataFrame()
        self.file_path = ""

        # Setup UI
        self.setup_ui()

    def setup_ui(self):
        # === Menu Bar ===
        menubar = tk.Menu(self.root)

        # File Menu
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Import Excel", command=self.import_excel)
        filemenu.add_command(label="Export Excel", command=self.export_excel)
        filemenu.add_separator()
        filemenu.add_command(label="Logout", command=self.logout)
        menubar.add_cascade(label="File", menu=filemenu)

        # Reports Menu
        # reportmenu = tk.Menu(menubar, tearoff=0)
        # reportmenu.add_command(label="Audit Log", command=self.show_audit_log)
        # reportmenu.add_command(label="Summary Report", command=self.show_summary_report)
        # menubar.add_cascade(label="Reports", menu=reportmenu)

        self.root.config(menu=menubar)

        # === Toolbar Frame for Buttons ===
        toolbar = tk.Frame(self.root)
        toolbar.pack(pady=10)

        tk.Button(toolbar, text="Generate Barcode", command=self.generate_barcode).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Check Notifications", command=self.check_notifications).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Add Sample", command=self.add_sample).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Edit Sample", command=self.edit_sample).pack(side=tk.LEFT, padx=5)
        tk.Button(toolbar, text="Delete Sample", command=self.delete_sample).pack(side=tk.LEFT, padx=5)

        # === Treeview for Data Display ===
        self.tree = ttk.Treeview(self.root, columns=("SampleID", "Owner", "MaturationDate", "Status"), show='headings')
        self.tree.heading("SampleID", text="Sample ID")
        self.tree.heading("Owner", text="Sample Owner")
        self.tree.heading("MaturationDate", text="Maturation Date")
        self.tree.heading("Status", text="Status")
        self.tree.pack(expand=True, fill=tk.BOTH, pady=10)

        # === Status Bar ===
        self.status_label = tk.Label(self.root, text="Load a file to get started.", anchor='w')
        self.status_label.pack(fill=tk.X, padx=10, pady=5)

    def import_excel(self):
        filetypes = (("Excel files", "*.xlsx *.xls"), ("All files", "*.*"))
        filename = filedialog.askopenfilename(title="Open Excel file", filetypes=filetypes)
        if filename:
            try:
                self.data = pd.read_excel(filename)
                self.file_path = filename
                self.refresh_tree()
                self.status_label.config(text=f"Loaded data from {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load Excel file:\n{e}")

    def export_excel(self):
        if self.data.empty:
            messagebox.showwarning("Warning", "No data to export.")
            return
        filetypes = (("Excel files", "*.xlsx"),)
        filename = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=filetypes)
        if filename:
            try:
                self.data.to_excel(filename, index=False)
                self.status_label.config(text=f"Data exported to {os.path.basename(filename)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export Excel file:\n{e}")

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for _, row in self.data.iterrows():
            # Expect columns: SampleID, Owner, MaturationDate
            mat_date = row['MaturationDate']
            if isinstance(mat_date, pd.Timestamp):
                mat_date = mat_date.strftime("%Y-%m-%d")
            self.tree.insert("", tk.END, values=(row['SampleID'], row['Owner'], mat_date, row['Status']))

    def generate_barcode(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample from the list.")
            return
        item = self.tree.item(selected[0])
        sample_id = item['values'][0]

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
        if self.data.empty:
            messagebox.showwarning("Warning", "No data loaded.")
            return

        today = datetime.now()
        notifications = []

        for _, row in self.data.iterrows():
            mat_date = row['MaturationDate']
            if not pd.isnull(mat_date):
                if isinstance(mat_date, pd.Timestamp):
                    mat_date = mat_date.to_pydatetime()
                delta = mat_date - today
                if 0 <= delta.days <= NOTIFICATION_DAYS_BEFORE:
                    notifications.append(f"Sample {row['SampleID']} owned by {row['Owner']} matures on {mat_date.strftime('%Y-%m-%d')}")

        if notifications:
            messagebox.showinfo("Notifications", "\n".join(notifications))
        else:
            messagebox.showinfo("Notifications", "No samples maturing within 2 months.")

    def add_sample(self):
        if self.data.empty:
            messagebox.showwarning("Warning", "Please import data before adding samples.")
            return

        form = tk.Toplevel(self.root)
        form.title("Add New Sample")
        form.geometry("300x200")

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

            if sample_id in self.data['SampleID'].values:
                messagebox.showerror("Error", "Sample ID already exists.")
                return

            new_row = {'SampleID': sample_id, 'Owner': owner, 'MaturationDate': mat_date}
            self.data = pd.concat([self.data, pd.DataFrame([new_row])], ignore_index=True)
            self.refresh_tree()

            # Auto-save to original Excel file
            if self.file_path:
                try:
                    self.data.to_excel(self.file_path, index=False)
                    self.status_label.config(text=f"Added sample {sample_id} and saved to {os.path.basename(self.file_path)}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save Excel file:\n{e}")
            else:
                self.status_label.config(text=f"Added sample {sample_id}. No original file to save.")

            form.destroy()

        tk.Button(form, text="Add", command=submit).pack(pady=10)

    def delete_sample(self):
        if self.data.empty:
            messagebox.showwarning("Warning", "Please import data before deleting samples.")
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample to delete.")
            return

        item = self.tree.item(selected[0])
        sample_id = item['values'][0]

        confirm = messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete sample {sample_id}?")
        if confirm:
            self.data = self.data[self.data['SampleID'] != sample_id].reset_index(drop=True)
            self.refresh_tree()

            # Auto-save to original Excel file
            if self.file_path:
                try:
                    self.data.to_excel(self.file_path, index=False)
                    self.status_label.config(text=f"Deleted sample {sample_id} and saved to {os.path.basename(self.file_path)}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save Excel file:\n{e}")
            else:
                self.status_label.config(text=f"Deleted sample {sample_id}. No original file to save.")

    def edit_sample(self):
        if self.data.empty:
            messagebox.showwarning("Warning", "Please import data before editing samples.")
            return

        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Info", "Please select a sample to edit.")
            return

        item = self.tree.item(selected[0])
        sample_id = item['values'][0]

        idx = self.data.index[self.data['SampleID'] == sample_id][0]
        row = self.data.loc[idx]

        form = tk.Toplevel(self.root)
        form.title(f"Edit Sample {sample_id}")
        form.geometry("300x200")

        tk.Label(form, text="Sample ID:").pack(pady=5)
        entry_sample_id = tk.Entry(form)
        entry_sample_id.insert(0, row['SampleID'])
        entry_sample_id.config(state='disabled')
        entry_sample_id.pack()

        tk.Label(form, text="Sample Owner:").pack(pady=5)
        entry_owner = tk.Entry(form)
        entry_owner.insert(0, row['Owner'])
        entry_owner.pack()

        tk.Label(form, text="Maturation Date (YYYY-MM-DD):").pack(pady=5)
        entry_date = tk.Entry(form)
        if isinstance(row['MaturationDate'], pd.Timestamp):
            entry_date.insert(0, row['MaturationDate'].strftime('%Y-%m-%d'))
        else:
            entry_date.insert(0, str(row['MaturationDate']))
        entry_date.pack()

        def submit():
            owner = entry_owner.get().strip()
            date_str = entry_date.get().strip()

            if not owner or not date_str:
                messagebox.showerror("Error", "All fields are required.")
                return
            try:
                mat_date = pd.to_datetime(date_str)
            except Exception:
                messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")
                return

            confirm = messagebox.askyesno("Confirm Edit", f"Are you sure you want to save changes to sample '{sample_id}'?")
            if not confirm:
                return

            self.data.at[idx, 'Owner'] = owner
            self.data.at[idx, 'MaturationDate'] = mat_date
            self.refresh_tree()

            # Auto-save to original Excel file
            if self.file_path:
                try:
                    self.data.to_excel(self.file_path, index=False)
                    self.status_label.config(text=f"Updated sample {sample_id} and saved to {os.path.basename(self.file_path)}")
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save Excel file:\n{e}")
            else:
                self.status_label.config(text=f"Updated sample {sample_id}. No original file to save.")

            form.destroy()

        tk.Button(form, text="Save", command=submit).pack(pady=10)

    def logout(self):
        if messagebox.askyesno("Confirm Logout", "Are you sure you want to log out?"):
            self.root.destroy()
            main()  # re-open the login screen


def main():
    login_root = tk.Tk()
    def on_login(username, role):
        login_root.destroy()
        app_root = tk.Tk()
        app = ShelfLifeApp(app_root)
        app_root.mainloop()

    login_screen = LoginScreen(login_root, on_login)
    login_root.mainloop()

if __name__ == "__main__":
    main()
