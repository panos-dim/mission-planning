# Mission Planning Web App

The primary setup and developer workflow now live in [`README.md`](./README.md).

Short version:

```bash
make install
make dev
```

Then open [http://localhost:3000](http://localhost:3000).

Key notes:

- Backend runs on `http://localhost:8000`
- `./run_dev.sh` uses `.venv/bin/python` automatically when available
- Frontend API types are regenerated from the live backend schema during startup
- Use `make release-gate` for the repo-level verification workflow
