# Golden Corpus Manifest v1 — Chemistry and Materials Science

Generated: 2026-06-30  
Versioned: 2026-07-01  
Project: `private_rag` / private scientific RAG parser + retrieval test corpus  
Focus: chemistry, materials science, patents, scientific PDFs, supporting information, text corpora, and markdown metadata.

> This manifest is intended as a practical test set, not a legal redistribution package. Keep source URLs and access dates with each file, and verify license/reuse terms before committing third-party files to a public repository.

---

## 1. Corpus purpose

This golden corpus should exercise the parts of the private scientific RAG system that are most likely to fail on real chemistry and materials-science research documents:

- section detection in journal articles and preprints;
- extraction of page, section, table, figure, caption, and chunk provenance;
- text extraction from user-uploaded patent PDFs, including front matter, classifications, claims, examples, and drawing sheets;
- table-heavy technical PDFs;
- figure-heavy PDFs with scientific captions;
- chemistry-heavy supporting information with reaction schemes, structures, spectra, and analytical data;
- OCR fallback for image-only or poorly parsed PDFs;
- plain-text scientific procedures;
- markdown documentation and dataset metadata;
- source-bundle workflows for scientific papers.

Bulk patent downloads, raw patent XML/SGML/APS/TIFF feeds, and multi-jurisdiction patent-data normalization are intentionally deferred to a later PRD. Patent coverage in PRD3 is limited to PDFs uploaded by the user.

Recommended initial size: 10–20 files for smoke tests, then expand to 30–50 files only after ingestion, parsing, chunking, retrieval, citation rendering, and export snapshots are stable.

---

## 2. Suggested folder layout

```text
golden_corpus/
  golden_corpus_manifest.md
  golden_corpus_manifest_v1.md
  pdf/
    sectioned-paper.pdf
    table-heavy.pdf
    figure-caption.pdf
    patent-drawings.pdf
    patent-chemistry.pdf
    patent-ocr-stress.pdf
    chemistry-heavy-si.pdf
    chemistry-ml-latex-paper.pdf
  source_bundles/
    sectioned-paper-source.tar
    table-heavy-source.tar
    chemistry-ml-latex-source.tar
  text/
    materials-synthesis-procedure.txt
    materials-synthesis-annotation.ann
    corpus-counts.txt
  markdown/
    dataset-readme.md
    corpus-notes.md
  patents_uploaded/
    README.md
  notes/
    deferred_patent_bulk_data.md
  checks/
    expected_features.yaml
    retrieval_questions.md
```

Keep the original downloaded file names in a source manifest if you rename files for fixture consistency.

---

## 3. Summary mapping

| Manifest slot | Recommended fixture | Status | Why it belongs |
|---|---|---:|---|
| `sectioned-paper.pdf` | arXiv: Interpretable and Explainable ML for Materials Science and Chemistry | Web candidate | Strong section hierarchy, review-style organization, chemistry/materials focus, figures and captions. |
| `table-heavy.pdf` | arXiv: Computational 2D Materials Database | Web candidate | Long PDF with many sections, equations, tables, appendices, and database-style metadata. |
| `figure-caption.pdf` | arXiv/Nature Materials manuscript: Liquid Metal–Organic Frameworks | Web candidate | Materials chemistry paper with structural figures, PDF/experimental interpretation, and dense captions. |
| `patent-drawings.pdf` | `US9941441.pdf` | Existing local file | Patent with photovoltaic module attachment-bracket drawings and claims. |
| `patent-chemistry.pdf` | `US11370944.pdf` | Existing local file | Patent with adhesive composition, chemistry terminology, classifications, and no drawings. |
| `patent-ocr-stress.pdf` | `US11845885.pdf` | Existing local file | Image-only parsed patent in current preprocessing; useful OCR/page-image stress test. |
| `patent-bulk-download` | Deferred to future PRD | Deferred | Bulk downloads, archives, raw patent feeds, and cross-jurisdiction normalization are outside PRD3. |
| `chemistry-heavy.pdf` | `ol401035t_si_001.pdf` | Existing local file | Supporting information with synthesis, chemical structures, NMR, MS, XPS, AFM, ellipsometry, and adhesion tests. |
| `chemistry-heavy-latex` | arXiv: ML4Chem or DScribe TeX source bundle | Web candidate | Tests LaTeX/e-print extraction, equations, references, captions, and code-like scientific prose. |
| `chemistry-heavy.txt` | Olivetti annotated materials synthesis `.txt` file | Web candidate | Plain-text materials synthesis procedures with chemistry operations and precursor/product language. |
| `plain-text.txt` | Olivetti corpus count/stat files or one synthesis procedure `.txt` | Web candidate | Tests non-PDF ingestion, short scientific text, and metadata-light files. |
| `markdown.md` | Olivetti annotated-materials-syntheses `README.md` | Web candidate | Tests markdown ingestion, headings, links, dataset documentation, and citation to non-PDF sources. |
| `annotation-pair.ann` | Olivetti BRAT `.ann` file paired with `.txt` | New section | Tests auxiliary scientific annotation formats and source-file linking. |

