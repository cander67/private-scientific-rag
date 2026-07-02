# Backend Package

The backend package contains the FastAPI app, configuration, database wiring, repository metadata, and future RAG services.

Module boundaries:

- `api/`: FastAPI application and routes.
- `core/`: settings and shared application infrastructure.
- `db/`: SQLAlchemy base, engine, and session wiring.
- `repositories/`: repository SQLAlchemy models, Pydantic settings/manifest schemas, and reproducibility service logic.
- `services/`: local service checks and future domain services.
- `ingestion/`: document upload models, PDF parser fallback chain, parser/chunker service, source file storage, and provenance schemas.
- Ingestion keeps original source files, parsed artifacts, chunks, and provenance metadata distinct.

Current API surface:

- `GET /health`: local app and dependency health check.
- `GET /repositories/default`: creates or returns the default repository with validated settings.
- `GET /repositories/{repository_id}/settings`: loads repository settings.
- `PUT /repositories/{repository_id}/settings`: validates and saves repository settings.
- `GET /repositories/{repository_id}/manifest`: exports a reproducibility manifest and stores a snapshot.
- `POST /repositories/recreate/validate`: reports missing source files, missing models, and incompatible settings before recreate work begins.
- `POST /repositories/{repository_id}/documents`: uploads and parses a local document.
- `GET /repositories/{repository_id}/documents`: lists uploaded documents.
- `GET /repositories/{repository_id}/documents/{document_id}`: inspects parsed chunks and provenance.
- `GET /repositories/{repository_id}/documents/{document_id}/versions/{version_id}/page-images/{page}`: serves generated PDF page thumbnails for source inspection.
- `POST /repositories/{repository_id}/documents/{document_id}/reprocess`: reparses the stored source file.
- `DELETE /repositories/{repository_id}/documents/{document_id}`: deletes a document and derived chunks.

PRD2 owns repository-aware settings and reproducibility. PRD3 adds local document ingestion and source inspection for PDFs, text, markdown, annotations, and user-uploaded patent PDFs. PDF parsing tries `pypdf`, then PyMuPDF, gates image-only/no-native-text pages as `needs_ocr`, then uses Docling and a conservative built-in fallback for remaining non-image PDFs. PRD3 intentionally does not run a full OCR pipeline; PRD13 owns OCRmyPDF/Tesseract and fallback OCR. Bulk patent-data feeds and multi-jurisdiction patent parsing are deferred to PRD12.
