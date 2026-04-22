import sys
import tkinter as tk
from tkinter import messagebox


class Extractor:
	def __init__(self, tool):
		self.tool = tool

	def Extract_main_call_PList(self):  # P3
		if not self.tool.file_path:
			print("No file path available.")
			return

		# Open the file and read its lines
		try:
			with open(self.tool.file_path, 'r') as file:
				buffer = file.readlines()
		except IOError:
			print(f"Couldn't open {self.tool.file_path}")
			return

		extracted_maincall_list = []
		inside_block = False
		current_block_name = ""

		# Process each line in the processed_text
		processed_lines = self.tool.processed_text.splitlines()

		# Iterate over each line in the buffer
		for line in buffer:
			if line.startswith("GlobalPList"):
				inside_block = True
				# Extract the block name
				start_index = line.find("GlobalPList") + len("GlobalPList")
				end_index = line.find("[", start_index)
				if end_index != -1:
					current_block_name = line[start_index:end_index].strip()
			elif inside_block and line.strip() == "}":
				inside_block = False
				current_block_name = ""

			# Check if any processed line is in the current block
			if inside_block:
				for processed_line in processed_lines:
					if processed_line in line:
						# Ensure the block name is not in processed_lines before adding
						if (
							current_block_name
							and current_block_name not in extracted_maincall_list
							and current_block_name not in processed_lines
						):
							extracted_maincall_list.append(current_block_name)
						break

		# Store the extracted MainCall list
		self.tool.Extracted_MainCall_list = extracted_maincall_list

		# Concatenate the extracted_maincall_list to the end of processed_text
		if self.tool.Extracted_MainCall_list:
			self.tool.processed_text += "\n" + "\n".join(self.tool.Extracted_MainCall_list)

	def Extract_PreBurstPList(self):  # P3
		if not self.tool.file_path:
			print("No file path available.")
			return

		# Open the file and read its lines
		try:
			with open(self.tool.file_path, 'r') as file:
				buffer = file.readlines()
		except IOError:
			print(f"Couldn't open {self.tool.file_path}")
			sys.exit(1)

		extracted_preburst_list = []
		inside_block = False
		processed_lines = self.tool.processed_text.splitlines()  # Convert processed_text to a list of lines

		# Find PreBurstPList in the buffer
		for line in buffer:
			if line.startswith("GlobalPList"):
				inside_block = True
				# Check for PreBurstPList in the line
				start_index = line.find("[PreBurstPList")
				if start_index != -1:
					end_index = line.find("]", start_index)
					if end_index != -1:
						preburst_text = line[start_index + len("[PreBurstPList"):end_index].strip()
						# Check if any element from processed_lines is in the line
						for processed_line in processed_lines:
							if processed_line in line:
								extracted_preburst_list.append(preburst_text)
								break  # Exit the loop once a match is found
			elif inside_block and line.strip() == "}":
				inside_block = False

		# Store the extracted PreBurstPList
		self.tool.Extracted_PreBurstPList_list = extracted_preburst_list

		# Concatenate the extracted PreBurstPList before processed_text
		if self.tool.Extracted_PreBurstPList_list:
			self.tool.processed_text = "\n".join(self.tool.Extracted_PreBurstPList_list) + "\n" + self.tool.processed_text

	def Extract_selected_PList(self):  # P3
		extracted_text = self.tool.Selected_PList_extract_text_area.get("1.0", tk.END).strip()

		if extracted_text:
			seen = set()
			processed_lines = []
			for line in extracted_text.splitlines():
				cleaned_line = line.replace("PList", "").replace(";", "").replace(" ", "")
				if cleaned_line and cleaned_line not in seen:  # Remove empty and duplicated
					seen.add(cleaned_line)
					processed_lines.append(cleaned_line)

			self.tool.processed_text = "\n".join(processed_lines)
			self.Extract_main_call_PList()
			if self.tool.include_preburst.get():  # Get the Pre Burst PList if the switch is on
				self.Extract_PreBurstPList()

		else:
			messagebox.showwarning(
				"Warning",
				"No text to process. Please enter text in the 'PList to Extract' area.",
			)
