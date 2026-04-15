# Catalog i18n overlays

Catalog metadata stays in English in `data/*.json`.
Localized `name` and `description` are provided through per-locale overlays.

## Location

- `data/i18n/<locale>/<catalog>.json`
- `<catalog>.json` uses the exact source metadata filename from config:
  - `data/barnard_catalog.json` -> `data/i18n/<locale>/barnard_catalog.json`
  - `data/ngc_catalog.json` -> `data/i18n/<locale>/ngc_catalog.json`
  - `data/solar_system_catalog.json` -> `data/i18n/<locale>/solar_system_catalog.json`

## Overlay format

```json
{
  "B 33": {
    "name": {
      "text": "Nebuleuse de la Tete de Cheval",
      "source_hash": "sha256:..."
    },
    "description": {
      "text": "Description traduite...",
      "source_hash": "sha256:..."
    }
  }
}
```

Rules:

- Object ids must match the base catalog exactly.
- Fields allowed: `name`, `description`.
- Each translated field stores:
  - `text`: localized text
  - `source_hash`: hash of the current English source text
- Runtime uses translation only if `source_hash` matches current base text hash.
- If hash does not match (stale translation), runtime falls back to English.

## Tooling

Audit overlays:

```powershell
python scripts/audit_catalog_i18n.py
python scripts/audit_catalog_i18n.py --strict
```

Create/update one translated entry with correct current `source_hash`:

```powershell
python scripts/upsert_catalog_overlay_entry.py --locale fr --catalog Barnard --object-id "B 33" --field description --text "Description francaise"
```

