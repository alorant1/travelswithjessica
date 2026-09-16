const express = require('express');
const multer = require('multer');
const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

const app = express();
const PORT = 3456;
const SITE_ROOT = path.resolve(__dirname, '..');

app.use(express.json({ limit: '10mb' }));
app.use(express.static(__dirname));

app.get('/', (req, res) => res.sendFile(path.join(__dirname, 'editor.html')));

// Image upload storage
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    const dir = path.join(SITE_ROOT, 'images', 'uploads');
    fs.mkdirSync(dir, { recursive: true });
    cb(null, dir);
  },
  filename: (req, file, cb) => {
    const ext = path.extname(file.originalname).toLowerCase();
    const base = path.basename(file.originalname, ext)
      .replace(/[^a-z0-9]/gi, '-').toLowerCase().slice(0, 40);
    cb(null, `${base}-${Date.now()}${ext}`);
  }
});
const upload = multer({ storage, limits: { fileSize: 24 * 1024 * 1024 } });

// List all post HTML files (excludes index.html)
app.get('/api/posts', (req, res) => {
  const postsDir = path.join(SITE_ROOT, 'posts');
  const files = [];
  function walk(dir, rel) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      const relPath = path.join(rel, entry.name).replace(/\\/g, '/');
      if (entry.isDirectory()) walk(full, relPath);
      else if (entry.name.endsWith('.html') && entry.name !== 'index.html') {
        files.push(relPath);
      }
    }
  }
  walk(postsDir, 'posts');
  res.json(files.sort());
});

// Get a post's raw HTML
app.get('/api/post', (req, res) => {
  const file = req.query.file;
  if (!file || !file.startsWith('posts/') || file.includes('..')) {
    return res.status(400).json({ error: 'Invalid path' });
  }
  const full = path.join(SITE_ROOT, file);
  if (!fs.existsSync(full)) return res.status(404).json({ error: 'Not found' });
  res.json({ html: fs.readFileSync(full, 'utf-8') });
});

// Save blocks → rebuild HTML → git commit + push + deploy
app.post('/api/save', (req, res) => {
  const { file, blocks, commitMessage } = req.body;
  if (!file || !file.startsWith('posts/') || file.includes('..')) {
    return res.status(400).json({ error: 'Invalid path' });
  }
  const fullPath = path.join(SITE_ROOT, file);
  const original = fs.readFileSync(fullPath, 'utf-8');

  let newHtml;
  try {
    newHtml = rebuildHtml(original, blocks);
  } catch (e) {
    return res.status(500).json({ error: `HTML rebuild failed: ${e.message}` });
  }

  fs.writeFileSync(fullPath, newHtml, 'utf-8');

  const log = [];
  const run = (cmd, label) => {
    try {
      const out = execSync(cmd, { cwd: SITE_ROOT, stdio: 'pipe', timeout: 120000 }).toString().trim();
      log.push({ step: label, ok: true, out });
      return true;
    } catch (e) {
      const msg = (e.stderr || e.stdout || e.message || '').toString().trim();
      log.push({ step: label, ok: false, out: msg });
      return false;
    }
  };

  const postName = path.basename(file, '.html');
  const msg = commitMessage || `Editor: update ${postName}`;

  run('git add -A', 'git add');

  // Check if there's actually anything to commit
  const status = execSync('git status --porcelain', { cwd: SITE_ROOT }).toString().trim();
  if (!status) {
    return res.json({ ok: true, log, message: 'No changes to commit — already up to date.' });
  }

  if (!run(`git commit -m "${msg.replace(/"/g, '\\"')}\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"`, 'git commit')) {
    return res.status(500).json({ ok: false, log, error: 'git commit failed' });
  }
  if (!run('git push', 'git push')) {
    return res.status(500).json({ ok: false, log, error: 'git push failed — check credentials' });
  }
  if (!run('npx wrangler deploy', 'wrangler deploy')) {
    return res.status(500).json({ ok: false, log, error: 'Deploy failed' });
  }

  res.json({ ok: true, log, message: 'Saved, pushed to GitHub, and deployed live!' });
});

// Upload image → save to images/uploads/
app.post('/api/upload-image', upload.single('image'), (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'No file' });
  res.json({ url: `/images/uploads/${req.file.filename}` });
});

// ── HTML reconstruction helpers ──────────────────────────────────────────────

function esc(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function escAttr(str) {
  return String(str ?? '').replace(/"/g, '&quot;');
}

function serializeBlocks(blocks) {
  const parts = [];
  for (const b of blocks) {
    if (b.type === 'heading') {
      parts.push(`  <h2>${esc(b.text)}</h2>`);
    } else if (b.type === 'text') {
      const paras = (b.paragraphs || []).map(p => `  <p>${p}</p>`).join('\n');
      if (paras) parts.push(paras);
    } else if (b.type === 'photo') {
      const loading = b.loading ? ` loading="${escAttr(b.loading)}"` : '';
      const lines = [
        `  <div class="photo-block">`,
        `    <img src="${escAttr(b.src)}" alt="${escAttr(b.alt ?? '')}"${loading}>`,
        `  </div>`
      ];
      for (const p of (b.paragraphs || [])) lines.push(`  <p>${p}</p>`);
      parts.push(lines.join('\n'));
    } else if (b.type === 'video') {
      const lines = [
        `  <div class="video-block">`,
        `    <iframe src="${escAttr(b.src)}" title="${escAttr(b.title ?? '')}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>`,
        `  </div>`
      ];
      for (const p of (b.paragraphs || [])) lines.push(`  <p>${p}</p>`);
      parts.push(lines.join('\n'));
    }
  }
  return parts.join('\n\n');
}

function rebuildHtml(html, blocks) {
  const articleOpen = '<article class="post-content">';
  const articleClose = '</article>';
  const startIdx = html.indexOf(articleOpen);
  const endIdx = html.lastIndexOf(articleClose);
  if (startIdx === -1 || endIdx === -1) throw new Error('No <article class="post-content"> found');

  const articleInner = html.substring(startIdx + articleOpen.length, endIdx);

  // Preserve the breadcrumb nav
  const bcMatch = articleInner.match(/<nav class="breadcrumb"[\s\S]*?<\/nav>/);
  const breadcrumb = bcMatch ? bcMatch[0] : '';

  const blocksHtml = serializeBlocks(blocks);
  const newArticle = breadcrumb
    ? `${articleOpen}\n\n  ${breadcrumb}\n\n${blocksHtml}\n\n${articleClose}`
    : `${articleOpen}\n\n${blocksHtml}\n\n${articleClose}`;

  return html.substring(0, startIdx) + newArticle + html.substring(endIdx + articleClose.length);
}

app.listen(PORT, () => {
  console.log(`\n✈  Travels with Jessica — Content Editor`);
  console.log(`   Open: http://localhost:${PORT}\n`);
});
