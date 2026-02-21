# POCS Internationalization (i18n)

This directory contains translation files for POCS user-facing messages.

## Supported Languages

- **English (en)**: Default language
- **Spanish (es)**: ¡Español! 🌎

## Directory Structure

```
locale/
├── README.md                          # This file
├── messages.pot                       # Template file (all messages)
└── es/                                # Spanish translations
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

See `conf_files/pocs_spanish.yaml` for a complete example.

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

After editing .po files, recompile to .mo format:

```bash
python3 << 'EOF'
import struct
from pathlib import Path

def parse_po_file(po_path):
    """Parse a .po file and extract msgid/msgstr pairs."""
    messages = {}
    current_msgid = []
    current_msgstr = []
    state = None
    header_found = False
    
    with open(po_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not state and (line.startswith('#') or not line.strip()):
                continue
            
            if line.startswith('msgid '):
                if state == 'msgstr':
                    msgid_text = ''.join(current_msgid)
                    msgstr_text = ''.join(current_msgstr)
                    if not msgid_text and not header_found:
                        messages[''] = msgstr_text
                        header_found = True
                    elif msgid_text:
                        messages[msgid_text] = msgstr_text
                
                current_msgid = [line[7:-1]]
                current_msgstr = []
                state = 'msgid'
                
            elif line.startswith('msgstr '):
                current_msgstr = [line[8:-1]]
                state = 'msgstr'
                
            elif line.startswith('"') and line.endswith('"'):
                content = line[1:-1]
                if state == 'msgid':
                    current_msgid.append(content)
                elif state == 'msgstr':
                    current_msgstr.append(content)
        
        if state == 'msgstr':
            msgid_text = ''.join(current_msgid)
            msgstr_text = ''.join(current_msgstr)
            if msgid_text:
                messages[msgid_text] = msgstr_text
    
    return messages

def generate_mo_file(messages, mo_path):
    """Generate a .mo file from message dictionary."""
    keys = sorted([k for k in messages.keys() if k != ''])
    if '' in messages:
        keys = [''] + keys
    
    offsets = []
    ids = b''
    strs = b''
    
    for key in keys:
        value = messages[key]
        offsets.append((len(ids), len(key.encode('utf-8')), 
                       len(strs), len(value.encode('utf-8'))))
        ids += key.encode('utf-8') + b'\x00'
        strs += value.encode('utf-8') + b'\x00'
    
    keystart = 7 * 4 + 16 * len(keys)
    valuestart = keystart + len(ids)
    
    output = struct.pack('I', 0x950412de)
    output += struct.pack('I', 0)
    output += struct.pack('I', len(keys))
    output += struct.pack('I', 7 * 4)
    output += struct.pack('I', 7 * 4 + 8 * len(keys))
    output += struct.pack('I', 0)
    output += struct.pack('I', 0)
    
    for o1, l1, o2, l2 in offsets:
        output += struct.pack('II', l1, keystart + o1)
    for o1, l1, o2, l2 in offsets:
        output += struct.pack('II', l2, valuestart + o2)
    
    output += ids + strs
    
    with open(mo_path, 'wb') as f:
        f.write(output)
    
    return len(messages)

# Compile Spanish translations
po_file = Path('es/LC_MESSAGES/pocs.po')
mo_file = Path('es/LC_MESSAGES/pocs.mo')
messages = parse_po_file(po_file)
count = generate_mo_file(messages, mo_file)
print(f"Compiled {count} messages to {mo_file}")
EOF
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
