#!/usr/bin/env bash
set -euo pipefail

# Purpose: recreate the local/manual documents/golden_corpus workspace.
# By default this script creates the expected folder layout and prints the
# files that should be downloaded or copied locally. Optional flags can fetch
# open-access web candidates. It does not run by default in CI.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CORPUS_DIR="${ROOT_DIR}/documents/golden_corpus"
DOWNLOAD_OPEN_ACCESS=0
DOWNLOAD_TEXT_CORPUS=0

usage() {
  cat <<'EOF'
Usage:
  scripts/prepare_golden_corpus.sh [options]

Options:
  --download-open-access   Download open-access arXiv PDF/source candidates.
  --download-text-corpus   Download Olivetti text/annotation/README candidates.
  -h, --help               Show this help.

This prepares a local/manual corpus under documents/golden_corpus. Default CI
does not read from this directory.
EOF
}

download_file() {
  local url="$1"
  local target="$2"

  if [[ -f "${target}" ]]; then
    echo "exists: ${target}"
    return
  fi

  echo "download: ${url}"
  curl -fL --retry 3 --retry-delay 2 -o "${target}" "${url}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --download-open-access)
      DOWNLOAD_OPEN_ACCESS=1
      ;;
    --download-text-corpus)
      DOWNLOAD_TEXT_CORPUS=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

mkdir -p \
  "${CORPUS_DIR}/checks" \
  "${CORPUS_DIR}/markdown" \
  "${CORPUS_DIR}/notes" \
  "${CORPUS_DIR}/ocr" \
  "${CORPUS_DIR}/patents_uploaded" \
  "${CORPUS_DIR}/pdf" \
  "${CORPUS_DIR}/source_bundles" \
  "${CORPUS_DIR}/text"

touch \
  "${CORPUS_DIR}/source_bundles/.gitkeep" \
  "${CORPUS_DIR}/text/.gitkeep"

if [[ "${DOWNLOAD_OPEN_ACCESS}" -eq 1 ]]; then
  command -v curl >/dev/null || {
    echo "curl is required for --download-open-access" >&2
    exit 1
  }

  download_file "https://arxiv.org/pdf/2111.01037" \
    "${CORPUS_DIR}/pdf/sectioned-paper.pdf"
  download_file "https://arxiv.org/e-print/2111.01037" \
    "${CORPUS_DIR}/source_bundles/sectioned-paper-source.tar"

  download_file "https://arxiv.org/pdf/1806.03173" \
    "${CORPUS_DIR}/pdf/table-heavy.pdf"
  download_file "https://arxiv.org/e-print/1806.03173" \
    "${CORPUS_DIR}/source_bundles/table-heavy-source.tar"

  download_file "https://arxiv.org/pdf/1704.06526" \
    "${CORPUS_DIR}/pdf/figure-caption.pdf"

  download_file "https://arxiv.org/pdf/2003.13388" \
    "${CORPUS_DIR}/pdf/chemistry-ml-latex-paper.pdf"
  download_file "https://arxiv.org/e-print/2003.13388" \
    "${CORPUS_DIR}/source_bundles/chemistry-ml-latex-source.tar"
fi

if [[ "${DOWNLOAD_TEXT_CORPUS}" -eq 1 ]]; then
  command -v curl >/dev/null || {
    echo "curl is required for --download-text-corpus" >&2
    exit 1
  }

  download_file \
    "https://raw.githubusercontent.com/olivettigroup/annotated-materials-syntheses/master/README.md" \
    "${CORPUS_DIR}/markdown/dataset-readme.md"
  download_file \
    "https://raw.githubusercontent.com/olivettigroup/annotated-materials-syntheses/master/data/101002adma200903953.txt" \
    "${CORPUS_DIR}/text/materials-synthesis-procedure.txt"
  download_file \
    "https://raw.githubusercontent.com/olivettigroup/annotated-materials-syntheses/master/data/101002adma200903953.ann" \
    "${CORPUS_DIR}/text/materials-synthesis-annotation.ann"
  download_file \
    "https://raw.githubusercontent.com/olivettigroup/annotated-materials-syntheses/master/ent2count-sorted.txt" \
    "${CORPUS_DIR}/text/entity-counts.txt"
fi

cat <<'EOF'
Golden corpus workspace prepared.

This directory is for local/manual evaluation only:
  documents/golden_corpus/

Default tests use:
  tests/fixtures/

Recommended local files:

  documents/golden_corpus/pdf/sectioned-paper.pdf
    Source: https://arxiv.org/pdf/2111.01037

  documents/golden_corpus/pdf/table-heavy.pdf
    Source: https://arxiv.org/pdf/1806.03173

  documents/golden_corpus/pdf/figure-caption.pdf
    Source: https://arxiv.org/pdf/1704.06526

  documents/golden_corpus/pdf/chemistry-ml-latex-paper.pdf
    Source: https://arxiv.org/pdf/2003.13388

  documents/golden_corpus/markdown/dataset-readme.md
  documents/golden_corpus/text/materials-synthesis-procedure.txt
  documents/golden_corpus/text/materials-synthesis-annotation.ann
    Source: Olivetti Group annotated materials syntheses repository.

  documents/golden_corpus/pdf/chemistry-heavy-si.pdf
    Source: user/local supporting-information PDF; verify redistribution terms.

  documents/golden_corpus/pdf/patent-drawings.pdf
    Source: local/user patent PDF, formerly US9941441.pdf.

  documents/golden_corpus/pdf/patent-chemistry.pdf
    Source: local/user patent PDF, formerly US11370944.pdf.

  documents/golden_corpus/pdf/patent-ocr-stress.pdf
    Source: local/user patent PDF, formerly US11845885.pdf.

  documents/golden_corpus/ocr/TestOCR.pdf
  documents/golden_corpus/ocr/US2764565.pdf
    Existing OCR-text-layer controls.

  documents/golden_corpus/ocr/*_from_png.pdf
    PNG round-trip, image-only variants for future OCR work.

See also:
  documents/golden_corpus/golden_corpus_manifest.md
  documents/golden_corpus/checks/expected_features.yaml

Optional downloads:
  scripts/prepare_golden_corpus.sh --download-open-access
  scripts/prepare_golden_corpus.sh --download-text-corpus

Tip:
  Put machine-specific copy/download commands in:
    documents/recreate_golden_corpus.local.sh
  That file is intentionally ignored by Git.
EOF
