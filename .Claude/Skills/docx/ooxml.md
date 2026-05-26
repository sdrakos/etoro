# Office Open XML Technical Reference

This is a comprehensive technical guide for working with Office Open XML (OOXML) documents.

## Main Topics Covered

### 1. **Technical Guidelines**
- **Schema Compliance**: Element ordering, whitespace handling, Unicode escaping
- **Tracked Changes**: Use `<w:del>` and `<w:ins>` tags with `w:author="Claude"`
- **RSIDs**: Must be 8-digit hex values (e.g., `00AB1234`)
- **Images**: Add to `word/media/`, reference in document.xml, set dimensions

### 2. **Document Content Patterns**
Includes XML patterns for:
- **Basic Structure**: `<w:p>` with `<w:r>` and `<w:t>` elements
- **Headings/Styles**: Using `<w:pStyle>` with values like "Title", "Heading2"
- **Text Formatting**: Bold (`<w:b/>`), Italic (`<w:i/>`), Underline (`<w:u>`), Highlight
- **Lists**: Numbered and bulleted with `<w:numPr>` and `<w:ilvl>`
- **Tables**: Complete structure with `<w:tbl>`, `<w:tr>`, `<w:tc>`
- **Layout**: Page breaks, centering, font changes

### 3. **Document Library (Python)**

**Initialization:**
```python
from scripts.document import Document, DocxXMLEditor

doc = Document('unpacked')
# With customization
doc = Document('unpacked', author="John Doe", initials="JD", track_revisions=True)
```

**Creating Tracked Changes:**
- Use `replace_node()` with `<w:del>` and `<w:ins>` tags
- Use `suggest_deletion()` for removing entire elements
- Preserve formatting by extracting `<w:rPr>` from originals

**Adding Comments:**
```python
doc.add_comment(start=node, end=node, text="Comment text")
doc.reply_to_comment(parent_comment_id=0, text="Reply text")
```

**Rejecting Changes:**
```python
doc['word/document.xml'].revert_insertion(ins_element)
doc['word/document.xml'].revert_deletion(del_element)
```

**Inserting Images:**
- Copy to `doc.unpacked_path/word/media/`
- Calculate dimensions in EMUs (English Metric Units)
- Add relationships and content types
- Use full image XML structure with proper namespaces

**Getting Nodes:**
```python
node = doc["word/document.xml"].get_node(tag="w:p", contains="text")
node = doc["word/document.xml"].get_node(tag="w:p", line_number=range(100, 150))
node = doc["word/document.xml"].get_node(tag="w:del", attrs={"w:id": "1"})
```

**Saving:**
```python
doc.save()  # Validates by default
doc.save('output-path')
doc.save(validate=False)  # Skip validation (debugging only)
```

### 4. **Tracked Changes (Redlining)**

**Critical Rules:**
1. Never modify content inside another author's tracked changes
2. Place `<w:del>` and `<w:ins>` at paragraph level containing complete `<w:r>` elements
3. Never nest inside `<w:r>` elements - creates invalid XML

**Patterns:**
- **Text Insertion**: `<w:ins>` with `<w:r><w:t>` content
- **Text Deletion**: `<w:del>` with `<w:r><w:delText>` content
- **Delete Another's Insertion**: Nest `<w:del>` inside their `<w:ins>`
- **Restore Another's Deletion**: Leave their `<w:del>` unchanged, add new `<w:ins>`

## Key Requirements

✓ **CRITICAL**: Use the Document class for all tracked changes
✓ Only mark text that actually changes
✓ Validate Unicode/entity encoding based on file encoding
✓ Auto-generate attributes (w:id, w:date, w:rsidR, w16du:dateUtc, xml:space)
✓ Set PYTHONPATH to docx skill root when running scripts
✓ Add images to temporary unpacked directory, not original
