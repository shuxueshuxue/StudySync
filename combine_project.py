#!/usr/bin/env python3
# combine_project.py - Combines all project files into a single file for easier LLM debugging

import os
import re
import argparse
from datetime import datetime

# Files to exclude from combination
EXCLUDE_FILES = [
    "__pycache__",
    ".git",
    ".vscode",
    ".idea",
    ".pytest_cache",
    "__init__.py",
    "combine_project.py"  # Don't include this script itself
]

# Extensions to include
INCLUDE_EXTENSIONS = [
    ".py",
    # ".html",
    # ".css",
    # ".js",
    # ".md",
    # ".txt"
]

def should_include_file(filepath):
    """Check if a file should be included in the combined output"""
    filename = os.path.basename(filepath)

    if filename == "index.html" or filename == "settings.html" or filename == "letter_template.html":
        return True
    
    # Check if the file is in the exclude list
    for exclude in EXCLUDE_FILES:
        if exclude in filepath:
            return False
    
    # Check if the file has an extension we want to include
    _, ext = os.path.splitext(filepath)
    if ext.lower() not in INCLUDE_EXTENSIONS:
        return False
    
    return True

def get_language_from_extension(ext):
    """Get language name for code block based on file extension"""
    ext = ext.lower()
    if ext == ".py":
        return "python"
    elif ext == ".html":
        return "html"
    elif ext == ".css":
        return "css"
    elif ext == ".js":
        return "javascript"
    elif ext == ".md":
        return "markdown"
    else:
        return "text"

def combine_files(directory, output_file, include_init=False):
    """Combine all project files into a single text file"""
    combined_content = []
    
    # Add header
    combined_content.append(f"# Nova Project - Combined Source Code\n")
    combined_content.append(f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    combined_content.append(f"# This file contains the combined source code of the Nova Project\n\n")
    
    # Get list of files in project directory
    file_list = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, directory)
            
            # Skip __init__.py files if not included
            if file == "__init__.py" and not include_init:
                continue
                
            if should_include_file(filepath):
                file_list.append((rel_path, filepath))
    
    # Sort files by path for consistent output
    file_list.sort()
    
    # Process each file
    for rel_path, filepath in file_list:
        _, ext = os.path.splitext(filepath)
        language = get_language_from_extension(ext)
        
        # Add file header
        combined_content.append(f"## File: {rel_path}\n")
        
        # Read and add file content
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                combined_content.append(f"```{language}")
                combined_content.append(content)
                combined_content.append("```\n")
        except Exception as e:
            combined_content.append(f"Error reading file: {e}\n")
    
    # Write combined content to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(combined_content))
    
    print(f"Combined {len(file_list)} files into {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Combine Nova Project files into a single file for LLM processing")
    parser.add_argument("-o", "--output", default="nova_project_combined.md", help="Output file name")
    parser.add_argument("-d", "--directory", default=".", help="Project root directory")
    parser.add_argument("--include-init", action="store_true", help="Include __init__.py files")
    
    args = parser.parse_args()
    
    # Ensure output file has .md extension
    output_file = args.output
    if not output_file.endswith('.md'):
        output_file += '.md'
    
    combine_files(args.directory, output_file, args.include_init)
    
    # Display instructions
    print("\nInstructions for using the combined file with an LLM:")
    print("1. Upload the generated file to the LLM interface")
    print("2. Ask the LLM to analyze, explain, or modify the code")
    print("3. For modifications, instruct the LLM to output the complete modified file")
    print("   with the original file path in a comment at the top")

if __name__ == "__main__":
    main()
