"""Tools for managing document sections in Docling documents."""

from typing import Dict, List, Optional, Any

from docling_core.types.doc.document import DoclingDocument
from docling_core.types.doc.labels import DocItemLabel

from docling_mcp.logger import setup_logger
from docling_mcp.shared import local_document_cache, mcp

# Create a default project logger
logger = setup_logger()


@mcp.tool()
def list_document_sections(document_key: str) -> str:
    """Lists all sections (headings) in a document from the local document cache.
    
    This function identifies all headings in the document and returns them in a 
    structured format that includes section level and title, organized hierarchically.
    
    Args:
        document_key (str): The unique identifier for the document in the local cache.
        
    Returns:
        str: A formatted string listing all sections with their levels and titles.
        
    Raises:
        ValueError: If the specified document_key does not exist in the local cache.
        
    Example:
        list_document_sections("doc123")
    """
    if document_key not in local_document_cache:
        doc_keys = ", ".join(local_document_cache.keys())
        raise ValueError(
            f"document-key: {document_key} is not found. Existing document-keys are: {doc_keys}"
        )

    doc: DoclingDocument = local_document_cache[document_key]
    sections = []
    section_ids = {}

    # Go through all items in the document to find headings
    for item_id, item in doc.items.items():
        if item.label == DocItemLabel.HEADING:
            # Get the level if available, otherwise default to 1
            level = getattr(item, "level", 1)
            sections.append({
                "id": item_id,
                "level": level,
                "title": item.text,
                "position": len(sections)  # Track original order
            })
            section_ids[item_id] = len(sections) - 1

    # Sort sections by their position
    sections.sort(key=lambda x: x["position"])

    # Format the output
    if not sections:
        return f"No sections found in document with key: {document_key}"

    result = f"Sections in document with key: {document_key}\n\n"
    for section in sections:
        indent = "  " * (section["level"] - 1)
        result += f"{indent}* [{section['id']}] Level {section['level']}: {section['title']}\n"

    return result


@mcp.tool()
def get_document_section_content(document_key: str, section_id: str) -> str:
    """Retrieves the content of a specific section from a document in the local cache.
    
    This function extracts the content of a section identified by its section_id,
    including all text and nested elements until the next heading of the same or higher level.
    
    Args:
        document_key (str): The unique identifier for the document in the local cache.
        section_id (str): The identifier of the section to retrieve.
        
    Returns:
        str: The content of the specified section, formatted as markdown.
        
    Raises:
        ValueError: If the specified document_key does not exist in the local cache.
        ValueError: If the specified section_id does not exist in the document.
        
    Example:
        get_document_section_content("doc123", "heading_12345")
    """
    if document_key not in local_document_cache:
        doc_keys = ", ".join(local_document_cache.keys())
        raise ValueError(
            f"document-key: {document_key} is not found. Existing document-keys are: {doc_keys}"
        )

    doc: DoclingDocument = local_document_cache[document_key]

    # Check if section exists
    if section_id not in doc.items:
        item_ids = ", ".join(doc.items.keys())
        raise ValueError(
            f"section-id: {section_id} is not found in document. Available items: {item_ids[:200]}..."
        )

    section_item = doc.items[section_id]

    # Verify it's a heading
    if section_item.label != DocItemLabel.HEADING:
        raise ValueError(
            f"Item with ID {section_id} is not a heading, but a {section_item.label}"
        )

    # Get section level
    section_level = getattr(section_item, "level", 1)
    section_title = section_item.text

    # Create a temporary document to export just this section
    section_doc = DoclingDocument(name=f"Section: {section_title}")

    # Add the section heading
    section_doc.add_heading(text=section_title, level=section_level)

    # Find all content that belongs to this section
    # Get document structure
    structure = doc.get_document_structure()

    # Find the section in the structure and extract its content
    in_section = False
    section_content = []

    for item_id in structure:
        if item_id == section_id:
            in_section = True
            continue  # Skip the heading itself as we've already added it

        if in_section:
            item = doc.items[item_id]

            # If we hit another heading of same or higher level, we've exited this section
            if item.label == DocItemLabel.HEADING:
                item_level = getattr(item, "level", 1)
                if item_level <= section_level:
                    break

            # Add this item to our content
            # For simplicity, we'll just store the text content
            if hasattr(item, "text") and item.text:
                section_content.append(item.text)

    # Add the content to our section document
    for text in section_content:
        section_doc.add_text(label=DocItemLabel.TEXT, text=text)

    # Export to markdown
    markdown = section_doc.export_to_markdown()

    return f"Content of section '{section_title}' from document with key: {document_key}\n\n{markdown}"


