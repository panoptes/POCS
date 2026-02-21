"""Internationalization support for POCS.

This module provides translation functionality for POCS messages using a simple
.mo file reader that handles UTF-8 properly.
"""
import struct
from pathlib import Path

# Default language is English
_current_language = 'en'
_translations = {}


class SimpleTranslator:
    """Simple .mo file translator that handles UTF-8 correctly."""
    
    def __init__(self, mo_path):
        """Load translations from a .mo file.
        
        Args:
            mo_path: Path to the .mo file.
        """
        self.catalog = {}
        self._load_mo(mo_path)
    
    def _load_mo(self, mo_path):
        """Load and parse a .mo file."""
        with open(mo_path, 'rb') as f:
            # Read magic number
            magic = struct.unpack('I', f.read(4))[0]
            
            if magic not in (0x950412de, 0xde120495):
                raise ValueError(f"Invalid magic number in .mo file: {hex(magic)}")
            
            # Read header
            version, msgcount, masteridx, transidx = struct.unpack('4I', f.read(16))
            
            # Skip hash table info
            f.read(8)
            
            # Read the message catalog
            for _ in range(msgcount):
                # Read original string info
                f.seek(masteridx)
                length, offset = struct.unpack('II', f.read(8))
                masteridx += 8
                
                # Read original string
                orig_pos = f.tell()
                f.seek(offset)
                msgid = f.read(length).decode('utf-8')
                f.seek(orig_pos)
                
                # Read translation string info
                f.seek(transidx)
                length, offset = struct.unpack('II', f.read(8))
                transidx += 8
                
                # Read translation string
                trans_pos = f.tell()
                f.seek(offset)
                msgstr = f.read(length).decode('utf-8')
                f.seek(trans_pos)
                
                # Store in catalog (skip empty keys which are headers)
                if msgid:
                    self.catalog[msgid] = msgstr
    
    def gettext(self, message):
        """Get translation for a message.
        
        Args:
            message: The message to translate.
            
        Returns:
            The translated message, or the original if not found.
        """
        return self.catalog.get(message, message)


def set_language(language='en'):
    """Set the language for POCS messages.
    
    Args:
        language (str): Language code (e.g., 'en', 'es'). Defaults to 'en'.
    """
    global _current_language, _translations
    _current_language = language
    
    if language == 'en':
        # For English, use empty translations (returns original strings)
        _translations = {}
    else:
        # Get the locale directory
        locale_dir = Path(__file__).parent / 'locale'
        mo_file = locale_dir / language / 'LC_MESSAGES' / 'pocs.mo'
        
        try:
            if mo_file.exists():
                translator = SimpleTranslator(mo_file)
                _translations = translator.catalog
            else:
                print(f"Warning: Translation file not found for '{language}': {mo_file}")
                _translations = {}
        except Exception as e:
            # If translation fails, fall back to English
            print(f"Warning: Could not load translation for '{language}': {e}")
            _translations = {}


def translate(message):
    """Translate a message to the current language.
    
    Args:
        message (str): The message to translate.
        
    Returns:
        str: The translated message.
    """
    return _translations.get(message, message)


# Initialize with English by default
set_language('en')


# Convenience alias
_ = translate
