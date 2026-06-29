# Public Repository Checklist

Complete before the first public commit and before creating the GitHub repo.

- [x] Confirm repository name and GitHub owner: `cander67/private-scientific-rag`.
- [x] Confirm license: MIT.
- [ ] Keep `.env` untracked.
- [ ] Keep `example_code/` untracked.
- [ ] Keep private documents, generated indexes, exports, logs, caches, model files, and Qdrant storage untracked.
- [ ] Review `.env.example` for placeholders only.
- [ ] Run a staged secret sweep before first commit.
- [ ] Confirm CI does not require private secrets.
- [ ] Confirm README does not mention private paths, private documents, or personal credentials.

Suggested staged checks before first commit:

```bash
git add -A
git ls-files --cached | grep -E '(^|/)\.env$|^example_code/|^data/|^models/|^exports/|^logs/|^cache/|^\.qdrant/' || echo "tracked paths clean"
git grep -nI -i 'api[_-]key\|pass[_-]word\|private[ _-]key\|begin[ _-]rsa\|auth[_-]token' --cached || echo "content sweep clean"
```
