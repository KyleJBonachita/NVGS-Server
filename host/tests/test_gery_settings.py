import os
import stat
import tempfile
import unittest
from pathlib import Path

from host.gery_settings import (
    GeryAISettings,
    load_gery_ai_settings,
    save_gery_ai_settings,
    validate_gery_ai_settings,
    verify_gery_admin_token,
)


class GerySettingsTests(unittest.TestCase):
    def test_admin_token_comparison_accepts_only_the_saved_token(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            token_path = Path(temporary_dir) / "gery_admin_token"
            token_path.write_text("correct-secret\n", encoding="utf-8")

            self.assertTrue(verify_gery_admin_token("correct-secret", token_path))
            self.assertFalse(verify_gery_admin_token("wrong-secret", token_path))
            self.assertFalse(verify_gery_admin_token("", token_path))

    def test_settings_are_loaded_without_disclosing_the_api_key(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            key_path = Path(temporary_dir) / "gery_ai_api_key"
            key_path.write_text("private-api-key\n", encoding="utf-8")
            settings = load_gery_ai_settings(
                {
                    "GERY_AI_BASE_URL": "https://ai.internal.example",
                    "GERY_AI_MODEL": "approved/model",
                    "GERY_INGESTION_AI_ENABLED": "true",
                    "GERY_ALLOW_LIVE_AI": "false",
                },
                key_path,
            )

            self.assertTrue(settings.api_key_configured)
            self.assertFalse(hasattr(settings, "api_key"))
            self.assertEqual(settings.model, "approved/model")

    def test_save_updates_only_gery_env_values_and_preserves_an_existing_key(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            env_path = root / ".env"
            key_path = root / "secrets" / "gery_ai_api_key"
            key_path.parent.mkdir()
            env_path.write_text(
                "# keep this comment\nSERVER_ADDRESS=localhost\n"
                "GERY_INGESTION_AI_ENABLED=false\n"
                "GERY_ALLOW_LIVE_AI=false\n"
                "GERY_AI_BASE_URL=http://old:1234\n"
                "GERY_AI_MODEL=old-model\n",
                encoding="utf-8",
            )
            key_path.write_text("existing-key\n", encoding="utf-8")

            result = save_gery_ai_settings(
                GeryAISettings(
                    base_url="https://ai.internal.example/v1/",
                    model="approved/model",
                    ingestion_ai_enabled=True,
                    live_ai_enabled=False,
                    api_key_configured=True,
                ),
                env_path,
                key_path,
                api_key_update=None,
            )

            saved_env = env_path.read_text(encoding="utf-8")
            self.assertIn("# keep this comment", saved_env)
            self.assertIn("SERVER_ADDRESS=localhost", saved_env)
            self.assertIn("GERY_INGESTION_AI_ENABLED=true", saved_env)
            self.assertIn("GERY_AI_BASE_URL=https://ai.internal.example/v1", saved_env)
            self.assertEqual(key_path.read_text(encoding="utf-8"), "existing-key\n")
            self.assertTrue(result.api_key_configured)

    def test_save_can_replace_or_clear_the_api_key(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            env_path = root / ".env"
            key_path = root / "secrets" / "gery_ai_api_key"
            key_path.parent.mkdir()
            env_path.write_text("SERVER_ADDRESS=localhost\n", encoding="utf-8")
            env_path.chmod(0o600)
            settings = GeryAISettings(
                base_url="http://host.docker.internal:1234",
                model="local-model",
                ingestion_ai_enabled=True,
                live_ai_enabled=False,
            )

            save_gery_ai_settings(settings, env_path, key_path, "new-secret")
            self.assertEqual(key_path.read_text(encoding="utf-8"), "new-secret\n")
            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(env_path.stat().st_mode), 0o600)
                self.assertEqual(stat.S_IMODE(key_path.stat().st_mode), 0o644)
            result = save_gery_ai_settings(settings, env_path, key_path, "")
            self.assertEqual(key_path.read_text(encoding="utf-8"), "\n")
            self.assertFalse(result.api_key_configured)

    def test_validation_rejects_unsafe_or_incomplete_values(self):
        settings = GeryAISettings(
            base_url="file:///tmp/model",
            model="valid-model",
            ingestion_ai_enabled=False,
            live_ai_enabled=False,
        )
        with self.assertRaisesRegex(ValueError, "http"):
            validate_gery_ai_settings(settings)
        with self.assertRaisesRegex(ValueError, "spaces"):
            validate_gery_ai_settings(
                GeryAISettings(
                    base_url="https://ai.example",
                    model="invalid model",
                    ingestion_ai_enabled=False,
                    live_ai_enabled=False,
                )
            )


if __name__ == "__main__":
    unittest.main()
