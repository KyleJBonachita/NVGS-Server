import os
import tempfile
from pathlib import Path
from unittest import mock, skipUnless

from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile
from django.test import Client, TestCase, override_settings

from accounts.models import User, UserRole
from downloads.services import store_uploaded_files


class DownloadManagerTests(TestCase):
    def setUp(self):
        self.temporary_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_dir.cleanup)
        self.library = Path(self.temporary_dir.name) / "downloads"
        self.settings_override = override_settings(
            DOWNLOAD_LIBRARY_DIR=self.library,
            DOWNLOAD_UPLOAD_MAX_BYTES=1024 * 1024,
            DOWNLOAD_UPLOAD_MAX_FILES=5,
            FILE_UPLOAD_TEMP_DIR=self.library / ".upload-tmp",
        )
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.team = User.objects.create_user(
            email="team.upload@nvidia.com",
            password="a-long-test-password",
            role=UserRole.TEAM,
            first_name="Team",
            last_name="Uploader",
        )
        self.agent = User.objects.create_user(
            email="agent.upload@nvidia.com",
            password="a-long-test-password",
            role=UserRole.AGENT,
        )

    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get("/downloads/manage/")
        self.assertRedirects(
            response,
            "/login/?next=/downloads/manage/",
            fetch_redirect_response=False,
        )

    def test_agent_cannot_open_or_post_to_manager(self):
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get("/downloads/manage/").status_code, 403)
        response = self.client.post(
            "/downloads/manage/",
            {
                "conflict_policy": "rename",
                "files": SimpleUploadedFile("blocked.txt", b"blocked"),
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse((self.library / "blocked.txt").exists())

    def test_team_user_can_upload_and_keep_both(self):
        self.library.mkdir()
        (self.library / "guide.pdf").write_bytes(b"old")
        self.client.force_login(self.team)

        response = self.client.post(
            "/downloads/manage/",
            {
                "conflict_policy": "rename",
                "files": SimpleUploadedFile("guide.pdf", b"new"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["files"][0]["name"], "guide (2).pdf")
        self.assertEqual((self.library / "guide.pdf").read_bytes(), b"old")
        self.assertEqual((self.library / "guide (2).pdf").read_bytes(), b"new")

    def test_team_user_can_replace_existing_file(self):
        self.library.mkdir()
        (self.library / "guide.pdf").write_bytes(b"old")
        self.client.force_login(self.team)

        response = self.client.post(
            "/downloads/manage/",
            {
                "conflict_policy": "replace",
                "files": SimpleUploadedFile("guide.pdf", b"updated"),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual((self.library / "guide.pdf").read_bytes(), b"updated")
        self.assertFalse((self.library / "guide (2).pdf").exists())

    @skipUnless(os.name == "posix", "zero-copy promotion is for the Ubuntu host")
    def test_disk_backed_upload_is_promoted_without_a_second_copy(self):
        staging = self.library / ".upload-tmp"
        staging.mkdir(parents=True)
        content = b"large upload content"
        uploaded = TemporaryUploadedFile(
            "archive.zip",
            "application/zip",
            len(content),
            None,
        )
        self.addCleanup(uploaded.close)
        uploaded.write(content)
        uploaded.seek(0)
        django_temporary_path = Path(uploaded.temporary_file_path())

        with mock.patch("downloads.services.tempfile.NamedTemporaryFile") as factory:
            stored = store_uploaded_files([uploaded], conflict_policy="rename")

        factory.assert_not_called()
        self.assertEqual(stored[0].name, "archive.zip")
        self.assertEqual((self.library / "archive.zip").read_bytes(), content)
        self.assertFalse(django_temporary_path.exists())

    def test_upload_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.team)
        response = client.post(
            "/downloads/manage/",
            {
                "conflict_policy": "rename",
                "files": SimpleUploadedFile("guide.pdf", b"new"),
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_page_lists_existing_files(self):
        self.library.mkdir()
        (self.library / "guide.pdf").write_bytes(b"guide")
        self.client.force_login(self.team)

        response = self.client.get("/downloads/manage/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "guide.pdf")
        self.assertContains(response, "Protected team workspace")
        self.assertIn("no-store", response["Cache-Control"])