---

## 4. Original manifest slots, revised

### sectioned-paper.pdf

- **Type:** Open-access arXiv PDF; review/conspectus-style chemistry and materials-science article.
- **Recommended source:** *Interpretable and Explainable Machine Learning for Materials Science and Chemistry*, arXiv:2111.01037.
- **Download targets:**
  - PDF: `https://arxiv.org/pdf/2111.01037`
  - Source bundle: `https://arxiv.org/e-print/2111.01037`
  - Landing page: `https://arxiv.org/abs/2111.01037`
- **Expected features:**
  - clear title/authors/abstract;
  - section headings and subsections;
  - figures with captions;
  - references;
  - chemistry/materials vocabulary mixed with machine-learning terminology.
- **Pages to inspect:**
  - Page 1: title, abstract/conspectus, introduction.
  - Pages around Figure 1: caption and body-reference matching.
  - Final pages: references and possible section-boundary edge cases.
- **Known quirks:**
  - arXiv extraction can mix captions and body text;
  - review articles may include long paragraphs that challenge chunk-size defaults;
  - TeX source may provide better section/caption structure than PDF text extraction.
- **Evaluation checks:**
  - Retrieve the abstract and cite page 1.
  - Retrieve a named figure caption and cite its page.
  - Ask for a section-specific summary and confirm that citations do not come only from the abstract.

---

### table-heavy.pdf

- **Type:** Open-access arXiv PDF; database/methods materials-science paper.
- **Recommended source:** *The Computational 2D Materials Database: High-throughput modeling and discovery of atomically thin crystals*, arXiv:1806.03173.
- **Download targets:**
  - PDF: `https://arxiv.org/pdf/1806.03173`
  - Source bundle: `https://arxiv.org/e-print/1806.03173`
  - Landing page: `https://arxiv.org/abs/1806.03173`
- **Expected features:**
  - long technical document;
  - many tables;
  - table captions and table references in the body;
  - equations, formulas, appendices, and database/property terminology;
  - materials identifiers and computed-property vocabulary.
- **Pages to inspect:**
  - Page 1: abstract and database description.
  - Early pages: table of contents and section hierarchy.
  - Representative table pages: one small table, one multi-row table, one appendix table.
- **Known quirks:**
  - table extraction may split rows or merge columns;
  - references to “Table 1,” “Table 2,” etc. should link to the table/caption, not only body text;
  - long PDFs test page mapping and chunk provenance.
- **Evaluation checks:**
  - Retrieve a table caption by table number.
  - Ask “what properties does the database include?” and confirm citations include the database-description section and not only the abstract.
  - Inspect whether table chunks retain enough row/column context to be useful.

---

### figure-caption.pdf

