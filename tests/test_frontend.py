from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parent.parent


class FrontendRegressionTest(unittest.TestCase):
    def test_editor_uses_real_section_pages_and_navigation(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        self.assertIn(".editor.has-sections > .mm-section{display:none", html)
        self.assertIn(".editor.has-sections > .mm-section.mm-section-active{display:block}", html)
        self.assertIn('id="prevSection"', html)
        self.assertIn('id="nextSection"', html)
        self.assertIn("function navigateSection(delta)", html)
        self.assertIn("function jumpToOffsets(start,end)", html)
        self.assertIn("function findWordOccurrence(index,word,occurrence)", html)
        self.assertNotIn("function openSidebarTab(", html)

    def test_issue_navigation_returns_to_writing_pane(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        match = re.search(r"function selectAndScroll\(range\)\{(.*?)\n\}", html, re.S)
        self.assertIsNotNone(match)
        self.assertIn("setMobilePane('writing')", match.group(1))

    def test_analysis_uses_untrimmed_index_for_offsets(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        self.assertIn("const manuscriptText=index.text;", html)
        self.assertNotIn("const manuscriptText=index.text.trim();", html)

    def test_projects_use_dom_event_handlers_for_menu_actions(self):
        html = (ROOT / "public" / "projects.html").read_text(encoding="utf-8")
        self.assertIn("rename.addEventListener", html)
        self.assertIn("remove.addEventListener", html)
        self.assertIn("async function renameProject(projectId,currentTitle)", html)
        self.assertIn("async function removeProject(projectId,title)", html)
        self.assertNotRegex(html, r'onclick="renameProject\(')
        self.assertNotRegex(html, r'onclick="removeProject\(')

    def test_editor_keeps_project_rename_delete_api_paths(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        self.assertIn("'/api/projects/'+activeProjectId", html)
        self.assertIn("method:'DELETE'", html)


if __name__ == "__main__":
    unittest.main()
