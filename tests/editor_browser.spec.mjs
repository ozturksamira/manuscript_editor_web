import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
const port=4173;
const server=spawn("python",["-m","http.server",String(port),"--directory","public"],{stdio:"ignore"});
const sleep=(ms)=>new Promise((resolve)=>setTimeout(resolve,ms));
const editorHtml=readFileSync("public/editor.html","utf8");
try {
  await sleep(800);
  const browser=await chromium.launch({headless:true});
  const page=await browser.newPage();
  const content="<p>Preface text.</p><h1>Chapter One</h1><p>John ran. John jumped. John screamed. John shouted. The ball was thrown by John.</p><h1>Chapter Two</h1><p>alpha alpha alpha alpha.</p><h1>Chapter Three</h1><p>alpha alpha alpha alpha.</p>";
  let savedContent="";
  const savedAnalysis={
    word_count:18,
    words:[{word:"alpha",count:12,contexts:["alpha alpha alpha alpha."]}],
    passive:[{sentence:"The ball was thrown by John.",start:51,end:79,reason:"High-confidence passive voice — explicit agent",confidence:"high"}],
    pacing:[{sentence:"John ran. John jumped. John screamed. John shouted. The ball was thrown by John.",start:25,end:79,reason:"Too fast — possible event compression",word_count:12,confidence:"medium"}],
    flagged_count:14
  };
  await page.route("**/api/account",async(route)=>route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({email:"smoke@example.test"})}));
  await page.route("**/api/projects/1",async(route)=>{
    if(route.request().method()==="POST"){
      const body=JSON.parse(route.request().postData()||"{}");
      savedContent=body.content||"";
      await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({status:"success",slug:"smoke-manuscript",url:"/project/smoke-manuscript/"})});
      return;
    }
    await route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({project:{id:1,title:"Smoke manuscript",slug:"smoke-manuscript",url:"/project/smoke-manuscript/",content:savedContent||content,analysis:savedAnalysis}})});
  });
  await page.route("**/api/projects",async(route)=>route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({projects:[{id:1,title:"Smoke manuscript",slug:"smoke-manuscript",url:"/project/smoke-manuscript/"}]})}));
  await page.route("**/projects/",async(route)=>route.fulfill({
    status:200,contentType:"text/html",
    body:'<!doctype html><html><body><a id="returnToProject" href="/project/smoke-manuscript/">Return to manuscript</a></body></html>'
  }));
  await page.route("**/project/smoke-manuscript/",async(route)=>route.fulfill({
    status:200,contentType:"text/html",body:editorHtml
  }));
  await page.goto("http://127.0.0.1:"+port+"/editor.html",{waitUntil:"domcontentloaded"});
  if(await page.locator(".editor-pane-tabs").isVisible())throw new Error("Writing/Issues tabs should be hidden on desktop");
  if(!await page.locator("#issuesScreen").isVisible())throw new Error("Issues sidebar should remain visible on desktop");
  if(!await page.locator("#saveNowButton").isVisible())throw new Error("Save now should be available at the top of the editor");
  if(await page.locator(".manuscript-footer #saveNowButton").count()!==0)throw new Error("Save now should not remain in the manuscript footer");
  if(await page.locator(".project-footer-actions").isVisible()===false)throw new Error("Project actions should be moved to the bottom");
  if(await page.locator(".project-footer-actions button").count()!==2)throw new Error("Bottom project actions should contain New project and Import manuscript");
  await page.locator("#exportProjectButton").click();
  if(await page.locator("#exportBackdrop").isVisible()===false)throw new Error("Export project dialog did not open");
  if(await page.locator("#exportBackdrop .export-option").count()!==3)throw new Error("Export project should offer exactly three formats");
  for(const format of ["DOCX","PDF","TXT"]){
    if(await page.locator("#exportBackdrop .export-option").filter({hasText:format}).count()!==1)throw new Error("Missing "+format+" export option");
  }
  if(await page.locator("#exportBackdrop").getByText("HTML",{exact:true}).count()!==0)throw new Error("HTML export should not be offered");
  await page.locator(".export-cancel").click();
  await page.locator(".mm-section").first().waitFor();
  if(await page.locator(".mm-section").count()!==4)throw new Error("Initial section build failed");
  if(await page.locator(".outline-item").count()!==3)throw new Error("Initial Contents build failed");
  const canonicalOnOpen=await page.evaluate(()=>serializeEditorContent());
  if(!canonicalOnOpen.includes("<p>Preface text.</p>"))throw new Error("Opening the manuscript mutated canonical prose");
  await page.evaluate(()=>{const e=document.getElementById("richEditor");e.innerHTML="<h1>Chapter One</h1><p>Intro.</p><div><h2>Nested Section</h2><p>Nested text.</p></div><h1>Chapter Two</h1><p>More.</p><h1>Chapter Three</h1><p>End.</p>";e.dispatchEvent(new Event("input",{bubbles:true}));});
  for(let i=0;i<30&&await page.locator(".outline-item").count()!==4;i++) await sleep(100);
  if(await page.locator(".outline-item").count()!==4)throw new Error("Nested canonical heading disappeared from Contents");
  if(await page.locator(".outline-item").filter({hasText:"Nested Section"}).count()!==1)throw new Error("Nested canonical heading was not navigable in Contents");
  await page.evaluate(()=>{const e=document.getElementById("richEditor");e.innerHTML="<p>Preface text.</p><h1>Chapter One</h1><p>John ran. John jumped. John screamed. John shouted. The ball was thrown by John.</p><h1>Chapter Two</h1><p>alpha alpha alpha alpha.</p><h1>Chapter Three</h1><p>alpha alpha alpha alpha.</p>";e.dispatchEvent(new Event("input",{bubbles:true}));});
  for(let i=0;i<30&&await page.locator(".mm-section").count()!==4;i++) await sleep(100);
  await page.locator(".outline-item").nth(2).click();
  if(!(await page.locator(".mm-section-active").innerText()).includes("Chapter Three"))throw new Error("Contents navigation failed");

  await page.evaluate(()=>{const e=document.getElementById("richEditor");e.innerHTML="<p>Preface text.</p><h1>Chapter One</h1><p>John ran. John jumped. John screamed. John shouted. The ball was thrown by John.</p><h1>Chapter Two</h1><p>alpha alpha alpha alpha.</p><h1>Chapter Three</h1><p>alpha alpha alpha alpha.</p><h1>Chapter Four</h1><p>alpha alpha alpha alpha.</p>";e.dispatchEvent(new Event("input",{bubbles:true}));});
  for(let i=0;i<30&&await page.locator(".mm-section").count()!==5;i++) await sleep(100);
  if(await page.locator(".mm-section").count()!==5||await page.locator(".outline-item").count()!==4)throw new Error("New heading refresh failed");

  await page.waitForTimeout(1200);
  if(!savedContent||savedContent.includes("mm-section"))throw new Error("Saved content should be canonical manuscript HTML without runtime section wrappers");
  await page.reload({waitUntil:"domcontentloaded"});
  await page.locator(".mm-section").first().waitFor();
  if(await page.evaluate(()=>window.CSS?.highlights?.has("mm-editor-issue") ? window.CSS.highlights.get("mm-editor-issue").size : 0)!==0)throw new Error("Transient issue focus survived a page reload");
  if(await page.locator(".mm-section").count()!==5||await page.locator(".outline-item").count()!==4)throw new Error("Contents did not rebuild after refresh");

  await page.locator("a.brand").click();
  await page.locator("#returnToProject").waitFor();
  await page.locator("#returnToProject").click();
  await page.locator(".mm-section").first().waitFor();
  if(await page.locator(".mm-section").count()!==5||await page.locator(".outline-item").count()!==4)throw new Error("Contents did not survive project-page round trip");
  await page.evaluate(()=>{
    currentAnalysis={
      word_count:29,
      words:[{word:"alpha",count:12,contexts:["alpha alpha alpha alpha."]}],
      passive:[{sentence:"The ball was thrown by John.",start:78,end:106,reason:"High-confidence passive voice — explicit agent",confidence:"high"}],
      pacing:[{sentence:"John jumped. John screamed. John shouted.",start:36,end:77,reason:"Too fast — possible event compression",word_count:9,confidence:"medium"}],
      flagged_count:14
    };
    visibleAnalysis=currentAnalysis;
    renderIssues();
    updateWordCount();
  });
  await page.setViewportSize({width:390,height:900});
  if(!await page.locator(".editor-pane-tabs").isVisible())throw new Error("Writing/Issues tabs should be visible on mobile");
  await page.locator("#mobileIssuesTab").click();

  await page.locator("#wordsView .issue-card").first().waitFor();
  await page.locator("#wordsView .issue-card").first().click();
  await page.locator("#wordSearchPopover.open").waitFor();
  const highlightedText=()=>page.evaluate(()=>{
    const h=window.CSS?.highlights?.get("mm-editor-issue");
    return h&&h.size ? Array.from(h).map(range=>range.toString()).join("") : "";
  });
  const waitForHighlight=async(expected)=>{
    await page.waitForFunction((value)=>{
      const h=window.CSS?.highlights?.get("mm-editor-issue");
      return !!(h&&h.size&&Array.from(h).map(range=>range.toString()).join("")===value);
    },expected,{timeout:3000});
  };
  const waitForHighlightInEditor=async()=>{
    await page.waitForFunction(()=>{
      const h=window.CSS?.highlights?.get("mm-editor-issue");
      const range=h&&h.size?Array.from(h)[0]:null;
      if(!range)return false;
      const editor=document.getElementById("richEditor");
      const rect=range.getBoundingClientRect();
      const editorRect=editor.getBoundingClientRect();
      return rect.bottom>=editorRect.top&&rect.top<=editorRect.bottom;
    },null,{timeout:3000});
  };
  await waitForHighlight("alpha");
  if(await highlightedText()!=="alpha")throw new Error("Overused word did not receive the correct soft focus highlight");
  if(await page.locator(".mm-section-active").innerText().then(text=>!text.includes("Chapter Two")))throw new Error("Overused word did not activate its containing chapter");
  await page.locator("#wordNext").click();
  if(await page.locator("#wordSearchMeta").innerText()!=="Use 2 of 12")throw new Error("Next word navigation did not advance to the second occurrence");
  const secondWord=await highlightedText();
  if(secondWord!=="alpha")throw new Error("Next word did not replace the focus highlight");
  await page.locator("#wordPrev").click();
  if(await highlightedText()!=="alpha")throw new Error("Previous word did not restore the prior focus");
  if(await page.locator("#wordSearchMeta").innerText()!=="Use 1 of 12")throw new Error("Previous word navigation did not move back to the first occurrence");

  await page.locator("#mobileIssuesTab").click();
  await page.locator(".issue-tab").filter({hasText:"Passive"}).click();
  await page.locator("#passiveView .issue-card").first().click();
  await waitForHighlight("The ball was thrown by John.");
  await waitForHighlightInEditor();
  if(await highlightedText()!=="The ball was thrown by John.")throw new Error("Passive issue did not receive the correct soft focus highlight");
  await page.evaluate(()=>saveProject());
  await page.waitForTimeout(300);
  if(savedContent.includes("issue-focus-highlight")||savedContent.includes("mm-editor-issue"))throw new Error("Transient issue focus was persisted into manuscript content");
  if(await page.locator(".mm-section-active").innerText().then(text=>!text.includes("Chapter One")))throw new Error("Passive issue did not activate its containing chapter");
  await page.locator("#mobileIssuesTab").click();
  await page.locator(".issue-tab").filter({hasText:"Pacing"}).click();
  await page.locator("#pacingView .issue-card").first().click();
  await waitForHighlight("John jumped. John screamed. John shouted.");
  if(await highlightedText()!=="John jumped. John screamed. John shouted.")throw new Error("Pacing issue did not replace the previous focus with the correct highlight");
  if(await page.locator(".mm-section-active").innerText().then(text=>!text.includes("Chapter One")))throw new Error("Pacing issue did not activate its containing chapter");

  await page.evaluate(()=>closeWordSearch());
  if(await page.evaluate(()=>window.CSS?.highlights?.has("mm-editor-issue") ? window.CSS.highlights.get("mm-editor-issue").size : 0)!==0)throw new Error("Issue highlight did not clear when closing focus");
  await page.evaluate(()=>{const e=document.getElementById("richEditor");e.innerHTML="<p>Preface text.</p><h1>Chapter One</h1><p>John ran. John jumped. John screamed. John shouted. The ball was thrown by John.</p><h1>Chapter Two</h1><p>alpha alpha alpha alpha.</p><h1>Chapter Three</h1><p>alpha alpha alpha alpha.</p>";e.dispatchEvent(new Event("input",{bubbles:true}));});
  for(let i=0;i<30&&await page.locator(".mm-section").count()!==4;i++) await sleep(100);
  if(await page.locator(".mm-section").count()!==4||await page.locator(".outline-item").count()!==3)throw new Error("Deleting a heading did not remove the stale Contents entry");
  await page.waitForTimeout(1200);
  await page.reload({waitUntil:"domcontentloaded"});
  await page.locator(".mm-section").first().waitFor();
  if(await page.locator(".mm-section").count()!==4||await page.locator(".outline-item").count()!==3)throw new Error("Deleted heading returned after reload");
  await browser.close();
} finally { server.kill("SIGTERM"); }