- **Type:** Open-access arXiv PDF; materials chemistry paper with dense scientific figures.
- **Recommended source:** *Liquid Metal–Organic Frameworks*, arXiv:1704.06526.
- **Download targets:**
  - PDF: `https://arxiv.org/pdf/1704.06526`
  - Landing page: `https://arxiv.org/abs/1704.06526`
- **Expected features:**
  - structural figures;
  - experimental interpretation;
  - X-ray/neutron pair distribution function terminology;
  - molecular dynamics/modeling references;
  - figure captions with panel labels.
- **Pages to inspect:**
  - Page 1: title, abstract, publication note.
  - Pages containing Figures 1–3: captions, panel labels, body references.
  - Supplemental/reference pages if available.
- **Known quirks:**
  - captions may be separated from figure panels;
  - captions may include symbols, panel labels, and chemical abbreviations;
  - body text may refer to figure panels without repeating the key experimental details.
- **Evaluation checks:**
  - Retrieve “Figure 3” or another named figure.
  - Ask what the figure demonstrates and require citation to the caption page.
  - Confirm the system distinguishes caption text from surrounding body paragraphs.

---

### patent-drawings.pdf

- **Type:** Existing local patent PDF.
- **Local source:** `US9941441.pdf`
- **Suggested fixture name:** `pdf/patent-drawings.pdf`
- **Document title:** *Structural bonding compositions and attachment brackets, and their use in photovoltaic solar modules*.
- **Expected features:**
  - patent front matter;
  - abstract;
  - CPC/intellectual-property metadata;
  - claims;
  - multiple drawing sheets;
  - figure labels and numbered components;
  - photovoltaic-module and adhesive-bonding terminology.
- **Pages to inspect:**
  - Page 1: front matter, abstract, title, CPC metadata.
  - Pages 3–6: drawing sheets and figure labels.
  - First description page after drawing sheets.
  - Claims pages near the end.
- **Known quirks:**
  - OCR may emit repeated characters from drawing regions;
  - patent drawing sheets may have little natural-language text but are still important assets;
  - page-image citation cards should preserve drawing-sheet previews.
- **Evaluation checks:**
  - Retrieve the patent title and abstract.
  - Retrieve drawing-sheet pages when asked about figures.
  - Retrieve claims separately from the abstract/description.

---

### patent-chemistry.pdf

- **Type:** Existing local patent PDF.
- **Local source:** `US11370944.pdf`
- **Suggested fixture name:** `pdf/patent-chemistry.pdf`
- **Document title:** *UV Curable Epoxy/Acrylate Adhesive Composition*.
- **Expected features:**
  - patent front matter;
  - adhesive composition abstract;
  - chemical composition terms;
  - examples;
  - claims;
  - CPC classifications;
  - no drawings.
- **Pages to inspect:**
  - Page 1: front matter and abstract.
  - Pages 2–4: field/background/summary and definitions.
  - Example/composition pages.
  - Claims pages near the end.
- **Known quirks:**
  - `C08` and `C09J` may be misread as `CO8` / `CO9J`;
  - formulas and parenthetical chemistry terms may be split by line breaks;
  - no drawing pages means patent-asset handling should not assume drawings exist.
- **Evaluation checks:**
  - Ask “what components are in the adhesive composition?”
  - Ask for examples or claims and confirm the answer cites the appropriate section/page.
  - Verify patent metadata extraction does not rely on drawings.

---

### patent-bulk-download

- **Type:** Deferred future workflow.
- **Reason deferred:** PRD3 should support user-uploaded patent PDFs only. Bulk patent downloads and raw patent-data parsing need a separate design for source APIs, archive provenance, jurisdiction-specific formats, rate limits, and metadata normalization.
- **Future PRD:** `prds/12-bulk-patent-data-integration.md`.
- **Suggested note file:** `notes/deferred_patent_bulk_data.md`.

---

### chemistry-heavy.pdf

