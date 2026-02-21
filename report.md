# Written Report: AD Document Extraction System

## Approach

My pipeline follows a two-stage architecture: **Local OCR (PaddleOCR) → LLM (text-only)** for extraction, followed by a **deterministic rule-based engine** for applicability evaluation.

The core idea is straightforward — OCR converts the PDF into raw text, the LLM parses that text into structured JSON, and a rule engine checks each aircraft against the parsed data. I chose this over a pure regex/template approach because AD document layouts are not standardized. They vary across issuing authorities, and even within EASA, the formatting shifts between revisions. Any hard-coded parser would need constant patching — it's a maintenance trap.

I also considered a **full multimodal LLM approach** (sending the PDF directly to a vision-capable model), which would be simpler to implement. I opted against it for two reasons: multimodal inference is more expensive per request, and — more critically — vision models tend to underperform on small, dense text like MSN lists, modification numbers, and SB identifiers. These are exactly the fields where precision matters most in AD compliance. A missed serial number or a misread modification ID can lead to an incorrect applicability determination, which in aviation is not an acceptable margin of error.

The OCR + LLM route gives me a layer of control between the document and the model. I can inspect, clean, and restructure the OCR output before the LLM ever sees it — something you simply cannot do when the model is reading the PDF as an image.

## Challenges

The hardest part was not the LLM extraction itself — it was everything around the OCR output.

**OCR post-processing** was the most time-consuming challenge. Raw PaddleOCR output is flat and unordered — it doesn't inherently understand that a block of text is a table header, or that two columns should be read left-to-right rather than top-to-bottom. I had to build post-processing logic to reconstruct reading order, merge fragmented text blocks, and normalize common OCR artifacts (misread characters in identifiers, inconsistent whitespace, broken line continuations). Getting this right was essential because garbage-in from OCR means garbage-out from the LLM, no matter how good the prompt is.

**Schema design and evaluation** was another significant effort. I formulated the extraction output as a strict Pydantic schema (`ADApplicabilityExtraction`) with clearly separated fields for models, MSN constraints, modification constraints, SB constraints, aircraft groups, and required actions. The challenge was handling the many edge cases in AD language — "all MSN except...", "whichever occurs first", recurring vs. one-time compliance, terminating actions that cancel other paragraphs. Each of these required careful schema modeling and explicit extraction rules in the system prompt to prevent the LLM from conflating similar-but-distinct concepts (e.g., Airbus `mod` numbers vs. Service Bulletin identifiers — these look similar but have completely different compliance implications).

**Building the deterministic applicability engine** required translating nuanced AD logic into boolean checks. The three-stage evaluation (model → MSN → modification/SB exclusion) sounds simple, but the devil is in the details: handling inclusive vs. exclusive range bounds, matching modification identifiers with regex while avoiding partial matches, and correctly implementing exclusion logic where an aircraft is initially in-scope but exempted by an already-embodied mod or SB.

## Limitations

There are several areas where this approach can fall short:

**Layout-dependent information loss.** When OCR flattens a PDF into text, spatial relationships (table structures, column alignments, indentation hierarchies) are partially lost. For most AD paragraphs this is manageable, but for complex multi-column tables — like group definitions that map models to MSN ranges — the flattened text can be ambiguous. A multimodal model would handle these cases better since it can "see" the table structure visually.

**LLM extraction is not deterministic.** Even with a strict schema and detailed prompt, the LLM can still occasionally misclassify a field, hallucinate a value, or miss a constraint. This is mitigated by the Pydantic validation layer (malformed output is rejected), but subtle errors — like placing a mod number in the SB field — can slip through if the prompt guardrails aren't specific enough.

**GPU bottleneck in the current setup.** The OCR stage runs on a 4GB VRAM laptop GPU, which is a practical limitation. Processing speed is slower than it would be on a dedicated GPU with more CUDA cores — in production, this would need to be addressed with better hardware or a batched processing queue.

**With more time, I would:**
- Add a confidence scoring layer — have the LLM output confidence levels per extracted field, then flag low-confidence extractions for human review.
- Build an automated evaluation pipeline that compares LLM extraction output against a ground-truth dataset of manually parsed ADs, measuring field-level precision and recall.
- Experiment with a hybrid approach — use OCR + LLM as the primary path, but fall back to multimodal extraction for documents where OCR post-processing detects likely table structures that would benefit from visual understanding.

## Trade-offs

**Why LLM?** Because AD documents are written in natural language with enough variation that deterministic parsing (regex, template matching) is fragile. The LLM absorbs the ambiguity — it can handle paraphrased compliance language, varying section orderings, and inconsistent formatting without breaking. The trade-off is cost and non-determinism, but for this use case, the flexibility outweighs the risk, especially when paired with schema validation.

**Why OCR + text-only LLM over a full multimodal (VLM) approach?** Three reasons: cost, precision, and control. Text-only inference is cheaper. OCR engines are purpose-built for text recognition and outperform vision models on small/dense identifiers. And the OCR intermediate step gives me a post-processing hook — I can clean, validate, and restructure the text before the LLM processes it. With a VLM, the model is a black box between PDF-in and JSON-out; I have no opportunity to intervene when the document is messy.

That said, VLMs win on simplicity and layout understanding. If cost were not a constraint and the documents were consistently well-formatted, a multimodal approach would be a perfectly valid — and arguably simpler — choice. The right answer depends on the production context: how many ADs you're processing, how often, and how much tolerance you have for per-request cost vs. pipeline complexity.