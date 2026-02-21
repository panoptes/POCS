"""Tests for internationalization (i18n) support in POCS."""
import pytest
from panoptes.pocs import i18n


class TestI18nModule:
    """Tests for the i18n module itself."""
    
    def test_default_language_is_english(self):
        """Test that the default language is English."""
        # Reset to default
        i18n.set_language('en')
        
        # English should return the original message
        msg = "Hi there!"
        translated = i18n.translate(msg)
        assert translated == msg

    def test_spanish_translation(self):
        """Test Spanish translation of messages."""
        # Set language to Spanish
        i18n.set_language('es')
        
        # Test a few key messages
        assert i18n.translate("Hi there!") == "¡Hola!"
        assert i18n.translate("I'm powering down") == "Me estoy apagando"
        assert i18n.translate("Ok, let's park!") == "¡Ok, vamos a estacionar!"
        assert i18n.translate("Another successful night!") == "¡Otra noche exitosa!"
        
        # Reset to English
        i18n.set_language('en')

    def test_format_string_translation(self):
        """Test that format strings work with translations."""
        i18n.set_language('es')
        
        # Test with a format string (should preserve the format placeholders)
        msg = "Observing {current_observation}"
        translated = i18n.translate(msg)
        assert translated == "Observando {current_observation}"
        
        # Test that the formatted version works
        formatted = translated.format(current_observation="M31")
        assert formatted == "Observando M31"
        
        i18n.set_language('en')

    def test_fallback_to_original(self):
        """Test that untranslated messages fall back to the original."""
        i18n.set_language('es')
        
        # A message that doesn't exist in translations
        untranslated = "This message is not translated"
        result = i18n.translate(untranslated)
        
        # Should return the original message
        assert result == untranslated
        
        i18n.set_language('en')

    def test_invalid_language_falls_back(self):
        """Test that an invalid language code falls back gracefully."""
        # Try to set an unsupported language
        i18n.set_language('xx')  # Invalid language code
        
        # Should fall back and not crash
        msg = "Hi there!"
        translated = i18n.translate(msg)
        # Should return original since the language doesn't exist
        assert translated == msg
        
        i18n.set_language('en')

    def test_convenience_alias(self):
        """Test that the _ alias works."""
        i18n.set_language('es')
        
        # Test using the _ alias
        assert i18n._("Hi there!") == "¡Hola!"
        
        i18n.set_language('en')

    def test_emoji_in_translation(self):
        """Test that emojis are preserved in translations."""
        i18n.set_language('es')
        
        msg = "🔭🔭 I'm observing {current_obs.field.field_name}! 🔭🔭"
        translated = i18n.translate(msg)
        
        # Should preserve emojis
        assert "🔭🔭" in translated
        assert translated == "🔭🔭 ¡Estoy observando {current_obs.field.field_name}! 🔭🔭"
        
        i18n.set_language('en')

    def test_multiple_language_switches(self):
        """Test that we can switch languages multiple times."""
        # Start with English
        i18n.set_language('en')
        assert i18n.translate("Hi there!") == "Hi there!"
        
        # Switch to Spanish
        i18n.set_language('es')
        assert i18n.translate("Hi there!") == "¡Hola!"
        
        # Switch back to English
        i18n.set_language('en')
        assert i18n.translate("Hi there!") == "Hi there!"
        
        # Switch to Spanish again
        i18n.set_language('es')
        assert i18n.translate("Hi there!") == "¡Hola!"
        
        # Reset to English
        i18n.set_language('en')

    def test_all_spanish_messages(self):
        """Test that all messages have Spanish translations."""
        i18n.set_language('es')
        
        # List of all messages that should be translated
        messages_to_check = [
            "Hi there!",
            "Looks like we're missing some required hardware.",
            "Initializing the system! Woohoo!",
            "I'm powering down",
            "Ok, I'm all set up and ready to go!",
            "Closing dome",
            "Ok, let's park!",
            "Another successful night!",
            "Parking the mount!",
            "Taking pointing picture.",
            "Checking our tracking",
            "I'm parked now.",
            "No observations found.",
        ]
        
        for msg in messages_to_check:
            translated = i18n.translate(msg)
            # All these messages should have Spanish translations
            assert translated != msg, f"Message '{msg}' is not translated"
            # Verify it's actually different (Spanish translation)
            assert len(translated) > 0
        
        # Reset to English
        i18n.set_language('en')