@mcp.tool()
def get_document_page_count(document_key: str) -> int:
    """Retorna o número estimado de páginas no documento. Considera cada quebra de página como início de uma nova página.

    Args:
        document_key (str): Identificador do documento no cache local.

    Returns:
        int: Número de páginas (mínimo 1).

    Raises:
        ValueError: Se o documento não existir.
    """
    if document_key not in local_document_cache:
        doc_keys = ", ".join(local_document_cache.keys())
        raise ValueError(
            f"document-key: {document_key} is not found. Existing document-keys are: {doc_keys}"
        )

    doc: DoclingDocument = local_document_cache[document_key]

    # O label pode ser diferente, verifique como é chamado na sua implementação!
    PAGEBREAK_LABEL = getattr(DocItemLabel, "PAGEBREAK", None)
    if PAGEBREAK_LABEL is None:
        # Talvez seja "PAGE_BREAK" ou similar! Ajuste conforme necessário.
        raise ValueError("PAGEBREAK label not found in DocItemLabel")

    pagebreak_count = sum(
        1 for item in doc.items.values() if item.label == PAGEBREAK_LABEL
    )

    # O número de páginas é pelo menos 1 (página antes da primeira quebra)
    return pagebreak_count + 1


@mcp.tool()
def get_document_paragraph_count(document_key: str) -> int:
    """Retorna o número total de parágrafos (itens de texto) do documento.

    Args:
        document_key (str): Identificador do documento no cache local.

    Returns:
        int: Número total de parágrafos no documento.

    Raises:
        ValueError: Se o documento não existir.
    """
    if document_key not in local_document_cache:
        doc_keys = ", ".join(local_document_cache.keys())
        raise ValueError(
            f"document-key: {document_key} is not found. Existing document-keys are: {doc_keys}"
        )

    doc: DoclingDocument = local_document_cache[document_key]

    paragraph_count = sum(
        1 for item in doc.items.values() if item.label == DocItemLabel.TEXT
    )

    return paragraph_count


@mcp.tool()
def get_document_page_content(document_key: str, page_number: int) -> list[str]:
    """
    Retorna o conteúdo (parágrafos) de uma página específica do documento.

    Args:
        document_key (str): Identificador do documento no cache local.
        page_number (int): Número da página desejada (começando em 1).

    Returns:
        list[str]: Lista de textos encontrados na página especificada.

    Raises:
        ValueError: Se o documento não existir ou o número de página for inválido.
    """
    if document_key not in local_document_cache:
        doc_keys = ", ".join(local_document_cache.keys())
        raise ValueError(
            f"document-key: {document_key} is not found. Existing document-keys are: {doc_keys}"
        )

    doc: DoclingDocument = local_document_cache[document_key]
    PAGEBREAK_LABEL = getattr(DocItemLabel, "PAGEBREAK", None)
    if PAGEBREAK_LABEL is None:
        raise ValueError("PAGEBREAK label not found in DocItemLabel")

    items_in_order = list(doc.items.values())
    current_page = 1
    page_content = []

    for item in items_in_order:
        if item.label == PAGEBREAK_LABEL:
            current_page += 1
            continue
        if current_page == page_number and \
                getattr(item, "text", None) and item.label == DocItemLabel.TEXT:
            page_content.append(item.text)
        elif current_page > page_number:
            break

    if not page_content:
        raise ValueError(f"Nenhum conteúdo encontrado para a página {page_number}.")

    return page_content