- **Type:** Existing local chemistry supporting information PDF.
- **Local source:** `ol401035t_si_001.pdf`
- **Suggested fixture name:** `pdf/chemistry-heavy-si.pdf`
- **Document title:** *Supporting Information — Quadruply Hydrogen Bonding Modules as Highly Selective Nanoscale Adhesive Agents*.
- **Expected features:**
  - synthetic procedures;
  - reaction schemes and chemical structures;
  - NMR and HR-MS analytical data;
  - contact-angle measurements;
  - XPS;
  - AFM;
  - MALDI-TOF-MS;
  - ellipsometry;
  - adhesion/lap-shear measurements.
- **Pages to inspect:**
  - S1/Table of Contents: confirms section map.
  - S2–S7: synthetic procedures and chemical structures.
  - S8–S20: NMR spectra.
  - S23–S35: surface-characterization sections.
  - S44: adhesion measurements/reference.
- **Known quirks:**
  - chemical structures are image assets, not text-only content;
  - NMR spectra may be image-dominant;
  - superscripts/subscripts and isotope labels may be parsed inconsistently;
  - “Error! Bookmark not defined.” may appear in extracted text.
- **Evaluation checks:**
  - Retrieve a specific compound procedure.
  - Retrieve an analytical characterization section.
  - Confirm figure/image pages remain inspectable even when text extraction is sparse.

---

### chemistry-heavy-latex

- **Type:** Open-access arXiv source bundle with chemistry/materials content.
- **Recommended primary source:** *ML4Chem: A Machine Learning Package for Chemistry and Materials Science*, arXiv:2003.13388.
- **Alternative source:** *DScribe: Library of descriptors for machine learning in materials science*, arXiv:1904.08875.
- **Download targets:**
  - ML4Chem PDF: `https://arxiv.org/pdf/2003.13388`
  - ML4Chem source: `https://arxiv.org/e-print/2003.13388`
  - DScribe PDF: `https://arxiv.org/pdf/1904.08875`
  - DScribe source: `https://arxiv.org/e-print/1904.08875`
- **Expected features:**
  - LaTeX source extraction;
  - equations and references;
  - figure environments;
  - bibliography files;
  - code-like package/module names;
  - chemistry/materials ML vocabulary.
- **Pages/files to inspect:**
  - Main `.tex` file section headings.
  - Figure environments and captions.
  - Bibliography file.
  - PDF page 1 for abstract.
- **Known quirks:**
  - source bundles may be compressed `.tar` files with nested paths;
  - LaTeX macros may hide section names or equations;
  - PDF and TeX source line/page provenance need separate handling.
- **Evaluation checks:**
  - Compare PDF-extracted headings with TeX-derived headings.
  - Retrieve a figure caption from TeX source and from PDF text.
  - Confirm citations can identify PDF page and source-file location separately.

---

### chemistry-heavy.txt

- **Type:** Plain-text materials synthesis procedure.
- **Recommended source:** Olivetti Group annotated materials syntheses dataset.
- **Suggested sample target:** `data/101002adma200903953.txt`
- **Download targets:**
  - Repository: `https://github.com/olivettigroup/annotated-materials-syntheses`
  - Sample raw text pattern: `https://raw.githubusercontent.com/olivettigroup/annotated-materials-syntheses/master/data/<paper_id>.txt`
- **Expected features:**
  - synthesis procedure text;
  - precursor/material/product/action language;
  - DOI/title metadata at the top of text files;
  - no page numbers;
  - possible pairing with BRAT `.ann` annotations.
- **Pages to inspect:** Not page-based. Inspect line ranges and document-level metadata.
- **Known quirks:**
  - no native page provenance;
  - scientific procedure steps may be short and dense;
  - text and annotations should remain linked by shared base filename.
- **Evaluation checks:**
  - Ask for reagents, operations, conditions, and products.
  - Confirm citations use line/chunk provenance rather than page provenance.
  - Confirm `.txt` and `.ann` files are grouped as related assets.

---

### plain-text.txt

