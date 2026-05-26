# DOCX Library Tutorial - Complete Guide

This is a comprehensive tutorial for generating `.docx` files with JavaScript/TypeScript using the `docx` library.

## Quick Start

```javascript
const { Document, Packer, Paragraph, TextRun } = require('docx');

const doc = new Document({
  sections: [{
    children: [/* content */]
  }]
});

// Node.js
Packer.toBuffer(doc).then(buffer => fs.writeFileSync("doc.docx", buffer));

// Browser
Packer.toBlob(doc).then(blob => { /* download logic */ });
```

## Key Sections Covered

### 1. **Text & Formatting**
- Use **separate Paragraph elements** for line breaks (never `\n`)
- TextRun supports: bold, italics, underline, color, highlighting, strikethrough, super/subscript, small caps
- SymbolRun for special characters (bullets, copyright, etc.)

### 2. **Styles & Professional Formatting**
- Override built-in heading styles using exact IDs: `"Heading1"`, `"Heading2"`, etc.
- Set `outlineLevel` for Table of Contents (0 for H1, 1 for H2, etc.)
- Define custom paragraph and character styles
- Use Arial as default font for universal compatibility

### 3. **Lists (CRITICAL RULES)**
- **NEVER use unicode bullets** — always use proper numbering configuration with `LevelFormat.BULLET`
- Same reference = continues numbering; different reference = restarts at 1
- Example:
```javascript
numbering: { reference: "bullet-list", level: 0 }
```

### 4. **Tables**
- **Set `columnWidths` array + individual cell widths** for compatibility
- Apply borders to TableCell, not Table
- Use `ShadingType.CLEAR` (never SOLID) for cell colors
- Set table `margins` once at table level
- Measurements in DXA (1440 = 1 inch)

### 5. **Links & Navigation**
- Use `ExternalHyperlink` for URLs
- Use `InternalHyperlink` + bookmarks for internal navigation
- `TableOfContents` requires HeadingLevel styles (don't mix with custom styles)

### 6. **Images & Media**
- **CRITICAL: ImageRun requires `type` parameter** (png, jpg, jpeg, gif, bmp, svg)
- Include complete altText with title, description, and name

### 7. **Page Setup**
- Margins & page orientation in properties
- Headers/Footers with pagination support
- Page numbers: `PageNumber.CURRENT` and `PageNumber.TOTAL_PAGES`

## ⚠️ Critical Issues to Avoid

| Issue | ❌ WRONG | ✅ CORRECT |
|-------|---------|-----------|
| Line breaks | `new TextRun("Line 1\nLine 2")` | Two `Paragraph` elements |
| Page breaks | `new PageBreak()` | `new Paragraph({ children: [new PageBreak()] })` |
| Bullets | Unicode `"•"` or `SymbolRun` | `LevelFormat.BULLET` constant |
| TOC with styles | `heading: HeadingLevel.HEADING_1, style: "custom"` | `heading: HeadingLevel.HEADING_1` only |
| Table shading | `ShadingType.SOLID` | `ShadingType.CLEAR` |
| Images | No `type` parameter | Always specify: `type: "png"` |

## Common Units

- **1440 DXA** = 1 inch
- **Letter width with 1" margins** = 9360 DXA
- **Font sizes** in half-points (24 = 12pt)

## Professional Recommendations

- Default font: **Arial** (most universally supported)
- Font combinations: Arial + Arial, or Times New Roman + Arial
- Always set `styles.default.document.run.font`
- Establish visual hierarchy with consistent spacing and sizing
