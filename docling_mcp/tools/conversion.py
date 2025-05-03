"""Tools for converting documents into DoclingDocument objects."""
import os
import json
from pathlib import Path
from docling_mcp.docling_cache import get_cache_dir
import gc
from typing import Annotated, Any

from mcp.shared.exceptions import McpError
from mcp.types import INTERNAL_ERROR, ErrorData

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import (
    AcceleratorDevice,
    PdfPipelineOptions,
)
from docling.document_converter import DocumentConverter, FormatOption, PdfFormatOption
from docling_core.types.doc.document import (
    ContentLayer,
    DoclingDocument
)
from docling_core.types.doc.labels import (
    DocItemLabel,
)

from docling_mcp.docling_cache import get_cache_key
from docling_mcp.logger import setup_logger
from docling_mcp.shared import local_document_cache, local_stack_cache, mcp

# Create a default project logger
logger = setup_logger()


def cleanup_memory() -> None:
    """Force garbage collection to free up memory."""
    logger.info("Performed memory cleanup")
    gc.collect()


@mcp.tool()
def is_document_in_local_cache(cache_key: str) -> bool:
    """Verify if document is already converted and in the local cache.

    Args:
        cache_key: Document identifier in the cache.

    Returns:
        Whether the document is already converted and in the local cache.
    """
    return cache_key in local_document_cache


@mcp.tool()
def list_cached_documents() -> str:
    """Lists all documents currently available in the local document cache.

    This function retrieves information about all documents stored in the local cache
    and returns a formatted list with details such as document keys, names, and the
    number of items in each document.

    Returns:
        str: A formatted string listing all cached documents with their details.

    Example:
        list_cached_documents()
    """
    if not local_document_cache:
        return "No documents found in the local cache."

    result = "Documents in local cache:\n\n"

    for doc_key, document in local_document_cache.items():
        # Get document name
        doc_name = document.name or "Unnamed Document"

        # Count items in document
        item_count = len(document.items) if hasattr(document, "items") else 0

        # Find any source annotation
        source = ""
        for item in document.items.values() if hasattr(document, "items") else []:
            if hasattr(item, "text") and item.text and item.text.startswith("source:"):
                source = item.text
                break

        # Add to result
        result += f"* Document Key: {doc_key}\n"
        result += f"  - Name: {doc_name}\n"
        result += f"  - Items: {item_count}\n"
        if source:
            result += f"  - {source}\n"
        result += "\n"

    return result


@mcp.tool()
def convert_pdf_to_json(
        source: str,
) -> tuple[bool, str]:
    """Convert a PDF document from a URL or local path and store in local cache.

    Args:
        source: URL or local file path to the document

    Returns:
        The tools returns a tuple, the first element being a boolean
        representing success and the second for the cache_key to allow
        future access to the file.

    Usage:
        convert_document("https://arxiv.org/pdf/2408.09869")
        convert_document("/path/to/document.pdf")
    """
    try:
        # Remove any quotes from the source string
        source = source.strip("\"'")

        # Log the cleaned source
        logger.info(f"Processing document from source: {source}")

        # Generate cache key
        cache_key = get_cache_key(source)

        if cache_key in local_document_cache:
            logger.info(f"{source} has previously been added.")
            return False, "Document already exists in the system cache."

        # Log the start of processing
        logger.info("Set up pipeline options")

        # Configure pipeline
        # ocr_options = EasyOcrOptions(lang=ocr_language or ["en"])
        pipeline_options = PdfPipelineOptions(
            # do_ocr=False,
            # ocr_options=ocr_options,
            accelerator_device=AcceleratorDevice.MPS  # Explicitly set MPS
        )
        format_options: dict[InputFormat, FormatOption] = {
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }

        # Create converter with MPS acceleration
        logger.info(f"Creating DocumentConverter with format_options: {format_options}")
        converter = DocumentConverter(format_options=format_options)

        # Convert the document
        logger.info("Start conversion")
        result = converter.convert(source)

        # Check for errors - handle different API versions
        has_error = False
        error_message = ""

        # Try different ways to check for errors based on the API version
        if hasattr(result, "status"):
            if hasattr(result.status, "is_error"):
                has_error = result.status.is_error
            elif hasattr(result.status, "error"):
                has_error = result.status.error

        if hasattr(result, "errors") and result.errors:
            has_error = True
            error_message = str(result.errors)

        if has_error:
            error_msg = f"Conversion failed: {error_message}"
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=error_msg))

        local_document_cache[cache_key] = result.document

        item = result.document.add_text(
            label=DocItemLabel.TEXT,
            text=f"source: {source}",
            content_layer=ContentLayer.FURNITURE,
        )

        local_stack_cache[cache_key] = [item]

        # Log completion
        logger.info(f"Successfully created the Docling document: {source}")

        # Clean up memory
        cleanup_memory()

        return True, cache_key

    except Exception as e:
        logger.exception(f"Error converting document: {source}")
        raise McpError(
            ErrorData(code=INTERNAL_ERROR, message=f"Unexpected error: {e!s}")
        ) from e


@mcp.tool()
def convert_attachments_into_docling_document(
        pdf_payloads: list[Annotated[bytes, {"media_type": "application/octet-stream"}]],
) -> list[dict[str, Any]]:
    """Process a pdf files attachment from Claude Desktop.

    Args:
        pdf_payloads: PDF document as binary data from the attachment

    Returns:
        A dictionary with processed results
    """
    results = []
    for pdf_payload in pdf_payloads:
        # Example processing - you can replace this with your actual processing logic
        file_size = len(pdf_payload)

        # First few bytes as hex for identification
        header_bytes = pdf_payload[:10].hex()

        # You can implement file type detection, parsing, or any other processing here
        # For example, if it's an image, you might use PIL to process it

        results.append(
            {
                "file_size_bytes": file_size,
                "header_hex": header_bytes,
                "status": "processed",
            }
        )

    return results


@mcp.tool()
def reload_local_document_cache_from_dir() -> str:
    """Reloads the local document cache from cache directory on disk.

    Loads documents from the cache directory and updates the in-memory cache.

    Returns:
        str: String with results of reload operation.
    """
    cache_dir = get_cache_dir()
    loaded = 0
    failures = []

    # Limpa o cache em memória
    local_document_cache.clear()

    for entry in os.scandir(cache_dir):
        if entry.is_file() and entry.name.endswith(".json"):
            try:
                with open(entry.path, "r", encoding="utf-8") as f:
                    doc_dict = json.load(f)
                    if hasattr(DoclingDocument, "model_validate"):
                        doc = DoclingDocument.model_validate(doc_dict)
                    else:
                        # fallback para Pydantic v1
                        doc = DoclingDocument.parse_obj(doc_dict)

                cache_key = entry.name.removesuffix(".json")
                local_document_cache[cache_key] = doc
                loaded += 1
            except Exception as e:
                failures.append((entry.name, str(e)))

    msg = f"Reload finished: {loaded} document(s) loaded from {cache_dir}."
    if failures:
        msg += f" {len(failures)} document(s) failed to load: {failures}"
    logger.info(msg)
    return msg