- **Type:** Plain-text corpus statistics or one short scientific procedure.
- **Recommended source:** Olivetti Group annotated materials syntheses dataset.
- **Suggested fixture choices:**
  - one individual synthesis procedure `.txt`;
  - `tok2count-sorted.txt`;
  - `ent2count-sorted.txt`;
  - `etype2count-sorted.txt`.
- **Expected features:**
  - simple plain-text ingestion;
  - no headings or page numbers;
  - short line-oriented data;
  - useful control case for text chunking.
- **Pages to inspect:** Not page-based. Inspect first 50–100 lines.
- **Known quirks:**
  - line-based files may not need semantic chunking;
  - count files may look like data tables but have no explicit delimiter schema;
  - no figure/table/page assets.
- **Evaluation checks:**
  - Confirm ingestion works without PDF parsing.
  - Confirm citations use line ranges or chunk IDs.
  - Confirm file type is not misclassified as markdown or CSV.

---

### markdown.md

- **Type:** Markdown dataset documentation.
- **Recommended source:** Olivetti Group annotated materials syntheses `README.md`.
- **Download target:** `https://raw.githubusercontent.com/olivettigroup/annotated-materials-syntheses/master/README.md`
- **Expected features:**
  - markdown headings;
  - links;
  - dataset description;
  - citation/license notes;
  - file structure documentation.
- **Pages to inspect:** Not page-based. Inspect headings and link targets.
- **Known quirks:**
  - markdown links should be preserved;
  - code-style file names should not be split oddly;
  - citations should point to headings/line ranges, not pages.
- **Evaluation checks:**
  - Ask what files the dataset contains.
  - Ask how `.txt` and `.ann` files relate.
  - Confirm markdown headings become retrievable sections.

---

## 5. Added sections

### patent-ocr-stress.pdf

- **Type:** Existing local image-only or poorly parsed patent PDF.
- **Local source:** `US11845885.pdf`
- **Suggested fixture name:** `pdf/patent-ocr-stress.pdf`
- **Document title visible on page image:** *Dual Stage Structural Bonding Adhesive*.
- **Expected features:**
  - page images with little/no parsed text;
  - patent front matter;
  - abstract visible in image;
  - drawing sheets;
  - OCR fallback requirement.
- **Pages to inspect:**
  - Page 1: title/front matter/abstract visible on rendered page image.
  - Page 2: references and continuation of front matter.
  - Page 3: first drawing sheet.
  - Later pages: claims/description after OCR.
- **Known quirks:**
  - current parser reports no parsed text;
  - useful for deciding when to trigger OCR or page-image inspection;
  - source viewer should still show page thumbnails even when text is absent.
- **Evaluation checks:**
  - Ingestion should mark it as `needs_ocr` or `image_only_pdf`.
  - OCR pipeline should recover at least title, abstract, inventors, and claim headings.
  - Retrieval should not silently ignore the document because parsed text is empty.

---

### annotation-pair.ann

- **Type:** BRAT standoff annotation file paired with a scientific `.txt` file.
- **Recommended source:** Olivetti Group annotated materials syntheses dataset.
- **Suggested sample target:** choose the `.ann` file with the same base name as the selected `.txt` sample, for example `data/101002adma200903953.ann`.
- **Expected features:**
  - entity annotations;
  - relation annotations;
  - offsets into the paired `.txt` file;
  - materials-science synthesis semantics.
- **Pages to inspect:** Not page-based. Inspect first 100 annotation lines and paired text offsets.
- **Known quirks:**
  - offsets can break if text normalization changes;
  - annotations should not be embedded as independent prose chunks without linking to source text;
  - useful for future extraction/evaluation, not necessarily first-pass chat retrieval.
- **Evaluation checks:**
  - Confirm paired `.ann` and `.txt` files share a base ID.
  - Confirm annotations preserve offsets after ingestion.
  - Confirm derived metadata can be attached to text chunks without corrupting citations.

