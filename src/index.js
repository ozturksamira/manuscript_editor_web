const COOKIE = "mm_session";
const SESSION_DAYS = 30;
const MAX_CONTENT_BYTES = 1_500_000;

function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...headers },
  });
}

function b64url(bytes) {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function utf8b64url(value) {
  return b64url(new TextEncoder().encode(value));
}

function fromB64url(value) {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((value.length + 3) % 4);
  const binary = atob(padded);
  return Uint8Array.from(binary, (char) => char.charCodeAt(0));
}

async function hmac(secret, value) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"],
  );
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(value)));
}

async function createSession(userId, secret) {
  const payload = utf8b64url(JSON.stringify({
    uid: Number(userId),
    exp: Date.now() + SESSION_DAYS * 86400000,
  }));
  const signature = b64url(await hmac(secret, payload));
  return payload + "." + signature;
}

async function verifySession(token, secret) {
  if (!token || !token.includes(".")) return null;
  const [payload, signature] = token.split(".", 2);
  if (!payload || !signature) return null;
  try {
    const expected = await hmac(secret, payload);
    const actual = fromB64url(signature);
    if (actual.length !== expected.length) return null;
    let mismatch = 0;
    for (let i = 0; i < expected.length; i++) mismatch |= expected[i] ^ actual[i];
    if (mismatch !== 0) return null;
    const data = JSON.parse(new TextDecoder().decode(fromB64url(payload)));
    if (!data.uid || !data.exp || Date.now() >= data.exp) return null;
    return { id: Number(data.uid) };
  } catch {
    return null;
  }
}

function parseCookies(header) {
  const cookies = {};
  for (const part of (header || "").split(";")) {
    const [key, ...rest] = part.trim().split("=");
    if (key) cookies[key] = rest.join("=");
  }
  return cookies;
}

function cookieHeader(value, maxAge) {
  const parts = [
    `${COOKIE}=${value}`,
    "Path=/",
    "HttpOnly",
    "Secure",
    "SameSite=Lax",
  ];
  if (maxAge !== undefined) parts.push(`Max-Age=${maxAge}`);
  return parts.join("; ");
}

async function hashPassword(password) {
  const iterations = 120000;
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = new Uint8Array(await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations },
    key,
    256,
  ));
  return `pbkdf2_sha256$${iterations}$${b64url(salt)}$${b64url(bits)}`;
}

async function verifyPassword(password, stored) {
  const [scheme, rawIterations, salt64, hash64] = String(stored || "").split("$");
  if (scheme !== "pbkdf2_sha256") return false;
  const iterations = Number(rawIterations);
  if (!iterations || !salt64 || !hash64) return false;
  try {
    const salt = fromB64url(salt64);
    const expected = fromB64url(hash64);
    const key = await crypto.subtle.importKey(
      "raw",
      new TextEncoder().encode(password),
      "PBKDF2",
      false,
      ["deriveBits"],
    );
    const actual = new Uint8Array(await crypto.subtle.deriveBits(
      { name: "PBKDF2", hash: "SHA-256", salt, iterations },
      key,
      expected.length * 8,
    ));
    if (actual.length !== expected.length) return false;
    let mismatch = 0;
    for (let i = 0; i < expected.length; i++) mismatch |= actual[i] ^ expected[i];
    return mismatch === 0;
  } catch {
    return false;
  }
}

function db(env) {
  return env.DB;
}

async function first(env, sql, ...values) {
  return db(env).prepare(sql).bind(...values).first();
}

async function all(env, sql, ...values) {
  const result = await db(env).prepare(sql).bind(...values).all();
  return result.results || [];
}

async function run(env, sql, ...values) {
  return db(env).prepare(sql).bind(...values).run();
}

async function currentUser(request, env) {
  const cookies = parseCookies(request.headers.get("Cookie"));
  const session = await verifySession(cookies[COOKIE], env.SESSION_SECRET || "");
  if (!session) return null;
  const user = await first(env, "SELECT id, email FROM users WHERE id = ? LIMIT 1", session.id);
  return user ? { id: Number(user.id), email: user.email } : null;
}

function requireSameOrigin(request) {
  const origin = request.headers.get("Origin");
  if (!origin) return true;
  return origin === new URL(request.url).origin;
}

function slugify(value) {
  return String(value || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 150) || "project";
}

