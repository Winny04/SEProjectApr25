# main_app.py
import tkinter as tk
from tkinter import ttk, messagebox

# Import modules
from firebase_setup import db
from auth_manager import AuthManager
from user_logic import UserLogic
from admin_logic import AdminLogic
from tester_logic import TesterLogic
from constants import MIN_PASSWORD_LENGTH  # Just for style mapping, not direct use in logic here


class ShelfLifeApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Shelf-life Study Management System")
        self.root.geometry("800x600")

        self.data = None  # This will hold the DataFrame, managed by UserLogic
        self.file_path = ""  # Managed by UserLogic

        self.current_user = None  # Stores authenticated user's data

        # Initialize the logic modules, passing self (the main app instance) for callbacks
        self.auth_manager = AuthManager(self.root, self)
        self.user_logic = UserLogic(self.root, self)
        self.admin_logic = AdminLogic(self.root, self)
        self.tester_logic = TesterLogic(self.root, self)

        self.login_screen()

    def clear_root(self):
        """Clears all widgets from the main window."""
        for widget in self.root.winfo_children():
            widget.destroy()

    def login_screen(self):
        """Displays the login screen by delegating to AuthManager."""
        self.auth_manager.login_screen()

    def admin_dashboard(self):
        """Displays the admin dashboard by delegating to AdminLogic."""
        self.admin_logic.admin_dashboard()

    def user_dashboard(self):
        """Displays the user dashboard by delegating to UserLogic."""
        self.user_logic.user_dashboard()

    def test_dashboard(self):
        self.tester_logic.tester_dashboard()

    def logout(self):
        """Logs out the current user and returns to the login screen."""
        confirm = messagebox.askyesno("Logout", "Are you sure you want to logout?")
        if confirm:
            self.current_user = None
            self.login_screen()


if __name__ == "__main__":
    root = tk.Tk()

    # Apply a modern theme
    style = ttk.Style(root)
    style.theme_use('clam')  # 'clam', 'alt', 'default', 'classic'
    # Define an accent button style
    style.configure('Accent.TButton', background='#4CAF50', foreground='white', font=('Helvetica', 10, 'bold'))
    style.map('Accent.TButton',
              background=[('active', '#45a049'), ('pressed', '#367c39')],
              foreground=[('active', 'white'), ('pressed', 'white')])

    app = ShelfLifeApp(root)
    root.mainloop()
    