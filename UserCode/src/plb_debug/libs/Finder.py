import re
import tkinter as tk
from tkinter import messagebox


class Finder:
	"""Mixin for GUI classes that need PList search/extract helpers.

	Expects the host class to provide:
	- self.content (str)
	- self.matches (list[tuple[str, str]])
	- self.current_index (int)
	- self.Plist_file_viewer_text_area (tk.Text)
	- self.Selected_PList_extract_text_area (tk.Text)
	- self.search_filter_user_input_text (tk.Entry)
	- self.search_extract_matches_button (optional tk.Button)
	- self.search_match_count_label (tk.Label)
	- self.Highlight_matches_search_main_global_PList() method
	"""

	def Search_main_global_PList(self, content):  # P2
		lines = content.splitlines()
		filtered_content = []
		inside_block = False
		current_block = []
		skip_block = False

		for line in lines:  # Process each line to identify plist blocks
			if line.startswith("GlobalPList"):
				inside_block = True
				current_block.append(line)
			elif inside_block:
				current_block.append(line)
				if line.strip() == "}":
					inside_block = False
					if not skip_block:  # Check if the block should be omitted
						filtered_content.extend(current_block)
					else:
						filtered_content.extend(["\n"] * len(current_block))  # Replace block with blank lines
					current_block = []
					skip_block = False
			else:
				filtered_content.append("\n")  # Replace irrelevant content with blank line

			if inside_block and line.strip().startswith("Pat d"):  # Ignore lines starting with "Pat d"
				skip_block = True

		return "\n".join(filtered_content)

	def _ensure_plist_loaded_for_search(self) -> bool:
		if getattr(self, "content", ""):
			return True
		messagebox.showerror("Error", "Please open a PList file first.")
		return False

	def _validate_io_plist_input(self, text: str) -> bool:
		"""
		Validate IO Plist input structure.
		
		Minimum required structure: scn_c_x_x_x_sSs_x_x_x_list
		- Must contain 'scn_c'
		- Must contain 'sSs' (case sensitive)
		- Must end with 'list'
		- Must have at least 9 sections separated by underscores
		
		Args:
			text: Input string to validate
		
		Returns:
			True if valid, False otherwise (shows error message)
		"""
		if not text:
			return False
		
		# Check if it contains required components
		if "scn_c" not in text.lower():
			messagebox.showerror(
				"Invalid Input",
				"Please enter a valid Full IO Plist.\n\n"
				"The input must contain 'scn_c'."
			)
			return False
		
		if "sSs" not in text:
			messagebox.showerror(
				"Invalid Input",
				"Please enter a valid Full IO Plist.\n\n"
				"The input must contain 'sSs' (case sensitive)."
			)
			return False
		
		if not text.lower().endswith("list"):
			messagebox.showerror(
				"Invalid Input",
				"Please enter a valid Full IO Plist.\n\n"
				"The input must end with 'list'."
			)
			return False
		
		# Check minimum structure (at least 9 sections)
		sections = text.split("_")
		if len(sections) < 9:
			messagebox.showerror(
				"Invalid Input",
				"Please enter a valid Full IO Plist.\n\n"
				f"Minimum structure required: scn_c_x_x_x_sSs_x_x_x_list\n"
				f"Your input has {len(sections)} sections, but at least 9 are required."
			)
			return False
		
		return True

	def _set_matches_count(self, count: int) -> None:
		setter = getattr(self, "Set_matches_count", None)
		if callable(setter):
			setter(count)
			return
		label = getattr(self, "search_match_count_label", None)
		if label is not None:
			label.config(text=f"Matches: {count}")

	def _set_extract_button_state(self, enabled: bool, match_count: int | None = None) -> None:
		setter = getattr(self, "Set_extract_matches_button_state", None)
		if callable(setter):
			setter(enabled, match_count)
			return
		button = getattr(self, "search_extract_matches_button", None)
		if button is not None:
			button.config(state="normal" if enabled else "disabled")

	def _extract_globalplist_block_from_content(self, plist_key: str) -> list[str]:
		content = getattr(self, "content", "")
		if not content or not plist_key:
			return []
		lines = content.splitlines()

		header_index: int | None = None
		for i, line in enumerate(lines):
			if line.lstrip().startswith("GlobalPList") and plist_key in line:
				header_index = i
				break
		if header_index is None:
			return []

		brace_level = lines[header_index].count("{") - lines[header_index].count("}")
		j = header_index + 1
		if brace_level <= 0:
			for k in range(j, len(lines)):
				brace_level += lines[k].count("{") - lines[k].count("}")
				if "{" in lines[k]:
					j = k + 1
					break
			if brace_level <= 0:
				return []

		block: list[str] = []
		for k in range(j, len(lines)):
			brace_level += lines[k].count("{") - lines[k].count("}")
			if brace_level <= 0:
				break
			block.append(lines[k])
		return block

	def Extract_selected_matches(self):  # P2
		self.Selected_PList_extract_text_area.delete(1.0, tk.END)

		if not hasattr(self, 'matches') or not self.matches:
			messagebox.showerror("Error", "Please run Search first.")
			return

		# Original behavior: extract the matched lines themselves
		extracted_lines = []
		for i, (start, end) in enumerate(self.matches):
			line_text = self.Plist_file_viewer_text_area.get(start, end).strip()
			if line_text:
				extracted_lines.append(line_text)

		# Prepend appended content if exists
		appended_content = getattr(self, "appended_plist_content", "")
		if appended_content:
			self.Selected_PList_extract_text_area.insert(tk.END, appended_content + "\n")

		if extracted_lines:
			self.Selected_PList_extract_text_area.insert(tk.END, "\n".join(extracted_lines))
		else:
			if not appended_content:
				self.Selected_PList_extract_text_area.insert(tk.END, "No valid lines extracted.")

	def Extract_selected_matches_IO(self):  # P2
		"""Extract GlobalPList block content for tab2 IO searches.

		Uses self.IO_plb_output (preferred) and/or matched lines that start with
		'GlobalPList' to locate the corresponding block in self.content and extract
		lines between '{' and the matching '}'.
		"""
		self.Selected_PList_extract_text_area.delete(1.0, tk.END)

		matches = getattr(self, "matches_tab2", None)
		if matches is None:
			matches = getattr(self, "matches", [])

		if not matches and not getattr(self, "IO_plb_output", "").strip():
			messagebox.showerror("Error", "Please run Search first.")
			return

		keys: list[str] = []
		io_out = getattr(self, "IO_plb_output", "")
		if isinstance(io_out, str) and io_out.strip():
			for line in io_out.splitlines():
				key = line.strip()
				if key:
					keys.append(key)

		for start, end in matches:
			line_text = self.Plist_file_viewer_text_area.get(start, end).strip()
			if line_text.startswith("GlobalPList"):
				m = re.search(r"(scn_c[0-9A-Za-z_]*(?:_plist|_list))", line_text)
				if m:
					keys.append(m.group(1))

		seen_keys: set[str] = set()
		keys = [k for k in keys if not (k in seen_keys or seen_keys.add(k))]

		extracted_lines: list[str] = []
		for key in keys:
			block = self._extract_globalplist_block_from_content(key)
			if block:
				extracted_lines.extend(block)

		# Prepend appended content if exists
		appended_content = getattr(self, "appended_plist_content", "")
		if appended_content:
			self.Selected_PList_extract_text_area.insert(tk.END, appended_content + "\n")

		if extracted_lines:
			self.Selected_PList_extract_text_area.insert(tk.END, "\n".join(extracted_lines))
		else:
			if not appended_content:
				self.Selected_PList_extract_text_area.insert(tk.END, "No GlobalPList blocks found to extract.")

	def Find_matches_search_main_global_PList(self):  # P2
		if not self._ensure_plist_loaded_for_search():
			return
		search_text = self.search_filter_user_input_text.get().strip().lower()
		self.matches = []
		self.current_index = 0

		if search_text:
			filtered_content = self.Search_main_global_PList(self.content)
			self.Plist_file_viewer_text_area.delete(1.0, tk.END)
			self.Plist_file_viewer_text_area.insert(tk.END, filtered_content)
			lines = filtered_content.splitlines()

			if "*" in search_text:  # Regex Search
				raw_parts = [part.strip().lower() for part in search_text.split("*") if part.strip()]
				parts = []

				for part in raw_parts:
					if part == "atpg":
						parts.append(re.escape("_atpg"))
					else:
						parts.append(re.escape(part))
				pattern = r"(?i)" + r".*".join(parts)
				regex = re.compile(pattern)

				for index, line in enumerate(lines, start=1):
					if regex.search(line.lower()):
						start = f"{index}.0"
						end = f"{index}.end"
						self.matches.append((start, end))

			else:  # Regular Search
				search_text_lower = search_text
				for index, line in enumerate(lines, start=1):
					if search_text_lower in line.lower():
						start = f"{index}.0"
						end = f"{index}.end"
						self.matches.append((start, end))
			self.Highlight_matches_search_main_global_PList()

		self._set_extract_button_state(len(self.matches) > 0, len(self.matches))
		self._set_matches_count(len(self.matches))
		# Keep per-tab matches to avoid cross-tab remanence
		setattr(self, "matches_tab1", list(self.matches))

	def Get_IO_Plist(self):
		"""Search for IO plist lines using tab2 input transformations.

		Uses self.content populated by Load_plist_file(). Expects the host GUI to
		provide self.search_filter_user_input_text_tab2 (tk.Entry).
		"""
		if not self._ensure_plist_loaded_for_search():
			return

		entry = getattr(self, "search_filter_user_input_text_tab2", None)
		if entry is None:
			return

		text = entry.get().strip()
		self.IO_plb_output = ""
		self.matches = []
		self.current_index = 0

		if not text:
			self._set_matches_count(0)
			return
		
		# Validate IO Plist input structure
		if not self._validate_io_plist_input(text):
			self._set_matches_count(0)
			return

		io_plb = re.sub("IE", "", text)
		io_plb = re.sub(r"scn_c_[0-9a-zA-Z_]*_sEs", "scn_c_.*_sSs", io_plb)

		# Treat everything as literal except the injected '.*' wildcard.
		wild_parts = io_plb.split(".*")
		pattern = ".*".join(re.escape(p) for p in wild_parts)
		regex = re.compile(pattern, re.IGNORECASE)

		# Search against the full content and show it in the viewer.
		self.Plist_file_viewer_text_area.delete(1.0, tk.END)
		self.Plist_file_viewer_text_area.insert(tk.END, self.content)
		lines = self.content.splitlines()

		for index, line in enumerate(lines, start=1):
			if regex.search(line):
				start = f"{index}.0"
				end = f"{index}.end"
				self.matches.append((start, end))

		# Build IO_plb_output (only substrings that start with 'scn_c' and end with '_list'/'_plist')
		io_outputs: list[str] = []
		for start, _ in self.matches:
			try:
				line_no = int(start.split(".")[0])
			except Exception:
				continue
			line = lines[line_no - 1]
			m = re.search(r"(scn_c[0-9A-Za-z_]*(?:_plist|_list))", line)
			if m:
				io_outputs.append(m.group(1))
		# de-dup while preserving order
		seen: set[str] = set()
		io_outputs = [s for s in io_outputs if not (s in seen or seen.add(s))]
		self.IO_plb_output = "\n".join(io_outputs)

		if self.matches:
			self.Highlight_matches_search_main_global_PList()

		self._set_matches_count(len(self.matches))
		self._set_extract_button_state(len(self.matches) > 0, len(self.matches))
		# Keep per-tab matches to avoid cross-tab remanence
		setattr(self, "matches_tab2", list(self.matches))

		#print(f"Get_IO_Plist | input='{text}' | transformed='{io_plb}' | matches={len(self.matches)}|{self.IO_plb_output}")

