"""
Utility helper functions for Deep Agent - Policy Edition
Contains text extraction, cleaning, and other utility functions
"""
import re
from pathlib import Path
from typing import Optional
from pypdf import PdfReader
from docx import Document as DocxDocument

from src.core.config import ALLOWED_EXTENSIONS


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract text content from a PDF file.
    
    Args:
        file_path: Path to the PDF file
        
    Returns:
        Extracted text content as a string
    """
    reader = PdfReader(file_path)
    text_parts = []
    
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)
    
    return "\n\n".join(text_parts)


def extract_text_from_docx(file_path: str) -> str:
    """
    Extract text content from a DOCX file.
    
    Args:
        file_path: Path to the DOCX file
        
    Returns:
        Extracted text content as a string
    """
    doc = DocxDocument(file_path)
    text_parts = []
    
    for paragraph in doc.paragraphs:
        if paragraph.text.strip():
            text_parts.append(paragraph.text)
    
    return "\n\n".join(text_parts)


def extract_text_from_txt(file_path: str) -> str:
    """
    Extract text content from a TXT file.
    
    Args:
        file_path: Path to the TXT file
        
    Returns:
        Extracted text content as a string
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def extract_text(file_path: str) -> str:
    """
    Extract text from a document based on its file extension.
    
    Args:
        file_path: Path to the document file
        
    Returns:
        Extracted text content as a string
        
    Raises:
        ValueError: If the file type is not supported
    """
    path = Path(file_path)
    extension = path.suffix.lower()
    
    if extension == ".pdf":
        return extract_text_from_pdf(file_path)
    elif extension == ".docx":
        return extract_text_from_docx(file_path)
    elif extension == ".txt":
        return extract_text_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {extension}")


def clean_text(text: str) -> str:
    """
    Clean and normalize text content.
    Removes excessive whitespace, normalizes line breaks, and handles common issues.
    
    Args:
        text: Raw text content
        
    Returns:
        Cleaned text content
    """
    # Remove NUL characters (0x00) - PostgreSQL doesn't allow these in text fields
    text = text.replace('\x00', '')
    
    # Remove other problematic control characters (except newline, tab, carriage return)
    text = re.sub(r'[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    # Replace multiple newlines with double newline (paragraph separator)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Replace multiple spaces with single space
    text = re.sub(r' {2,}', ' ', text)
    
    # Remove leading/trailing whitespace from each line
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    # Remove leading/trailing whitespace from entire text
    text = text.strip()
    
    return text


def validate_file_extension(filename: str) -> bool:
    """
    Validate if a file has an allowed extension.
    
    Args:
        filename: Name of the file
        
    Returns:
        True if extension is allowed, False otherwise
    """
    extension = Path(filename).suffix.lower()
    return extension in ALLOWED_EXTENSIONS


def get_file_type(filename: str) -> str:
    """
    Get the file type from filename.
    
    Args:
        filename: Name of the file
        
    Returns:
        File type string (pdf, docx, txt)
    """
    return Path(filename).suffix.lower().lstrip('.')


def truncate_text(text: str, max_length: int = 500) -> str:
    """
    Truncate text to a maximum length while preserving word boundaries.
    
    Args:
        text: Text to truncate
        max_length: Maximum length of the truncated text
        
    Returns:
        Truncated text with ellipsis if truncated
    """
    if len(text) <= max_length:
        return text
    
    # Find the last space before max_length
    truncated = text[:max_length]
    last_space = truncated.rfind(' ')
    
    if last_space > 0:
        truncated = truncated[:last_space]
    
    return truncated + "..."


def format_sources(chunks: list, max_preview_length: int = 200) -> list:
    """
    Format document chunks as source references for the response.
    
    Args:
        chunks: List of DocumentChunk objects
        max_preview_length: Maximum length of the content preview
        
    Returns:
        List of formatted source dictionaries
    """
    sources = []
    for chunk in chunks:
        sources.append({
            "document_id": chunk.document_id,
            "chunk_index": chunk.chunk_index,
            "content_preview": truncate_text(chunk.content, max_preview_length),
            "document_name": chunk.document.filename if chunk.document else "Unknown"
        })
    return sources