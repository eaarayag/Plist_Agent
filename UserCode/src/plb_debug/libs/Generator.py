import os
import re
import sys
import getpass
from tkinter import filedialog, messagebox

from libs.UsageLog import append_usage_log


class Gen_PLB:
    def __init__(self, app):
        self.app = app

    def Give_me_this_block(self, processed_lines, output_file_path):  # P4
        if not self.app.file_path:
            print("No file path available.")
            return

        try:
            with open(self.app.file_path, "r") as file:
                buffer = file.readlines()
        except IOError:
            print(f"Couldn't open {self.app.file_path}")
            sys.exit(1)

        extracted_plist = []

        for plb in processed_lines:
            extracted_lines = []
            flag = False
            for line in buffer:
                if flag:
                    extracted_lines.append(line)
                    if "}" in line:
                        flag = False
                        break
                elif line.strip().startswith(f"GlobalPList {plb}"):
                    flag = True
                    extracted_lines.append(line)
            extracted_plist.extend(extracted_lines)

        with open(output_file_path, "w") as file:
            file.write("Version 5.0;\n\n")
            file.writelines(extracted_plist)

    def Extract_plb_calls_grouping(self):  # P4
        if not self.app.output_file_path:
            return

        reset_hotreset_header = ["#-----------------#\n", "# RESET/HOT RESET #\n", "#-----------------#\n"]
        partitions_content_header = ["#--------------------#\n", "# PARTITIONS CONTENT #\n", "#--------------------#\n"]
        plb_header = ["#--------------------#\n", "# PLB CALLS GROUPING #\n", "#--------------------#\n"]

        try:
            with open(self.app.output_file_path, "r") as file:
                lines = file.readlines()
        except IOError:
            return

        def Format_PList_File(lines):
            modified_lines = []
            hotreset_inserted = False
            partitions_inserted = False
            plb_grouping_inserted = False
            inside_partition_block = False
            last_partition_block_end_index = -1

            for _, line in enumerate(lines):
                stripped = line.strip()

                if (
                    not hotreset_inserted
                    and stripped.startswith("GlobalPList")
                    and "_hotreset_" in stripped
                    and stripped.endswith("{")
                ):
                    modified_lines.extend(reset_hotreset_header)
                    hotreset_inserted = True

                if re.search(
                    r"^GlobalPList\s+((?!hotreset).)*\[\s*PreBurstPList\s+\S*hotreset\S*\]\s*\[\s*PostBurstPList\s+[^\]]+\]\s*\[.*\]\s*{$",
                    stripped,
                ):
                    if not partitions_inserted:
                        modified_lines.extend(partitions_content_header)
                        partitions_inserted = True
                    inside_partition_block = True

                modified_lines.append(line)

                if inside_partition_block and stripped == "}":
                    last_partition_block_end_index = len(modified_lines)
                    inside_partition_block = False

            if last_partition_block_end_index != -1:
                modified_lines[last_partition_block_end_index:last_partition_block_end_index] = plb_header
                plb_grouping_inserted = True

            if not plb_grouping_inserted:
                modified_lines.extend(["\n"] + plb_header)

            return modified_lines

        modified_lines = Format_PList_File(lines)

        try:
            with open(self.app.output_file_path, "w") as file:
                file.writelines(modified_lines)
        except IOError:
            pass

        try:
            with open(self.app.output_file_path, "r") as file:
                full_content = file.readlines()
        except IOError:
            return

        start_index = -1
        for i in range(len(full_content)):
            if full_content[i : i + 3] == plb_header:
                start_index = i + 3
                break

        if start_index == -1:
            return

        blocks = []
        current_block = []
        inside_block = False

        for line in full_content[start_index:]:
            if line.strip().startswith("GlobalPList"):
                current_block = [line]
                inside_block = True
            elif inside_block:
                current_block.append(line)
                if line.strip() == "}":
                    blocks.append(current_block)
                    inside_block = False

        for block in blocks:
            updated_block = []
            block_header = block[0]
            block_footer = block[-1]
            updated_block.append(block_header)

            for line in block[1:-1]:
                match = re.search(r"PList(.*?)\;", line)
                if match:
                    plist_id = match.group(1).strip()
                    count = sum(1 for l in full_content if plist_id in l)
                    if count > 1:
                        updated_block.append(line)
                else:
                    updated_block.append(line)

            updated_block.append(block_footer)
            block_start = full_content.index(block[0])
            block_end = block_start + len(block)
            full_content[block_start:block_end] = updated_block

        try:
            with open(self.app.output_file_path, "w") as file:
                file.writelines(full_content)
        except IOError:
            pass

    def Add_custom_plb_name(self):  # P4
        if not self.app.output_file_path:
            return

        try:
            with open(self.app.output_file_path, "r") as file:
                lines = file.readlines()
        except IOError:
            return

        modified_lines = []

        custom_suffix = self.app.custom_name_plb.get()
        if self.app.use_debug_default.get() and custom_suffix.strip() == "":
            custom_suffix = "debug"

        suffix = "_" + custom_suffix

        for line in lines:
            if "reset_Mscn" in line or "scn_preprecat" in line:
                modified_lines.append(line)
                continue

            matches = re.findall(r"\b\w*_list\w*\b", line)
            for match in matches:
                new_match = match + suffix
                line = re.sub(rf"\b{re.escape(match)}\b", new_match, line)
            modified_lines.append(line)

        try:
            with open(self.app.output_file_path, "w") as file:
                file.writelines(modified_lines)
        except IOError:
            pass

    def Generate_debug_plb(self):  # P4
        if not self.app.processed_text:
            messagebox.showwarning("Warning", "No processed text available. Please extract text first.")
            return

        # Validate that extract area doesn't contain GlobalPList elements
        try:
            extract_text_area = getattr(self.app, "Selected_PList_extract_text_area", None)
            if extract_text_area is not None:
                extract_content = extract_text_area.get("1.0", "end-1c")
                if "GlobalPList" in extract_content:
                    messagebox.showerror(
                        "Invalid Content",
                        "Only PList elements are valid, not GlobalPList.\n\n"
                        "Please remove any GlobalPList entries from the extract area\n"
                        "and keep only PList elements."
                    )
                    return
        except Exception:
            pass

        self.app.output_file_path = filedialog.asksaveasfilename(
            defaultextension=".plist", filetypes=[("PLIST Files", "*.plist")]
        )
        if self.app.output_file_path:
            self.Give_me_this_block(self.app.processed_text.splitlines(), self.app.output_file_path)
            self.Extract_plb_calls_grouping()

            if self.app.custom_name_plb.get() != "" or self.app.use_debug_default.get():
                self.Add_custom_plb_name()

            if hasattr(self.app, "debug_path_label"):
                self.app.debug_path_label.config(text=f"Last debug PList:\n{self.app.output_file_path}")

            if hasattr(self.app, "use_previous_plist") and self.app.use_previous_plist.get():
                if hasattr(self.app, "debug_plist_path_generated"):
                    self.app.debug_plist_path_generated.config(text=self.app.output_file_path)
            else:
                if hasattr(self.app, "debug_plist_path_generated"):
                    self.app.debug_plist_path_generated.config(text="No file selected")

            try:
                username = getpass.getuser()
                plb_name = os.path.basename(self.app.output_file_path)
                search_text = ""
                get_entry = getattr(self.app, "_get_active_search_entry", None)
                if callable(get_entry):
                    entry = get_entry()
                    if entry is not None and hasattr(entry, "get"):
                        search_text = entry.get()
                mtpl_file = ""
                input_path = getattr(self.app, "file_path", "")
                if isinstance(input_path, str) and input_path:
                    mtpl_file = os.path.basename(input_path)
                append_usage_log(username=username, plb_name=plb_name, search_text=search_text, mtpl_file=mtpl_file)
            except Exception:
                # Never block user flow on logging.
                pass

            messagebox.showinfo("Success", "PList file saved successfully.")

            # Clear search results + extract frame only after Success is shown.
            reset = getattr(self.app, "Reset_search_results_and_extract", None)
            if callable(reset):
                reset()
