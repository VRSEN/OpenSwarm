import os
from typing import Optional
from agency_swarm.tools import BaseTool
from pydantic import Field
from markitdown import MarkItDown

class DeepReadFile(BaseTool):
    """
    A tool to read and convert various file formats into Markdown.
    Supports PDF, DOCX, XLSX, PPTX, HTML, and common image formats (via OCR if configured).
    
    Use this tool when you need to understand the content of a non-plain-text file.
    """

    file_path: str = Field(..., description="The absolute path to the file to read and convert.")
    
    def run(self):
        try:
            # Ensure the path is absolute
            abs_path = os.path.abspath(self.file_path)
            
            if not os.path.exists(abs_path):
                return f"Error: File does not exist at {abs_path}"
            
            if not os.path.isfile(abs_path):
                return f"Error: {abs_path} is not a file."

            # Initialize MarkItDown
            md = MarkItDown()
            
            # Convert the file
            result = md.convert(abs_path)
            
            if not result or not result.text_content:
                return f"Warning: Conversion successful but no text content was extracted from {os.path.basename(abs_path)}."
            
            content = result.text_content
            
            # Add a header to indicate the source
            header = f"--- Content of {os.path.basename(abs_path)} ---\n\n"
            return header + content

        except Exception as e:
            return f"Error converting file {self.file_path}: {str(e)}"

if __name__ == "__main__":
    # Test with a simple text file first
    test_file = "test_deep_read.txt"
    with open(test_file, "w") as f:
        f.write("# Test Heading\nThis is a test file for DeepReadFile.")
    
    tool = DeepReadFile(file_path=os.path.abspath(test_file))
    print(tool.run())
    
    os.remove(test_file)
