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

    def test_editor_has_chapter_analysis_and_fixed_page_navigation(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        self.assertIn('id="analyseChapterButton"', html)
        self.assertIn('onclick="analyseChapter()"', html)
        self.assertIn("async function analyseChapter()", html)
        self.assertIn("buildTextIndex(section)", html)
        self.assertIn("id=" + '"writingJumpTop"', html)
        self.assertIn("window.scrollTo({top:0,behavior:'smooth'})", html)
        self.assertIn("id=" + '"writingJumpBottom"', html)
        self.assertIn("position:fixed", html)
        self.assertIn('class="editor-pane-tabs"', html)
        self.assertIn('id="mobileIssuesTab"', html)
        self.assertIn('class="issues-screen"', html)
        self.assertIn("layout.classList.toggle('issues-mode',!writing)", html)
        self.assertNotIn('class="issues-panel" aria-label="Editorial issues"', html.split('class="issues-screen"', 1)[0])

    def test_analysis_refreshes_headings_and_contents(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        self.assertIn("function promoteEditorHeadingCandidates()", html)
        self.assertIn("function refreshEditorialStructure(checkHeadingCandidates)", html)
        self.assertIn("refreshEditorialStructure(true);", html)
        self.assertIn("Checking headings and refreshing Contents…", html)
        self.assertIn("refreshOutline();", html)
        self.assertIn("const numbered=/^(?:chapter\\s+)?(?:\\d+|[ivxlcdm]+)[\\s:.)-]+[A-Za-z]/i.test(text);", html)

    def test_overused_word_navigation_re_resolves_target_range(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        start = html.index("function findWordOccurrences(index,word){")
        end = html.index("function jumpToWord(word,progress){", start)
        block = html[start:end]
        self.assertIn("node:item.node", block)
        self.assertIn("nodeOffsetStart:match.index", block)
        self.assertIn("nodeOffsetEnd:match.index+match[0].length", block)

        start = html.index("function focusWordOccurrence(index,occurrenceIndex){")
        end = html.index("function moveWordOccurrence(delta){", start)
        block = html[start:end]
        self.assertIn("const freshMatches=findWordOccurrences(buildTextIndex(),index);", block)
        self.assertIn("freshTarget.nodeOffsetStart", block)
        self.assertIn("selection.addRange(range)", block)
        self.assertIn("scrollRangeIntoEditor(range)", block)
        self.assertIn("setActiveSection(sectionIndex,false)", block)
    def test_editor_uses_canonical_heading_structure_refresh(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        self.assertIn("function sectionStructureNeedsSync()", html)
        self.assertIn("function rebuildSections()", html)
        self.assertIn("function getSelectionOffsets()", html)
        self.assertIn("function restoreSelectionOffsets(offsets)", html)
        self.assertIn("promoteEditorHeadingCandidates();", html)
        self.assertIn("mso-)?outline-level", html)
        self.assertIn("const titleCase=titleWords.length>=2&&titleWords.length<=8", html)
        self.assertIn("hasOnlyBoldText", html)
        self.assertIn("text-align\\s*:\\s*center", html)
        self.assertIn("refreshEditorialStructure(true);", html)
        self.assertIn("Checking headings and refreshing Contents…", html)
        self.assertNotIn("const needsRebuild=!existing.length || Boolean(force) || headingCount>existing.length;", html)

    def test_contents_targets_actual_section_after_preface(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        start = html.index("function refreshOutline(){")
        end = html.index("function issueCard(title,meta,copy,action){", start)
        block = html[start:end]
        self.assertIn("button.dataset.sectionIndex=String(index);", block)
        self.assertIn("setActiveSection(Number(this.dataset.sectionIndex),true);", block)
        self.assertIn("Number(button.dataset.sectionIndex)===activeIndex", block)

    def test_overused_word_navigation_targets_live_text_node(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        start = html.index("function findWordOccurrences(index,word){")
        end = html.index("function jumpToWord(word,progress){", start)
        block = html[start:end]
        self.assertIn("node:item.node", block)
        self.assertIn("nodeOffsetStart:match.index", block)
        self.assertIn("nodeOffsetEnd:match.index+match[0].length", block)

        start = html.index("function focusWordOccurrence(index,occurrenceIndex){")
        end = html.index("function moveWordOccurrence(delta){", start)
        block = html[start:end]
        self.assertIn("const freshMatches=findWordOccurrences(buildTextIndex(),index);", block)
        self.assertIn("freshTarget.nodeOffsetStart", block)
        self.assertIn("selection.addRange(range)", block)
        self.assertIn("scrollRangeIntoEditor(range)", block)

    def test_editor_keeps_project_rename_delete_api_paths(self):
        html = (ROOT / "public" / "editor.html").read_text(encoding="utf-8")
        self.assertIn("'/api/projects/'+activeProjectId", html)
        self.assertIn("method:'DELETE'", html)


if __name__ == "__main__":
    unittest.main()
