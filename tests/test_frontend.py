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
        self.assertIn("function findWordOccurrences(index,word)", html)
        self.assertNotIn("function openSidebarTab(", html)

    def test_issue_navigation_returns_to_writing_pane(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        start = html.index("function selectAndScroll(range){")
        end = html.index("function jumpToOffsets", start)
        block = html[start:end]
        self.assertIn("setMobilePane('writing')", block)

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

    def test_editor_has_word_sort_search_and_bottom_jump(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        self.assertIn("Most to least", html)
        self.assertIn("A–Z", html)
        self.assertIn("wordSearchPopover", html)
        self.assertIn("wordNext", html)
        self.assertIn("wordPrev", html)
        self.assertIn("writingJumpBottom", html)
        self.assertIn("manuscript-footer').scrollIntoView", html)
        self.assertIn("function promoteImportedHeadings(value)", html)
        self.assertIn("includeDefaultStyleMap:true", html)

    def test_issue_text_removes_literal_newline_markers(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        self.assertIn("replace(/\\\\n/g,' ')", html)
        self.assertIn("replace(/\\r?\\n/g,' ')", html)

    def test_editor_imports_pdf_and_keeps_actions_at_top(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        self.assertIn('accept=".txt,.docx,.pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/pdf"', html)
        self.assertIn("if(name.endsWith('.pdf'))", html)
        self.assertIn("pdfjs-dist@6.3.289", html)
        self.assertIn('class="editor-top-actions"', html)
        self.assertIn('id="analyseButton"', html)
        self.assertIn('id="writingJumpBottom"', html)
        self.assertLess(html.index('class="editor-top-actions"'), html.index('class="paper-wrap"'))
        footer_start = html.index('<div class="manuscript-footer">')
        footer_end = html.index('</div>\\n      </div>', footer_start) if '</div>\\n      </div>' in html[footer_start:] else len(html)
        footer = html[footer_start:footer_end]
        self.assertNotIn('id="analyseButton"', footer)

    def test_editor_keeps_project_rename_delete_api_paths(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        self.assertIn("'/api/projects/'+activeProjectId", html)
        self.assertIn("method:'DELETE'", html)


if __name__ == "__main__":
    unittest.main()
