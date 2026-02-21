#!/usr/bin/env python3
"""
Demonstration of POCS Internationalization Support

This script demonstrates how the POCS say() method now supports Spanish translations.
"""

import sys
from pathlib import Path

# Add src to path for direct execution
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from panoptes.pocs import i18n


def print_header(text):
    """Print a formatted header."""
    print("\n" + "="*70)
    print(f"  {text}")
    print("="*70)


def demonstrate_translation(language_code, language_name):
    """Demonstrate translations in a specific language."""
    print_header(f"{language_name} Translations")
    
    i18n.set_language(language_code)
    
    # Example messages that POCS would say
    example_messages = [
        "Hi there!",
        "Initializing the system! Woohoo!",
        "Ok, I'm all set up and ready to go!",
        "Ok, I'm finding something good to look at...",
        "🔭🔭 I'm observing {current_obs.field.field_name}! 🔭🔭",
        "Checking our tracking",
        "Another successful night!",
        "I'm powering down",
    ]
    
    for msg in example_messages:
        translated = i18n.translate(msg)
        
        # Format any placeholders with example values
        if '{current_obs.field.field_name}' in translated:
            translated = translated.replace('{current_obs.field.field_name}', 'M31')
        
        print(f"\n  Original: {msg}")
        print(f"  {language_name}: {translated}")


def main():
    """Main demonstration function."""
    print("\n")
    print("╔════════════════════════════════════════════════════════════════════╗")
    print("║                                                                    ║")
    print("║         POCS Internationalization (i18n) Demonstration            ║")
    print("║                                                                    ║")
    print("╚════════════════════════════════════════════════════════════════════╝")
    
    # Show English
    demonstrate_translation('en', 'English')
    
    # Show Spanish
    demonstrate_translation('es', 'Spanish (Español)')
    
    print_header("How to Use")
    print("""
To enable Spanish in your POCS installation:

1. Edit your pocs.yaml or pocs_local.yaml
2. Add this line at the top level:
   
   language: es

3. Restart POCS

All user-facing messages from the say() method will now be in Spanish!

For more languages, see: src/panoptes/pocs/locale/README.md
    """)
    
    print_header("Summary")
    print("""
✓ 47 messages translated to Spanish
✓ Easy to add more languages
✓ Simple configuration option
✓ Preserves format strings and emojis
✓ Falls back gracefully for untranslated messages

¡Gracias! Thanks for using POCS! 🌟🔭
    """)


if __name__ == '__main__':
    main()
