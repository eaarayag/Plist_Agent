import json
import getpass
import os
import re
from pathlib import Path
import tkinter as tk
from tkinter import messagebox


class User_Manager:
    def __init__(self, app):
        self.app = app

    def _project_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def _users_config_path(self) -> Path:
        return self._project_root() / "config" / "users_config.json"

    def _ensure_config_dir(self) -> None:
        self._users_config_path().parent.mkdir(parents=True, exist_ok=True)

    def Windows_path_validator(self, path):  # P0
        return bool(re.match(r"^[a-zA-Z]:\\", path)) and os.path.isabs(path)

    def Create_default_user_json(self):  # P0
        current_user = getpass.getuser()
        default_data = {
            "favorites": {
                current_user: {"Username": "Guest (Default)", "Project": "CWF", "Die": "Top Die"}
            },
            "users": {
                "Guest (Default)": {
                    "PListDebugFolder": "NA",
                    "BundleFolder": "NA",
                    "Project": "CWF",
                    "Die": "Top Die",
                }
            },
            "definitions": {"Projects": ["CWF"], "Dies": {"CWF": ["Top Die", "Base Die"]}},
        }

        self._ensure_config_dir()
        config_path = self._users_config_path()

        # Backward compatibility: if a legacy config exists at repo root, migrate it.
        legacy_path = self._project_root() / "users_config.json"
        if not config_path.exists() and legacy_path.exists():
            try:
                config_path.write_text(legacy_path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                # Fall back to creating defaults below.
                pass

        if not config_path.exists():
            with config_path.open("w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=4)
            print(f"'{config_path.as_posix()}' file created with default values")

    def Load_users_from_json(self):  # P0
        self.Create_default_user_json()
        current_user = getpass.getuser()

        config_path = self._users_config_path()

        try:
            with config_path.open("r", encoding="utf-8") as f:
                self.app.user_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.app.user_data = {}

        usernames = list(self.app.user_data.get("users", {}).keys())
        self.app.user_list["values"] = usernames

        favorite_entry = self.app.user_data.get("favorites", {}).get(current_user, {})
        if isinstance(favorite_entry, str):
            favorite_username = favorite_entry
            self.app.favorite_project = "NA"
            self.app.favorite_die = "NA"
        else:
            favorite_username = favorite_entry.get("Username", "Guest (Default)")
            self.app.favorite_project = favorite_entry.get("Project", "NA")
            self.app.favorite_die = favorite_entry.get("Die", "NA")

        self.app.user_list.set(favorite_username)

        self.app.current_user = current_user
        self.app.current_username = favorite_username
        self.app.current_user_config = self.app.user_data.get("users", {}).get(favorite_username, {})

        self.app.available_projects = self.app.user_data.get("definitions", {}).get("Projects", ["NA"])
        dies_by_project = self.app.user_data.get("definitions", {}).get("Dies", {})
        self.app.available_dies = dies_by_project.get(self.app.favorite_project, ["NA"])

    def Add_new_user_P0(self):  # P0
        popup = self.app.Create_user_window_popup("Add New User")

        form_frame = tk.Frame(popup, bg="lightgray")
        form_frame.pack(pady=(20, 10), padx=20, fill="x")

        current_user = getpass.getuser()

        username_entry = self.app.Create_user_window_label_entrys(form_frame, "Username:", initial_value=current_user)

        plist_folder_entry = self.app.Create_user_window_label_entrys(
            form_frame, "Folder for PList Debug:", "", "Must be Windows Full File Path Format"
        )

        bundle_folder_entry = self.app.Create_user_window_label_entrys(
            form_frame, "Folder for Bundle:", "", "Must be Windows Full File Path Format"
        )

        project_var = tk.StringVar(value=self.app.available_projects[0] if self.app.available_projects else "NA")
        self.app.Create_user_window_dropdown(form_frame, "Project: (Most Used)", project_var, self.app.available_projects)

        die_var = tk.StringVar(value=self.app.available_dies[0] if self.app.available_dies else "NA")
        self.app.Create_user_window_dropdown(form_frame, "Die (Most Used)", die_var, self.app.available_dies)

        def save_user():
            username = username_entry.get().strip()
            plist_folder = plist_folder_entry.get().strip()
            bundle_folder = bundle_folder_entry.get().strip()
            project = project_var.get()
            die = die_var.get()

            errors = []
            if not username:
                errors.append("Username is required.")
            if not self.Windows_path_validator(plist_folder):
                errors.append("PList Debug folder must be a valid Windows path (e.g., C:\\Folder).")
            if not self.Windows_path_validator(bundle_folder):
                errors.append("Bundle folder must be a valid Windows path (e.g., C:\\Folder).")

            if errors:
                messagebox.showerror("Error", "\n".join(errors))
                return

            try:
                with self._users_config_path().open("r", encoding="utf-8") as f:
                    self.app.user_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                self.app.user_data = {"favorites": {}, "users": {}}

            if username in self.app.user_data.get("users", {}):
                messagebox.showerror("Error", f"User '{username}' already exists.")
                return

            self.app.user_data["users"][username] = {
                "PListDebugFolder": plist_folder,
                "BundleFolder": bundle_folder,
                "Project": project,
                "Die": die,
            }

            self.app.user_data["favorites"][current_user] = {"Username": username, "Project": project, "Die": die}

            with self._users_config_path().open("w", encoding="utf-8") as f:
                json.dump(self.app.user_data, f, indent=4)

            self.Load_users_from_json()
            self.app.Load_user_info_for_bundle_section_P6(self.app.User_info_frame_P6)
            popup.destroy()

        self.app.Create_user_window_save_button(popup, save_user)

    def Edit_existing_user_P0(self):  # P0
        selected_username = self.app.user_list.get()
        if not selected_username:
            messagebox.showerror("Error", "Please select a user to edit.")
            return

        try:
            user_data = self.app.user_data.get("users", {}).get(selected_username)
            if not user_data:
                messagebox.showerror("Error", f"No data found for user '{selected_username}'.")
                return
        except AttributeError:
            messagebox.showerror("Error", "User data is not loaded. Please reload users.")
            return

        popup = self.app.Create_user_window_popup(f"Edit User: {selected_username}")

        form_frame = tk.Frame(popup, bg="lightgray")
        form_frame.pack(pady=20, padx=20, fill="x")

        plist_folder_entry = self.app.Create_user_window_label_entrys(
            form_frame,
            "Folder for PList Debug:",
            user_data.get("PListDebugFolder", ""),
            "Must be Windows Path Format",
        )

        bundle_folder_entry = self.app.Create_user_window_label_entrys(
            form_frame,
            "Folder for Bundle:",
            user_data.get("BundleFolder", ""),
            "Must be Windows Path Format",
        )

        project_var = tk.StringVar(
            value=user_data.get(
                "Project", self.app.available_projects[0] if self.app.available_projects else "NA"
            )
        )
        self.app.Create_user_window_dropdown(form_frame, "Project: (Most Used)", project_var, self.app.available_projects)

        die_var = tk.StringVar(value=user_data.get("Die", self.app.available_dies[0] if self.app.available_dies else "NA"))
        self.app.Create_user_window_dropdown(form_frame, "Die (Most Used)", die_var, self.app.available_dies)

        def edit_user_save_changes():
            plist_folder = plist_folder_entry.get().strip()
            bundle_folder = bundle_folder_entry.get().strip()
            project = project_var.get()
            die = die_var.get()

            errors = []
            if not self.Windows_path_validator(plist_folder):
                errors.append("PList Debug folder must be a valid Windows path (e.g., C:\\Folder).")
            if not self.Windows_path_validator(bundle_folder):
                errors.append("Bundle folder must be a valid Windows path (e.g., C:\\Folder).")

            if errors:
                messagebox.showerror("Error", "\n".join(errors))
                return

            self.app.user_data["users"][selected_username] = {
                "PListDebugFolder": plist_folder,
                "BundleFolder": bundle_folder,
                "Project": project,
                "Die": die,
            }

            with self._users_config_path().open("w", encoding="utf-8") as f:
                json.dump(self.app.user_data, f, indent=4)

            self.Load_users_from_json()
            self.app.Load_user_info_for_bundle_section_P6(self.app.User_info_frame_P6)
            popup.destroy()

        self.app.Create_user_window_save_button(popup, edit_user_save_changes)
