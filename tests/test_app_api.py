import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class FlaskApiIntegrationTest(unittest.TestCase):
    def test_json_import_matches_editor_contract(self):
        script = r'''
import json
import os
import sys
sys.path.insert(0, os.environ["MM_ROOT"])
from app import app

client = app.test_client()
email = "integration-import@example.test"
password = "integration-password-123"

register = client.post("/auth", json={
    "action": "register",
    "email": email,
    "password": password,
})
assert register.status_code == 200, register.get_data(as_text=True)

response = client.post("/api/projects/import", json={
    "filename": "chapter-one.txt",
    "title": "Chapter One",
    "content": "<h1>Chapter One</h1><p>Imported text.</p>",
})
assert response.status_code == 201, response.get_data(as_text=True)
project = response.get_json()["project"]
assert project["title"] == "Chapter One"
assert project["source_filename"] == "chapter-one.txt"
assert "Imported text." in project["content"]

delete = client.post("/api/account/delete", json={
    "password": password,
    "confirmation": "DELETE",
})
assert delete.status_code == 200, delete.get_data(as_text=True)
'''
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env.pop("DATABASE_URL", None)
            env["MM_DB_PATH"] = str(Path(directory) / "integration.db")
            env["MM_ROOT"] = str(ROOT)
            result = subprocess.run(
                [sys.executable, "-c", script],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(
                result.returncode,
                0,
                result.stdout + "\n" + result.stderr,
            )


if __name__ == "__main__":
    unittest.main()
