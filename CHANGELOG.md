# Changelog

All notable changes to this project are documented in this file.

## [1.0.0-beta] - 2026-04-12
### Added
- New catalogs (including LBN, Sh2, VdB, and others)
- Notes migration from AstroCatalogueViewer
- Migration summary dialog with copy-to-clipboard support

### Changed
- Image notes are now stored in `photo_notes.json`
- Welcome dialog content updated for AstroCat fork context

### Fixed
- Migration destination path alignment with AstroCat config location
- Duplicate migration behavior for image notes (existing notes are ignored)
- Migration ignored-note counters in summary output
- Migration summary readability on dark themes

### Migration
- Legacy notes can be imported from AstroCatalogueViewer paths
- Existing destination notes are preserved and reported as ignored
- Migration has been tested against AstroCatalogueViewer v3.0-beta
- Compatibility with earlier, different, or future AstroCatalogueViewer versions is not guaranteed
