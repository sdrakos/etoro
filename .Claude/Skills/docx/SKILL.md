---
name: docx
description: Work with Word documents (.docx files). Use when creating, editing, analyzing, or converting DOCX files. Supports text extraction, document creation with docx-js, OOXML editing, redlining workflow for tracked changes, and conversion to PDF/images.
---

# DOCX Skill - Complete Documentation

## Overview
This is a comprehensive skill for working with Word documents (.docx files). A .docx file is essentially a ZIP archive containing XML files and other resources. The skill provides different tools and workflows depending on your task.

## Workflow Decision Tree

### Reading/Analyzing Content
Use "Text extraction" or "Raw XML access" sections

### Creating New Document
Use "Creating a new Word document" workflow

### Editing Existing Document
- **Your own document + simple changes**: Use "Basic OOXML editing" workflow
- **Someone else's document**: Use **"Redlining workflow"** (recommended default)
- **Legal, academic, business, or government docs**: Use **"Redlining workflow"** (required)

---

## Reading and Analyzing Content

### Text Extraction
Convert document to markdown with tracked changes preserved:
```bash
pandoc --track-changes=all path-to-file.docx -o output.md
# Options: --track-changes=accept/reject/all
```

### Raw XML Access

#### Unpacking a file
```bash
python ooxml/scripts/unpack.py <office_file> <output_directory>
```

#### Key file structures
- `word/document.xml` - Main document contents
- `word/comments.xml` - Comments referenced in document.xml
- `word/media/` - Embedded images and media files
- Tracked changes use `<w:ins>` (insertions) and `<w:del>` (deletions) tags

---

## Creating a New Word Document

**MANDATORY**: Read `docx-js.md` (~500 lines) completely from start to finish.

### Workflow
1. Read the complete `docx-js.md` file (never set range limits)
2. Create a JavaScript/TypeScript file using Document, Paragraph, TextRun components
3. Export as .docx using `Packer.toBuffer()`

---

## Editing an Existing Word Document

**MANDATORY**: Read `ooxml.md` (~600 lines) completely from start to finish.

### Workflow
1. Read the complete `ooxml.md` file (never set range limits)
2. Unpack the document: `python ooxml/scripts/unpack.py <office_file> <output_directory>`
3. Create and run a Python script using the Document library
4. Pack the final document: `python ooxml/scripts/pack.py <input_directory> <office_file>`

The Document library provides both high-level methods for common operations and direct DOM access for complex scenarios.

---

## Redlining Workflow for Document Review

This workflow allows comprehensive tracked changes using markdown before implementation in OOXML.

### Key Principles
- **Critical**: Implement ALL changes systematically for complete tracked changes
- **Batching Strategy**: Group 3-10 related changes per batch for manageable debugging
- **Minimal Edits**: Only mark text that actually changes
  - Break replacements into: [unchanged text] + [deletion] + [insertion] + [unchanged text]
  - Preserve original run's RSID for unchanged text

### Bad Example
```xml
<w:del><w:r><w:delText>The term is 30 days.</w:delText></w:r></w:del><w:ins><w:r><w:t>The term is 60 days.</w:t></w:r></w:ins>
```

### Good Example
```xml
<w:r w:rsidR="00AB12CD"><w:t>The term is </w:t></w:r><w:del><w:r><w:delText>30</w:delText></w:r></w:del><w:ins><w:r><w:t>60</w:t></w:r></w:ins><w:r w:rsidR="00AB12CD"><w:t> days.</w:t></w:r>
```

### Tracked Changes Workflow

1. **Get markdown representation**:
   ```bash
   pandoc --track-changes=all path-to-file.docx -o current.md
   ```

2. **Identify and group changes**: Organize into logical batches (by section, type, or proximity)

3. **Read documentation and unpack**:
   - Read complete `ooxml.md` file
   - Unpack: `python ooxml/scripts/unpack.py <file.docx> <dir>`
   - Note the suggested RSID from unpack script

4. **Implement changes in batches**:
   - Group 3-10 related changes together
   - Use `get_node` to find nodes, implement changes, then `doc.save()`
   - Always grep `word/document.xml` before writing scripts to verify current content

5. **Pack the document**:
   ```bash
   python ooxml/scripts/pack.py unpacked reviewed-document.docx
   ```

6. **Final verification**:
   ```bash
   pandoc --track-changes=all reviewed-document.docx -o verification.md
   grep "original phrase" verification.md # Should NOT find it
   grep "replacement phrase" verification.md # Should find it
   ```

---

## Converting Documents to Images

### Two-Step Process

1. **Convert DOCX to PDF**:
   ```bash
   soffice --headless --convert-to pdf document.docx
   ```

2. **Convert PDF pages to JPEG**:
   ```bash
   pdftoppm -jpeg -r 150 document.pdf page
   ```
   Creates: `page-1.jpg`, `page-2.jpg`, etc.

### Options
- `-r 150`: Resolution in DPI (adjust for quality/size balance)
- `-jpeg`: JPEG format (use `-png` for PNG)
- `-f N`: First page to convert
- `-l N`: Last page to convert

### Example for specific range
```bash
pdftoppm -jpeg -r 150 -f 2 -l 5 document.pdf page  # Converts only pages 2-5
```

---

## Code Style Guidelines

When generating code for DOCX operations:
- Write concise code
- Avoid verbose variable names and redundant operations
- Avoid unnecessary print statements

---

## Dependencies

Install required dependencies if not available:

```bash
sudo apt-get install pandoc              # Text extraction
npm install -g docx                      # Creating new documents
sudo apt-get install libreoffice         # PDF conversion
sudo apt-get install poppler-utils       # PDF to image conversion
pip install defusedxml                   # Secure XML parsing
```
