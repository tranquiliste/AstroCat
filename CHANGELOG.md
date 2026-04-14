# Changelog

All notable changes to this project are documented in this file.

## [1.3.0-beta] - 2026-04-14
### Added
- Explicit constellation metadata across supported catalogs
- Localized constellation display in object details, shown as `Latin name (localized name)`
- Dedicated constellation locale resources for supported UI languages

### Changed
- Harmonized catalog terminology by translating remaining French catalog labels and metadata into English
- Refined the main user interface with a cleaner dark theme, improved spacing, and more consistent rounded components
- Reworked the detail view layout to give more prominence to the main image
- Improved the overall presentation of the catalog gallery and object detail panels

## [1.2.0-beta] - 2026-04-13
### Added
- New << / >> toggle in the photo view to hide or restore thumbnails and the description panel
- Translated tooltips for the photo focus toggle in all supported locales

### Changed
- Improved the appearance of the photo focus toggle with a dedicated chevron icon

### Fixed
- IC catalog image path could disappear from settings after restarting the application

## [1.1.1-beta] - 2026-04-13
### Fixed
- i18n locale files not found at runtime in frozen build (PyInstaller)
- All three platform specs (Windows, macOS, Linux) updated to include `app/locales`

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
