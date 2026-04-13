# Changelog

All notable changes to this project are documented in this file.

## [1.1.0-beta] - 2026-04-13
### Added
- Multi-language support across the user interface
- New translations available for English, French, German, Spanish, and Italian
- In-app language selection
- Locale fallback mechanism to English when a translation key is missing
- Internal i18n audit tooling to detect missing or inconsistent translation keys

### Changed
- Reorganized text resources to simplify translation maintenance
- Standardized labels and user-facing messages across the app
- Improved clarity on several screens with more explicit wording

### Fixed
- Incomplete or ambiguous labels in multiple views
- Punctuation and terminology consistency issues
- Stability of localized text loading at startup

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
