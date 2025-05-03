"""This module initializes and runs the Docling MCP server."""

import os

from docling_mcp.logger import setup_logger
from docling_mcp.shared import mcp
from docling_mcp.tools.conversion import (
    convert_pdf_to_json,
    is_document_in_local_cache,
    list_cached_documents,
    reload_local_document_cache_from_dir
)
from docling_mcp.tools.generation import (
    add_listitem_to_list_in_docling_document,
    add_paragraph_to_docling_document,
    add_section_heading_to_docling_document,
    add_title_to_docling_document,
    close_list_in_docling_document,
    create_new_docling_document,
    export_docling_document_to_markdown,
    open_list_in_docling_document,
    save_docling_document,
)

from docling_mcp.tools.document_section_management import (
    list_document_sections,
    get_document_section_content,
    get_document_page_content,
    get_document_page_count,
    get_document_paragraph_count,
)

if (
    os.getenv("RAG_ENABLED") == "true"
    and os.getenv("OLLAMA_MODEL") != ""
    and os.getenv("EMBEDDING_MODEL") != ""
):
    from docling_mcp.tools.applications import (
        export_docling_document_to_vector_db,
        search_documents,
    )


def main() -> None:
    """Initialize and run the Docling MCP server."""
    # Create a default project logger
    logger = setup_logger()
    logger.info("starting up Docling MCP-server ...")

    # Initialize and run the server
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