---

### dataset-readme.md

- **Type:** Markdown file documenting a scientific text corpus.
- **Recommended source:** Olivetti Group annotated materials syntheses repository `README.md`.
- **Expected features:**
  - dataset description;
  - citation instructions;
  - license notes;
  - repository layout.
- **Evaluation checks:**
  - Ask “what does this dataset contain?”
  - Ask “how are raw text and annotations stored?”
  - Confirm markdown citations point to line ranges/headings.

---

### corpus-notes.md

- **Type:** Local, hand-authored markdown notes file.
- **Suggested content:** Create this yourself after downloading the corpus.
- **Expected features:**
  - source URLs;
  - access dates;
  - checksum notes;
  - why each file was included;
  - known extraction quirks;
  - expected retrieval questions.
- **Evaluation checks:**
  - Confirm local notes are searchable alongside external documents.
  - Confirm local notes do not override source-document evidence in answer ranking.

---

## 6. Candidate download script

This is intentionally conservative and does not download large USPTO archives automatically.

```bash
mkdir -p golden_corpus/{pdf,source_bundles,text,markdown,patents_uploaded,notes,checks}

# Open-access PDFs and arXiv source bundles
curl -L -o golden_corpus/pdf/sectioned-paper.pdf https://arxiv.org/pdf/2111.01037
curl -L -o golden_corpus/source_bundles/sectioned-paper-source.tar https://arxiv.org/e-print/2111.01037

curl -L -o golden_corpus/pdf/table-heavy.pdf https://arxiv.org/pdf/1806.03173
curl -L -o golden_corpus/source_bundles/table-heavy-source.tar https://arxiv.org/e-print/1806.03173

curl -L -o golden_corpus/pdf/figure-caption.pdf https://arxiv.org/pdf/1704.06526

curl -L -o golden_corpus/pdf/chemistry-ml-latex-paper.pdf https://arxiv.org/pdf/2003.13388
curl -L -o golden_corpus/source_bundles/chemistry-ml-latex-source.tar https://arxiv.org/e-print/2003.13388

# Scientific text + annotation + markdown fixtures
curl -L -o golden_corpus/markdown/dataset-readme.md \
  https://raw.githubusercontent.com/olivettigroup/annotated-materials-syntheses/master/README.md

curl -L -o golden_corpus/text/materials-synthesis-procedure.txt \
  https://raw.githubusercontent.com/olivettigroup/annotated-materials-syntheses/master/data/101002adma200903953.txt

curl -L -o golden_corpus/text/materials-synthesis-annotation.ann \
  https://raw.githubusercontent.com/olivettigroup/annotated-materials-syntheses/master/data/101002adma200903953.ann

curl -L -o golden_corpus/text/entity-counts.txt \
  https://raw.githubusercontent.com/olivettigroup/annotated-materials-syntheses/master/ent2count-sorted.txt
```

Copy the existing local PDFs into `golden_corpus/pdf/` manually:

```bash
cp US9941441.pdf golden_corpus/pdf/patent-drawings.pdf
cp US11370944.pdf golden_corpus/pdf/patent-chemistry.pdf
cp US11845885.pdf golden_corpus/pdf/patent-ocr-stress.pdf
cp ol401035t_si_001.pdf golden_corpus/pdf/chemistry-heavy-si.pdf
```

For bulk patent data, create a deferral note instead of downloading archives in PRD3:

```bash
cat > golden_corpus/notes/deferred_patent_bulk_data.md <<'EOF'
# Deferred patent bulk data notes

Patent coverage in PRD3 is limited to user-uploaded PDFs. Bulk downloads, raw XML/SGML/APS/TIFF feeds, and multi-jurisdiction patent-data parsing are deferred to PRD12.
EOF
```

---

## 7. Expected feature matrix

