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
  const content="<p>Preface text.</p><h1>Chapter One</h1><p>alpha alpha alpha alpha. The ball was thrown by John.</p><h1>Chapter Two</h1><p>alpha alpha alpha alpha.</p><h1>Chapter Three</h1><p>alpha alpha alpha alpha.</p>";
  let savedContent="";
  const savedAnalysis={
    word_count:18,
    words:[{word:"alpha",count:12,contexts:["alpha alpha alpha alpha."]}],
    passive:[{sentence:"The ball was thrown by John.",start:51,end:79,reason:"High-confidence passive voice — explicit agent",confidence:"high"}],
    pacing:[{sentence:"alpha alpha alpha alpha. The ball was thrown by John.",start:25,end:79,reason:"Too fast — possible event compression",word_count:12,confidence:"medium"}],
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
  await page.locator(".mm-section").first().waitFor();
  if(await page.locator(".mm-section").count()!==4)throw new Error("Initial section build failed");
  if(await page.locator(".outline-item").count()!==3)throw new Error("Initial Contents build failed");
  await page.locator(".outline-item").nth(2).click();
  if(!(await page.locator(".mm-section-active").innerText()).includes("Chapter Three"))throw new Error("Contents navigation failed");

  await page.evaluate(()=>{const e=document.getElementById("richEditor");e.innerHTML="<p>Preface text.</p><h1>Chapter One</h1><p>alpha alpha alpha alpha. The ball was thrown by John.</p><h1>Chapter Two</h1><p>alpha alpha alpha alpha.</p><h1>Chapter Three</h1><p>alpha alpha alpha alpha.</p><h1>Chapter Four</h1><p>alpha alpha alpha alpha.</p>";e.dispatchEvent(new Event("input",{bubbles:true}));});
  for(let i=0;i<30&&await page.locator(".mm-section").count()!==5;i++) await sleep(100);
  if(await page.locator(".mm-section").count()!==5||await page.locator(".outline-item").count()!==4)throw new Error("New heading refresh failed");

  await page.waitForTimeout(1200);
  if(!savedContent||savedContent.includes("mm-section"))throw new Error("Saved content should be canonical manuscript HTML without runtime section wrappers");
  await page.reload({waitUntil:"domcontentloaded"});
  await page.locator(".mm-section").first().waitFor();
  if(await page.locator(".mm-section").count()!==5||await page.locator(".outline-item").count()!==4)throw new Error("Contents did not rebuild after refresh");

  await page.locator("a.brand").click();
  await page.locator("#returnToProject").waitFor();
  await page.locator("#returnToProject").click();
  await page.locator(".mm-section").first().waitFor();
  if(await page.locator(".mm-section").count()!==5||await page.locator(".outline-item").count()!==4)throw new Error("Contents did not survive project-page round trip");

  await page.locator("#mobileIssuesTab").click();
  await page.locator("#wordsView .issue-card").first().waitFor();
  await page.locator("#wordsView .issue-card").first().click();
  await page.locator("#wordSearchPopover.open").waitFor();
  for(let i=0;i<30&&!(await page.evaluate(()=>window.getSelection().rangeCount));i++) await sleep(50);
  const highlightedText=()=>page.evaluate(()=>{
    const h=window.CSS?.highlights?.get("mm-editor-issue");
    return h&&h.size ? Array.from(h).map(range=>range.toString()).join("") : "";
  });
  if(await highlightedText()!=="alpha")throw new Error("Overused word did not receive the correct soft focus highlight");
  if(await page.locator(".mm-section-active").innerText().then(text=>!text.includes("Chapter One")))throw new Error("Overused word did not activate its containing chapter");
  await page.locator("#wordNext").click();
  const secondWord=await highlightedText();
  if(secondWord!=="alpha")throw new Error("Next word did not replace the focus highlight");
  await page.locator("#wordPrev").click();
  if(await highlightedText()!=="alpha")throw new Error("Previous word did not restore the prior focus");
  if(await page.locator("#wordSearchMeta").innerText()!=="Use 1 of 16")throw new Error("Previous word navigation did not move back to the first occurrence");

  await page.locator(".issue-tab").filter({hasText:"Passive"}).click();
  await page.locator("#passiveView .issue-card").first().click();
  if(await highlightedText()!=="The ball was thrown by John.")throw new Error("Passive issue did not receive the correct soft focus highlight: "+JSON.stringify(await highlightedText()));
  if(await page.locator(".mm-section-active").innerText().then(text=>!text.includes("Chapter One")))throw new Error("Passive issue did not activate its containing chapter");
  await page.locator(".issue-tab").filter({hasText:"Pacing"}).click();
  await page.locator("#pacingView .issue-card").first().click();
  if(await highlightedText()!=="alpha alpha alpha alpha. The ball was thrown by John.")throw new Error("Pacing issue did not replace the previous focus with the correct highlight");
  if(await page.locator(".mm-section-active").innerText().then(text=>!text.includes("Chapter One")))throw new Error("Pacing issue did not activate its containing chapter");

  await page.evaluate(()=>closeWordSearch());
  if(await page.evaluate(()=>window.CSS?.highlights?.has("mm-editor-issue") ? window.CSS.highlights.get("mm-editor-issue").size : 0)!==0)throw new Error("Issue highlight did not clear when closing focus");
  await page.evaluate(()=>{const e=document.getElementById("richEditor");e.innerHTML="<p>Preface text.</p><h1>Chapter One</h1><p>alpha alpha alpha alpha. The ball was thrown by John.</p><h1>Chapter Two</h1><p>alpha alpha alpha alpha.</p><h1>Chapter Three</h1><p>alpha alpha alpha alpha.</p>";e.dispatchEvent(new Event("input",{bubbles:true}));});
  for(let i=0;i<30&&await page.locator(".mm-section").count()!==4;i++) await sleep(100);
  if(await page.locator(".mm-section").count()!==4||await page.locator(".outline-item").count()!==3)throw new Error("Deleting a heading did not remove the stale Contents entry");
  await page.waitForTimeout(1200);
  await page.reload({waitUntil:"domcontentloaded"});
  await page.locator(".mm-section").first().waitFor();
  if(await page.locator(".mm-section").count()!==4||await page.locator(".outline-item").count()!==3)throw new Error("Deleted heading returned after reload");
  await browser.close();
} finally { server.kill("SIGTERM"); }