async function uniqueSlug(env, userId, title, projectId = null) {
  const base = slugify(title);
  let candidate = base;
  for (let n = 2; n < 10000; n++) {
    const row = projectId
      ? await first(env, "SELECT id FROM projects WHERE user_id = ? AND slug = ? AND id != ? LIMIT 1", userId, candidate, projectId)
      : await first(env, "SELECT id FROM projects WHERE user_id = ? AND slug = ? LIMIT 1", userId, candidate);
    if (!row) return candidate;
    candidate = `${base}-${n}`;
  }
  throw new Error("Could not generate a unique project URL.");
}

function projectUrl(slug) {
  return "/project/" + encodeURIComponent(slug) + "/";
}

function decodeEntities(value) {
  return String(value || "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/gi, "&")
    .replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">")
    .replace(/&quot;/gi, '"')
    .replace(/&#39;/gi, "'")
    .replace(/&#x27;/gi, "'");
}

function htmlToText(value) {
  let text = String(value || "");
  text = text.replace(/<\s*(br|\/p|\/div|\/h[1-6]|\/li|\/blockquote|hr)\s*\/?>/gi, "\n");
  text = text.replace(/<[^>]*>/g, "");
  text = decodeEntities(text).replace(/\u00a0/g, " ");
  return text.replace(/[ \t]+/g, " ").replace(/ *\n */g, "\n").trim();
}

const ALLOWED_TAGS = new Set([
  "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
  "strong", "b", "em", "i", "u", "s", "strike", "br",
  "blockquote", "ul", "ol", "li", "a", "hr", "span", "mark",
]);

function safeStyle(value) {
  const allowed = new Set([
    "color", "background-color", "font-size", "text-align",
    "font-family", "letter-spacing", "margin-left", "margin-right",
  ]);
  const output = [];
  for (const declaration of String(value || "").split(";")) {
    const index = declaration.indexOf(":");
    if (index < 0) continue;
    const name = declaration.slice(0, index).trim().toLowerCase();
    const val = declaration.slice(index + 1).trim();
    if (!allowed.has(name)) continue;
    if (!/^(?:#[0-9a-f]{3,8}|[a-zA-Z ]+|[0-9.]+(?:px|pt|em|rem|%)?)$/i.test(val)) continue;
    output.push(`${name}:${val}`);
  }
  return output.join(";");
}

function sanitizeHtml(value) {
  let html = String(value || "");
  html = html.replace(/<!--[\s\S]*?-->/g, "");
  html = html.replace(/<\s*(script|style|iframe|object|embed|svg|math|form|input|button|link|meta|base|video|audio)[^>]*>[\s\S]*?<\s*\/\s*\1\s*>/gi, "");
  html = html.replace(/<\s*(script|style|iframe|object|embed|svg|math|form|input|button|link|meta|base|video|audio)[^>]*\/?>/gi, "");
  return html.replace(/<\/?([a-z0-9]+)([^>]*)>/gi, (full, rawTag, rawAttrs) => {
    const tag = String(rawTag).toLowerCase();
    if (!ALLOWED_TAGS.has(tag)) return "";
    if (full.startsWith("</")) return ["br", "hr"].includes(tag) ? "" : `</${tag}>`;
    if (tag === "br" || tag === "hr") return `<${tag}>`;
    if (tag === "a") {
      const hrefMatch = String(rawAttrs || "").match(/\bhref\s*=\s*["']([^"']+)["']/i);
      const href = hrefMatch ? hrefMatch[1].trim() : "";
      if (/^(https?:|mailto:)/i.test(href)) {
        return `<a href="${escapeAttr(href)}" target="_blank" rel="noopener">`;
      }
      return "<a>";
    }
    const styleMatch = String(rawAttrs || "").match(/\bstyle\s*=\s*["']([^"']*)["']/i);
    const style = styleMatch ? safeStyle(styleMatch[1]) : "";
    return style ? `<${tag} style="${escapeAttr(style)}">` : `<${tag}>`;
  }).trim();
}

function escapeAttr(value) {
  return String(value || "").replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function contentTooLarge(content) {
  return new TextEncoder().encode(String(content || "")).byteLength > MAX_CONTENT_BYTES;
}

async function asset(request, env, path) {
  const url = new URL(request.url);
  url.pathname = path;
  return env.ASSETS.fetch(new Request(url.toString(), request));
}

async function requireUser(request, env) {
  const user = await currentUser(request, env);
  if (!user) return null;
  return user;
}

function badMethod(message = "Method not allowed.") {
  return json({ error: message }, 405, { Allow: "GET, POST, DELETE" });
}

async function handleApi(request, env) {
  if (!requireSameOrigin(request)) return json({ error: "Cross-origin request blocked." }, 403);
  const url = new URL(request.url);
  const path = url.pathname;

  if (path === "/api/account" && request.method === "GET") {
    const user = await requireUser(request, env);
    if (!user) return json({ error: "Authentication required." }, 401);
    return json({ email: user.email });
  }

  if (path === "/auth" && request.method === "POST") {
    const body = await request.json().catch(() => ({}));
    const email = String(body.email || "").trim().toLowerCase();
    const password = String(body.password || "");
    const action = body.action || "login";
    if (!email || !password) return json({ error: "Email and password are required." }, 400);
    if (password.length < 8) return json({ error: "Your password must be at least 8 characters." }, 400);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return json({ error: "Please enter a valid email address." }, 400);

    const existing = await first(env, "SELECT id, email, password_hash FROM users WHERE email = ? LIMIT 1", email);
    if (action === "register") {
      if (existing) return json({ error: "An account with that email already exists. Please sign in." }, 409);
      const passwordHash = await hashPassword(password);
      const createdAt = new Date().toISOString();
      await run(env, "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)", email, passwordHash, createdAt);
      const user = await first(env, "SELECT id, email FROM users WHERE email = ? LIMIT 1", email);
      const slug = await uniqueSlug(env, Number(user.id), "Untitled manuscript");
      await run(
        env,
        "INSERT INTO projects (user_id, title, slug, source_filename, content, analysis_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        Number(user.id), "Untitled manuscript", slug, "", "", "{}", createdAt, createdAt,
      );
      const token = await createSession(user.id, env.SESSION_SECRET);
      return json({ status: "success", message: "Account created successfully." }, 200, {
        "Set-Cookie": cookieHeader(token, SESSION_DAYS * 86400),
      });
    }
    if (action === "login") {
      if (!existing || !(await verifyPassword(password, existing.password_hash))) {
        return json({ error: "Invalid email or password." }, 401);
      }
      const token = await createSession(existing.id, env.SESSION_SECRET);
      return json({ status: "success", message: "Logged in successfully." }, 200, {
        "Set-Cookie": cookieHeader(token, SESSION_DAYS * 86400),
      });
    }
    return json({ error: "Unknown authentication action." }, 400);
  }

  if (path === "/logout" && request.method === "POST") {
    return json({ status: "success" }, 200, {
      "Set-Cookie": cookieHeader("", 0),
    });
  }

  const user = await requireUser(request, env);
  if (!user) return json({ error: "Authentication required." }, 401);

  if (path === "/api/projects" && request.method === "GET") {
    const rows = await all(
      env,
      "SELECT id, title, slug, source_filename, created_at, updated_at FROM projects WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
      user.id,
    );
    return json({
      projects: rows.map((row) => ({
        id: Number(row.id),
        title: row.title,
        slug: row.slug,
        source_filename: row.source_filename || "",
        created_at: row.created_at,
        updated_at: row.updated_at,
        url: projectUrl(row.slug),
      })),
    });
  }

  if (path === "/api/projects" && request.method === "POST") {
    const body = await request.json().catch(() => ({}));
    const title = String(body.title || "Untitled manuscript").trim().slice(0, 160) || "Untitled manuscript";
    const slug = await uniqueSlug(env, user.id, title);
    const now = new Date().toISOString();
    await run(
      env,
      "INSERT INTO projects (user_id, title, slug, source_filename, content, analysis_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
      user.id, title, slug, "", "", "{}", now, now,
    );
    const project = await first(env, "SELECT id, title, slug, source_filename, content, analysis_json, created_at, updated_at FROM projects WHERE user_id = ? AND slug = ? LIMIT 1", user.id, slug);
    return json({ project: projectPayload(project, true) }, 201);
  }

  const projectMatch = path.match(/^\/api\/projects\/(\d+)(?:\/(analyze))?$/);
  if (projectMatch && request.method === "GET" && !projectMatch[2]) {
    const projectId = Number(projectMatch[1]);
    const project = await first(env, "SELECT id, title, slug, source_filename, content, analysis_json, created_at, updated_at FROM projects WHERE id = ? AND user_id = ? LIMIT 1", projectId, user.id);
    if (!project) return json({ error: "Project not found." }, 404);
    return json({ project: projectPayload(project, true) });
  }

  if (projectMatch && request.method === "POST" && !projectMatch[2]) {
    const projectId = Number(projectMatch[1]);
    const project = await first(env, "SELECT id, title, slug, source_filename, content, analysis_json FROM projects WHERE id = ? AND user_id = ? LIMIT 1", projectId, user.id);
    if (!project) return json({ error: "Project not found." }, 404);
    const body = await request.json().catch(() => ({}));
    const title = String(body.title || project.title).trim().slice(0, 160) || "Untitled manuscript";
    const content = sanitizeHtml(body.content !== undefined ? body.content : project.content || "");
    if (contentTooLarge(content)) return json({ error: "This manuscript is too large for the free hosted database. Keep each project below about 1.5 MB." }, 413);
    let slug = project.slug;
    if (title !== project.title) slug = await uniqueSlug(env, user.id, title, projectId);
    const analysis = body.analysis && typeof body.analysis === "object" ? JSON.stringify(body.analysis) : (project.analysis_json || "{}");
    const now = new Date().toISOString();
    await run(env, "UPDATE projects SET title = ?, slug = ?, content = ?, analysis_json = ?, updated_at = ? WHERE id = ? AND user_id = ?", title, slug, content, analysis, now, projectId, user.id);
    return json({ status: "success", updated_at: now, slug, url: projectUrl(slug) });
  }

  if (projectMatch && request.method === "POST" && projectMatch[2] === "analyze") {
    const projectId = Number(projectMatch[1]);
    const project = await first(env, "SELECT id FROM projects WHERE id = ? AND user_id = ? LIMIT 1", projectId, user.id);
    if (!project) return json({ error: "Project not found." }, 404);
    const body = await request.json().catch(() => ({}));
    const analysis = body.analysis && typeof body.analysis === "object" ? body.analysis : {};
    const now = new Date().toISOString();
    await run(env, "UPDATE projects SET analysis_json = ?, updated_at = ? WHERE id = ? AND user_id = ?", JSON.stringify(analysis), now, projectId, user.id);
    return json({ status: "success" });
  }

  if (path === "/api/projects/import" && request.method === "POST") {
    const body = await request.json().catch(() => ({}));
    const filename = String(body.filename || "").trim().slice(0, 255);
    const title = String(body.title || "Imported manuscript").trim().slice(0, 160) || "Imported manuscript";
    const content = sanitizeHtml(body.content || "");
    if (!filename || !content) return json({ error: "The manuscript file was empty." }, 400);
    if (!/\.(txt|docx|pdf)$/i.test(filename)) return json({ error: "Unsupported file type. Please use .txt, .docx, or .pdf." }, 400);
    if (contentTooLarge(content)) return json({ error: "This manuscript is too large for the free hosted database. Keep each project below about 1.5 MB." }, 413);
    const slug = await uniqueSlug(env, user.id, title);
    const now = new Date().toISOString();
    await run(env, "INSERT INTO projects (user_id, title, slug, source_filename, content, analysis_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", user.id, title, slug, filename, content, "{}", now, now);
    const project = await first(env, "SELECT id, title, slug, source_filename, content, analysis_json, created_at, updated_at FROM projects WHERE user_id = ? AND slug = ? LIMIT 1", user.id, slug);
    return json({ project: projectPayload(project, true) }, 201);
  }

  if (projectMatch && request.method === "DELETE" && !projectMatch[2]) {
    const projectId = Number(projectMatch[1]);
    const projectCount = await first(env, "SELECT COUNT(*) AS count FROM projects WHERE user_id = ?", user.id);
    if (Number(projectCount?.count || 0) <= 1) return json({ error: "Keep at least one project in your writing room." }, 400);
    const project = await first(env, "SELECT id FROM projects WHERE id = ? AND user_id = ? LIMIT 1", projectId, user.id);
    if (!project) return json({ error: "Project not found." }, 404);
    await run(env, "DELETE FROM projects WHERE id = ? AND user_id = ?", projectId, user.id);
    return json({ status: "success" });
  }

  const slugMatch = path.match(/^\/api\/projects\/by-slug\/([a-z0-9-]{1,150})$/);
  if (slugMatch && request.method === "GET") {
    const project = await first(env, "SELECT id, title, slug, source_filename, content, analysis_json, created_at, updated_at FROM projects WHERE slug = ? AND user_id = ? LIMIT 1", slugMatch[1], user.id);
    if (!project) return json({ error: "Project not found." }, 404);
    return json({ project: projectPayload(project, true) });
  }

  const exportMatch = path.match(/^\/api\/projects\/(\d+)\/export\/(txt|html)$/);
  if (exportMatch && request.method === "GET") {
    const project = await first(env, "SELECT id, title, content FROM projects WHERE id = ? AND user_id = ? LIMIT 1", Number(exportMatch[1]), user.id);
    if (!project) return json({ error: "Project not found." }, 404);
    const safeTitle = String(project.title || "manuscript").replace(/[^A-Za-z0-9._-]+/g, "_").replace(/^_+|_+$/g, "") || "manuscript";
    if (exportMatch[2] === "txt") {
      return new Response(htmlToText(project.content || ""), {
        headers: {
          "Content-Type": "text/plain; charset=utf-8",
          "Content-Disposition": `attachment; filename="${safeTitle}.txt"`,
        },
      });
    }
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>${escapeAttr(project.title)}</title><style>body{max-width:860px;margin:50px auto;padding:0 30px;background:#f7f5f2;color:#171411;font:17px/1.8 Georgia,serif}h1,h2,h3{color:#3f3027}hr{border:0;border-top:1px solid #c0ab9a;margin:2em 0}</style></head><body>${project.content || ""}</body></html>`;
    return new Response(html, {
      headers: {
        "Content-Type": "text/html; charset=utf-8",
        "Content-Disposition": `attachment; filename="${safeTitle}.html"`,
      },
    });
  }

  if (path === "/api/account/delete" && request.method === "POST") {
    const body = await request.json().catch(() => ({}));
    const password = String(body.password || "");
    const confirmation = String(body.confirmation || "").trim();
    if (confirmation !== "DELETE") return json({ error: "Type DELETE to confirm permanent account removal." }, 400);
    const record = await first(env, "SELECT password_hash FROM users WHERE id = ? LIMIT 1", user.id);
    if (!record || !(await verifyPassword(password, record.password_hash))) return json({ error: "Your password is incorrect." }, 401);
    await run(env, "DELETE FROM projects WHERE user_id = ?", user.id);
    await run(env, "DELETE FROM users WHERE id = ?", user.id);
    return json({ status: "deleted" }, 200, { "Set-Cookie": cookieHeader("", 0) });
  }

  return json({ error: "Not found." }, 404);
}

function projectPayload(row, includeContent = false) {
  const payload = {
    id: Number(row.id),
    title: row.title,
    slug: row.slug,
    source_filename: row.source_filename || "",
    created_at: row.created_at,
    updated_at: row.updated_at,
    url: projectUrl(row.slug),
  };
  if (includeContent) {
    let analysis = {};
    try { analysis = JSON.parse(row.analysis_json || "{}"); } catch {}
    payload.content = row.content || "";
    payload.analysis = analysis;
  }
  return payload;
}

export default {
  async fetch(request, env) {
    try {
      const url = new URL(request.url);
      if (url.pathname.startsWith("/api/") || url.pathname === "/auth" || url.pathname === "/logout") {
        return await handleApi(request, env);
      }

      const userRequired = url.pathname === "/projects/" ||
        url.pathname === "/projects" ||
        url.pathname === "/editor/" ||
        url.pathname === "/editor" ||
        /^\/project\/[a-z0-9-]+\/?$/i.test(url.pathname);

      if (userRequired) {
        const user = await requireUser(request, env);
        if (!user) return Response.redirect(new URL("/login/", request.url), 302);
        if (url.pathname === "/editor" || url.pathname === "/editor/") {
          const row = await first(env, "SELECT slug FROM projects WHERE user_id = ? ORDER BY updated_at DESC, id DESC LIMIT 1", user.id);
          if (!row) return Response.redirect(new URL("/projects/", request.url), 302);
          return Response.redirect(new URL(projectUrl(row.slug), request.url), 302);
        }
        const file = url.pathname.startsWith("/projects") ? "/projects.html" : "/editor.html";
        return asset(request, env, file);
      }

      if (url.pathname === "/login" || url.pathname === "/login/") return asset(request, env, "/login.html");
      if (url.pathname === "/") return asset(request, env, "/index.html");
      if (url.pathname === "/404.html") return asset(request, env, "/not_found.html");
      return asset(request, env, "/index.html");
    } catch (error) {
      console.error(error);
      return json({ error: "An unexpected server error occurred." }, 500);
    }
  },
};
