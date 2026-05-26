---
name: crawl4ai-knowledge-base
description: >-
  Εξαγωγή οικονομικών και επιχειρηματικών πληροφοριών από websites χρησιμοποιώντας crawl4ai με LLM extraction. Δημιουργεί Knowledge Base σε Markdown format.
---

---
name: crawl4ai-knowledge-base
description: Extract business/financial information from websites using crawl4ai deep crawling with LLM extraction. Creates comprehensive Knowledge Base in Markdown.
triggers:
  - web scraping
  - knowledge base extraction
  - business info extraction
  - crawl4ai
  - site analysis
  - οικονομικές πληροφορίες
  - εξαγωγή δεδομένων
---

# Crawl4AI Knowledge Base Extractor

Εξαγωγή ολοκληρωμένων επιχειρηματικών πληροφοριών από websites χρησιμοποιώντας deep crawling και LLM-based extraction.

## Προαπαιτούμενα

```bash
pip install crawl4ai openai pydantic python-dotenv
```

## Χρήση

### Βασική χρήση
```python
from scripts.crawl_kb import create_knowledge_base
import asyncio

urls = ["https://example.com"]
asyncio.run(create_knowledge_base(urls))
```

### Command line
```bash
python scripts/crawl_kb.py https://example.com https://another-site.gr
```

## Τι εξάγει

- **Company Overview**: Εταιρική περιγραφή, ιστορία, αξίες
- **Products/Services/Amenities**: Προϊόντα, υπηρεσίες, παροχές (λεπτομερώς)
- **Contact**: Στοιχεία επικοινωνίας, διευθύνσεις, τηλέφωνα
- **Policies/FAQ**: Πολιτικές, όροι, συχνές ερωτήσεις
- **Other**: Λοιπές σχετικές πληροφορίες

## Ρυθμίσεις

- **max_depth**: Βάθος crawling (default: 1)
- **max_pages**: Μέγιστος αριθμός σελίδων (default: 25)
- **model_llm**: OpenAI model για extraction (default: gpt-4.1-mini)

## Output

Δημιουργεί αρχείο `{domain}_kb.md` με δομημένο Knowledge Base.

## Environment Variables

```
OPENAI_API_KEY=sk-...
```

## Παράδειγμα Output

```markdown
# 🏨 Knowledge Base: example.com

## Company Overview
Λεπτομερής περιγραφή της εταιρείας...

## Products/Services/Amenities
- Υπηρεσία 1: Περιγραφή
- Υπηρεσία 2: Περιγραφή
...

## Contact
Email: info@example.com
Τηλέφωνο: +30 210 1234567
...
```