| Fixture | PDF text | Page images | OCR needed | Tables | Figures | Captions | Chemistry | Patent | Text/MD | Source bundle |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| sectioned-paper.pdf | yes | yes | no | maybe | yes | yes | yes | no | no | yes |
| table-heavy.pdf | yes | yes | no | high | yes | yes | materials | no | no | yes |
| figure-caption.pdf | yes | yes | no | maybe | high | high | materials | no | no | maybe |
| patent-drawings.pdf | yes | yes | maybe | no | high | patent figures | adhesives/PV | yes | no | no |
| patent-chemistry.pdf | yes | yes | maybe | examples | no | no | adhesives | yes | no | no |
| patent-ocr-stress.pdf | no/low | yes | yes | unknown | high | patent figures | adhesives | yes | no | no |
| chemistry-heavy-si.pdf | yes | yes | maybe | analytical | high | mixed | high | no | no | no |
| chemistry-ml-latex-paper.pdf | yes | yes | no | maybe | yes | yes | chemistry/materials ML | no | no | yes |
| materials-synthesis-procedure.txt | no | no | no | no | no | no | high | no | yes | no |
| materials-synthesis-annotation.ann | no | no | no | no | no | no | high metadata | no | yes | no |
| dataset-readme.md | no | no | no | no | no | no | dataset metadata | no | yes | no |

---

## 8. Retrieval and citation smoke-test questions

Use these after ingestion to validate parsing, chunking, ranking, reranking, and citation cards.

1. **Sectioned paper:** “What does the explainable ML paper say are the main uses of interpretable ML in chemistry and materials science?”
2. **Table-heavy paper:** “What is the Computational 2D Materials Database, and what kinds of properties does it include?”
3. **Figure-caption paper:** “What does the MOF liquid paper’s figure about coordination structure show?”
4. **Patent drawings:** “Which figures in the photovoltaic patent show the attachment bracket or module assembly?”
5. **Patent chemistry:** “What components are described in the UV-curable epoxy/acrylate adhesive composition?”
6. **OCR patent:** “Can you identify the title and abstract of the image-only patent?”
7. **Supporting information:** “Find the synthetic procedure and analytical data for one compound in the quadruply hydrogen-bonding module SI.”
8. **Plain text synthesis:** “What operations and materials are described in the selected materials synthesis procedure?”
9. **Markdown:** “What does the annotated materials syntheses dataset contain, and how are `.txt` and `.ann` files organized?”
10. **Provenance:** “For each answer, show page/section/table/figure/chunk provenance where available, and fall back to line/chunk provenance for text and markdown.”

---

## 9. Ingestion metadata to record

At minimum, store the following per source file:

```yaml
source_id:
display_name:
fixture_name:
source_type: pdf | text | markdown | archive | annotation
local_path:
source_url:
landing_page_url:
download_date:
license_or_terms:
sha256:
original_filename:
renamed_fixture_filename:
parser:
parser_version:
ocr_required: true | false | unknown
known_quirks:
expected_features:
  pages:
  sections:
  tables:
  figures:
  captions:
  claims:
  references:
  equations:
  source_bundle:
related_assets:
  - source_id:
    relation: source_tex | paired_annotation | paired_text | source_archive
```

---

## 10. Recommended first pass

1. Ingest the four existing local PDFs first:
   - `US9941441.pdf`
   - `US11370944.pdf`
   - `US11845885.pdf`
   - `ol401035t_si_001.pdf`

2. Add three web PDFs:
   - arXiv:2111.01037 as `sectioned-paper.pdf`
   - arXiv:1806.03173 as `table-heavy.pdf`
   - arXiv:1704.06526 as `figure-caption.pdf`

3. Add three non-PDF files:
   - Olivetti sample `.txt`
   - matching Olivetti `.ann`
   - Olivetti `README.md`

4. Run ingestion and manually inspect:
   - page counts;
   - section maps;
   - table/caption candidates;
   - OCR flags;
   - chunk metadata;
   - citation-card rendering.

5. Only then add arXiv source bundles and USPTO bulk archive tests.
