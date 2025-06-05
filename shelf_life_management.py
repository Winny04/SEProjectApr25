# shelf_life_combined.py
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import barcode
from barcode.writer import ImageWriter

# --- Configuration ---
DATA_FILE = "samples_data.xlsx"
NOTIFICATION_DAYS = 60
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
        self.root.geometry("300x180")

        tk.Label(root, text="Username:").pack(pady=5)
        self.username_entry = tk.Entry(root)
        self.username_entry.pack()

        tk.Label(root, text="Password:").pack(pady=5)
        self.password_entry = tk.Entry(root, show="*")
        self.password_entry.pack()

        tk.Button(root, text="Login", command=self.login).pack(pady=10)
        self.status_label = tk.Label(root, text="", fg="red")
        self.status_label.pack()

    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        user = USERS.get(username)
        if user and user["password"] == password:
            self.on_login(username, user["role"])
        else:
            self.status_label.config(text="Invalid username or password.")

# --- Main Application ---
class ShelfLifeApp:
    def __init__(self, root, username, role):
        self.root = root
        self.username = username
        self.role = role
        self.data = self.load_data()
        self.audit_log = []

        self.root.title(f"Shelf-life Study System - {username} ({role})")
        self.root.geometry("950x600")
        self.setup_menu()
        self.setup_dashboard()
        self.setup_treeview()
        self.setup_buttons()
        self.refresh_tree()

    def setup_menu(self):
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Import Excel", command=self.import_excel)
        filemenu.add_command(label="Export Excel", command=self.export_excel)
        filemenu.add_separator()
        filemenu.add_command(label="Logout", command=self.logout)
        menubar.add_cascade(label="File", menu=filemenu)
        menubar.add_command(label="Audit Log", command=self.show_audit_log)
        menubar.add_command(label="Summary Report", command=self.show_summary_report)
        self.root.config(menu=menubar)

    def setup_dashboard(self):
        frame = tk.Frame(self.root)
        frame.pack(fill=tk.X, pady=5)
        self.total_var = tk.StringVar()
        self.expiring_var = tk.StringVar()
        tk.Label(frame, textvariable=self.total_var, font=("Arial", 12)).pack(side=tk.LEFT, padx=10)
        tk.Label(frame, textvariable=self.expiring_var, font=("Arial", 12)).pack(side=tk.LEFT, padx=10)

    def setup_treeview(self):
        self.tree = ttk.Treeview(self.root, columns=COLUMNS, show="headings")
        for col in COLUMNS:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=140)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.tag_configure("Pending", background="#e0e0e0")
        self.tree.tag_configure("Expired", background="#ffcccc")
        self.tree.tag_configure("Expiring", background="#ffe0b2")
        self.tree.tag_configure("Active", background="#ccffcc")

    def setup_buttons(self):
        frame = tk.Frame(self.root)
        frame.pack(pady=5)
        tk.Button(frame, text="Add Sample", command=self.add_sample).pack(side=tk.LEFT, padx=5)
        if self.role == "Admin":
            tk.Button(frame, text="Edit Sample", command=self.edit_sample).pack(side=tk.LEFT, padx=5)
            tk.Button(frame, text="Delete Sample", command=self.delete_sample).pack(side=tk.LEFT, padx=5)
            tk.Button(frame, text="Approve Sample", command=self.approve_sample).pack(side=tk.LEFT, padx=5)
        tk.Button(frame, text="Generate Barcode", command=self.generate_barcode).pack(side=tk.LEFT, padx=5)
        tk.Button(frame, text="Check Notifications", command=self.check_notifications).pack(side=tk.LEFT, padx=5)

    def get_updated_status(self, maturation_date):
        today = datetime.now()
        if pd.isna(maturation_date):
            return "Pending"
        days_diff = (maturation_date - today).days
        if days_diff < 0:
            return "Expired"
        elif days_diff <= NOTIFICATION_DAYS:
            return "Expiring"
        else:
            return "Active"

    def refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        today = datetime.now()
        expiring = 0

        for idx, row in self.data.iterrows():
            status = row["Status"]
            maturation_date = row["MaturationDate"]

            # Auto-update only approved/active/expiring statuses
            if status in ["Approved", "Active", "Expiring"]:
                self.data.at[idx, "Status"] = self.get_updated_status(maturation_date)

            updated_status = self.data.at[idx, "Status"]
            if updated_status == "Expiring":
                expiring += 1

            self.tree.insert("", tk.END, values=(
                row["SampleID"],
                row["Owner"],
                maturation_date.date() if pd.notna(maturation_date) else "",
                updated_status
            ), tags=(updated_status,))

        self.total_var.set(f"Total Samples: {len(self.data)}")
        self.expiring_var.set(f"Expiring Soon: {expiring}")
        self.save_data()  # Persist auto-updated statuses

    def add_sample(self):
        SampleDialog(self.root, self.username, self.role, self.add_sample_callback)

    def add_sample_callback(self, sample_id, date):
        if sample_id in self.data["SampleID"].values:
            messagebox.showerror("Duplicate", "Sample ID already exists.")
            return
        status = "Approved" if self.role == "Admin" else "Pending"
        self.data.loc[len(self.data)] = [sample_id, self.username, date, status]
        self.save_data()
        self.refresh_tree()
        self.log_action(f"Added sample '{sample_id}' [{status}]")
        if status == "Pending":
            messagebox.showinfo("Pending Approval", "Sample is pending Admin approval.")

    def edit_sample(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Edit", "Select a sample to edit.")
            return
        values = self.tree.item(selected[0])["values"]
        SampleDialog(self.root, self.username, self.role, self.edit_sample_callback, sample_id=values[0], date=values[2])

    def edit_sample_callback(self, sample_id, date):
        idx = self.data.index[self.data["SampleID"] == sample_id][0]
        self.data.at[idx, "MaturationDate"] = date
        self.save_data()
        self.refresh_tree()
        self.log_action(f"Edited sample '{sample_id}'")

    def delete_sample(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Delete", "Select a sample to delete.")
            return
        sample_id = self.tree.item(selected[0])["values"][0]
        self.data = self.data[self.data["SampleID"] != sample_id]
        self.save_data()
        self.refresh_tree()
        self.log_action(f"Deleted sample '{sample_id}'")

    def approve_sample(self):
        selected = self.tree.selection()
        if not selected:
            return
        sample_id = self.tree.item(selected[0])["values"][0]
        idx = self.data.index[self.data["SampleID"] == sample_id][0]
        maturation_date = self.data.at[idx, "MaturationDate"]
        new_status = self.get_updated_status(maturation_date)
        self.data.at[idx, "Status"] = new_status
        self.save_data()
        self.refresh_tree()
        self.log_action(f"Approved sample '{sample_id}' → {new_status}")

    def generate_barcode(self):
        selected = self.tree.selection()
        if not selected:
            return
        sample_id = self.tree.item(selected[0])["values"][0]
        ean = barcode.get_barcode_class("code128")(sample_id, writer=ImageWriter())
        filename = filedialog.asksaveasfilename(defaultextension=".png", initialfile=f"{sample_id}_barcode")
        if filename:
            ean.save(filename)
            messagebox.showinfo("Saved", f"Barcode saved to {filename}")

    def check_notifications(self):
        today = datetime.now()
        messages = []
        for _, row in self.data.iterrows():
            days = (row["MaturationDate"] - today).days
            if days < 0:
                messages.append(f"Sample '{row['SampleID']}' has expired.")
            elif days <= NOTIFICATION_DAYS:
                messages.append(f"Sample '{row['SampleID']}' expires soon.")
        if messages:
            messagebox.showinfo("Notifications", "\n".join(messages))
        else:
            messagebox.showinfo("Notifications", "No notifications.")

    def show_audit_log(self):
        if not self.audit_log:
            messagebox.showinfo("Audit", "No log entries.")
            return
        win = tk.Toplevel(self.root)
        win.title("Audit Log")
        text = tk.Text(win)
        text.pack(fill=tk.BOTH, expand=True)
        for entry in self.audit_log:
            text.insert(tk.END, f"{entry['timestamp']} - {entry['user']}: {entry['action']}\n")

    def show_summary_report(self):
        if self.data.empty:
            return
        counts = {
            "Approved": len(self.data[self.data["Status"] == "Active"]),
            "Pending": len(self.data[self.data["Status"] == "Pending"]),
            "Expired": sum((datetime.now() > d for d in self.data["MaturationDate"])),
            "Expiring Soon": sum((0 <= (d - datetime.now()).days <= NOTIFICATION_DAYS for d in self.data["MaturationDate"]))
        }
        fig, ax = plt.subplots()
        ax.pie(counts.values(), labels=counts.keys(), autopct='%1.0f%%')
        ax.axis("equal")
        plt.title("Sample Summary")
        plt.show()

    def load_data(self):
        if not os.path.exists(DATA_FILE):
            return pd.DataFrame(columns=COLUMNS)
        df = pd.read_excel(DATA_FILE)
        df["MaturationDate"] = pd.to_datetime(df["MaturationDate"], errors="coerce")
        return df

    def save_data(self):
        self.data.to_excel(DATA_FILE, index=False)

    def log_action(self, action):
        self.audit_log.append({
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "user": self.username,
            "action": action
        })

    def import_excel(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        if not file_path:
            return
        try:
            df = pd.read_excel(file_path)
            df["MaturationDate"] = pd.to_datetime(df["MaturationDate"], errors="coerce")
            if set(COLUMNS).issubset(df.columns):
                self.data = df[COLUMNS]
                self.save_data()
                self.refresh_tree()
        except Exception as e:
            messagebox.showerror("Import Error", str(e))

    def export_excel(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".xlsx")
        if file_path:
            self.data.to_excel(file_path, index=False)
            messagebox.showinfo("Exported", f"Data exported to {file_path}")

    def logout(self):
        self.root.destroy()
        main()

# --- Sample Dialog ---
class SampleDialog:
    def __init__(self, parent, user, role, callback, sample_id=None, date=None):
        self.top = tk.Toplevel(parent)
        self.top.title("Add Sample" if sample_id is None else "Edit Sample")
        self.callback = callback
        tk.Label(self.top, text="Sample ID:").grid(row=0, column=0)
        self.sample_entry = tk.Entry(self.top)
        self.sample_entry.grid(row=0, column=1)
        if sample_id:
            self.sample_entry.insert(0, sample_id)
            self.sample_entry.config(state="disabled")
        tk.Label(self.top, text="Maturation Date (YYYY-MM-DD):").grid(row=1, column=0)
        self.date_entry = tk.Entry(self.top)
        self.date_entry.grid(row=1, column=1)
        if date:
            self.date_entry.insert(0, date)
        tk.Button(self.top, text="Submit", command=self.submit).grid(row=2, column=0, columnspan=2)

    def submit(self):
        sid = self.sample_entry.get().strip()
        try:
            date = datetime.strptime(self.date_entry.get().strip(), "%Y-%m-%d")
            self.callback(sid, date)
            self.top.destroy()
        except ValueError:
            messagebox.showerror("Error", "Invalid date format. Use YYYY-MM-DD.")

# --- Main Function ---
def main():
    root = tk.Tk()
    LoginScreen(root, lambda u, r: (root.destroy(), launch_main(u, r)))
    root.mainloop()

def launch_main(user, role):
    new_root = tk.Tk()
    ShelfLifeApp(new_root, user, role)
    new_root.mainloop()

if __name__ == "__main__":
    main()
