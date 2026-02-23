# POCS Internationalization (i18n)

This directory contains translation files for POCS user-facing messages.

## Supported Languages

- **English (en)**: Default language
- **Spanish (es)**: ¡Español! 🌎
- **Japanese (ja)**: 日本語 🗾

## Directory Structure

```
locale/
├── README.md                          # This file
├── messages.pot                       # Template file (all messages)
├── es/                                # Spanish translations
│   └── LC_MESSAGES/
│       ├── pocs.po                   # Human-readable translations
│       └── pocs.mo                   # Compiled binary translations
└── ja/                                # Japanese translations
    └── LC_MESSAGES/
        ├── pocs.po                   # Human-readable translations
        └── pocs.mo                   # Compiled binary translations
```

## Using Translations

### For Users

To enable Spanish messages, add this to your `pocs.yaml` or `pocs_local.yaml`:

```yaml
language: es
```

For Japanese:

```yaml
language: ja
```

### For Developers

#### Adding New Messages

When adding new messages to POCS code:

1. Use the message in English in your code:
   ```python
   self.say("This is a new message!")
   ```

2. Add the English message to `messages.pot`:
   ```
   msgid "This is a new message!"
   msgstr ""
   ```

3. Add the Spanish translation to `es/LC_MESSAGES/pocs.po`:
   ```
   msgid "This is a new message!"
   msgstr "¡Este es un nuevo mensaje!"
   ```

4. Recompile the .mo file (see below)

#### Recompiling .mo Files

After editing .po files, recompile to .mo format using the standard `msgfmt` command:

```bash
# Install gettext tools if not already installed
# Ubuntu/Debian:
sudo apt-get install gettext

# macOS:
brew install gettext

# Compile Spanish translations
msgfmt es/LC_MESSAGES/pocs.po -o es/LC_MESSAGES/pocs.mo

# Compile Japanese translations
msgfmt ja/LC_MESSAGES/pocs.po -o ja/LC_MESSAGES/pocs.mo
```

Or compile all languages at once:

```bash
find . -name "*.po" -execdir msgfmt pocs.po -o pocs.mo \;
```

#### Adding a New Language

To add support for a new language (e.g., French 'fr'):

1. Create directory structure:
   ```bash
   mkdir -p fr/LC_MESSAGES
   ```

2. Copy the template:
   ```bash
   cp messages.pot fr/LC_MESSAGES/pocs.po
   ```

3. Edit `fr/LC_MESSAGES/pocs.po`:
   - Update header (Language, Language-Team)
   - Translate all `msgstr` entries

4. Compile the .mo file (see above)

5. Test:
   ```python
   from panoptes.pocs import i18n
   i18n.set_language('fr')
   print(i18n.translate("Hi there!"))
   ```

## Translation Guidelines

1. **Keep it friendly**: POCS messages are designed to be conversational and friendly
2. **Preserve formatting**: Maintain `{variable}` placeholders in translations
3. **Keep emojis**: Preserve emoji characters (e.g., 🔭)
4. **Context matters**: Some words have multiple translations - choose based on context
5. **Test thoroughly**: Always test translations with actual POCS runs

## Questions or Contributions

- For questions about i18n: Open an issue on GitHub
- To contribute translations: Submit a PR with updated .po files
- To report translation errors: Open an issue with details

¡Gracias! Thanks! 🌟
