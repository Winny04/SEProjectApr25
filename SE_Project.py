import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import pandas as pd
from datetime import datetime, timedelta
import barcode
from barcode.writer import ImageWriter
import os

# Constants
NOTIFICATION_DAYS_BEFORE = 60  # 2 months approx.

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
        # Frame for buttons
        frame_btn = tk.Frame(self.root)
        frame_btn.pack(pady=10)

        tk.Button(frame_btn, text="Import Excel", command=self.import_excel).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Export Excel", command=self.export_excel).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Generate Barcode", command=self.generate_barcode).pack(side=tk.LEFT, padx=5)
        tk.Button(frame_btn, text="Check Notifications", command=self.check_notifications).pack(side=tk.LEFT, padx=5)

        # Treeview for data display
        self.tree = ttk.Treeview(self.root, columns=("SampleID", "Owner", "MaturationDate"), show='headings')
        self.tree.heading("SampleID", text="Sample ID")
        self.tree.heading("Owner", text="Sample Owner")
        self.tree.heading("MaturationDate", text="Maturation Date")
        self.tree.pack(expand=True, fill=tk.BOTH, pady=10)

        # Status Label
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
            self.tree.insert("", tk.END, values=(row['SampleID'], row['Owner'], mat_date))

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

if __name__ == "__main__":
    root = tk.Tk()
    app = ShelfLifeApp(root)
    root.mainloop()
