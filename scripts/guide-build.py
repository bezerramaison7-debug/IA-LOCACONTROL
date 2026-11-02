"""Builds docs/guia-visual/index.html from steps.json. The page works offline, from a folder."""

import json
from pathlib import Path

GUIDE = Path(__file__).resolve().parents[1] / "docs" / "guia-visual"
steps = json.loads((GUIDE / "steps.json").read_text(encoding="utf-8"))
missing = [
    f"{kind}/{step['id']}.{ext}"
    for step in steps
    for kind, ext in (("img", "png"), ("audio", "wav"))
    if not (GUIDE / kind / f"{step['id']}.{ext}").is_file()
]
if missing:
    raise SystemExit("Arquivos ausentes: " + ", ".join(missing))

PAGE = """<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LocaControl — Guia visual narrado</title>
<style>
  :root { --bg:#f6f8fb; --surface:#fff; --text:#172033; --muted:#5b6577; --line:#d5dbe5;
          --primary:#2563eb; --primary-text:#fff; --band:#eef2f9; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#0b1120; --surface:#111827; --text:#e5e7eb; --muted:#9aa4b5; --line:#263247;
            --primary:#60a5fa; --primary-text:#0b1120; --band:#172033; }
  }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
         font:16px/1.5 Inter, system-ui, "Segoe UI", sans-serif; }
  header { padding:20px 16px 8px; max-width:1200px; margin:0 auto; }
  h1 { font-size:1.4rem; margin:0 0 4px; }
  header p { margin:0; color:var(--muted); }
  main { max-width:1200px; margin:0 auto; padding:8px 16px 40px; display:grid; gap:16px;
         grid-template-columns:minmax(0,1fr) 300px; }
  @media (max-width: 900px) { main { grid-template-columns:minmax(0,1fr); } nav { order:2; } }
  .stage, nav { background:var(--surface); border:1px solid var(--line); border-radius:12px; }
  .stage { padding:16px; min-width:0; }
  .kicker { color:var(--muted); font-size:.85rem; text-transform:uppercase; letter-spacing:.04em; }
  h2 { margin:2px 0 12px; font-size:1.25rem; }
  .shot { width:100%; height:auto; display:block; border:1px solid var(--line); border-radius:8px;
          background:var(--band); }
  .text { margin:14px 0 8px; }
  .tips { margin:0; padding-left:20px; color:var(--muted); }
  .controls { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-top:14px; }
  button { font:inherit; padding:9px 14px; border-radius:8px; border:1px solid var(--line);
           background:var(--surface); color:var(--text); cursor:pointer; min-height:44px; }
  button.primary { background:var(--primary); color:var(--primary-text); border-color:var(--primary);
                   font-weight:600; }
  button:disabled { opacity:.5; cursor:default; }
  button:focus-visible, nav button:focus-visible { outline:3px solid var(--primary); outline-offset:2px; }
  .progress { flex:1 1 160px; height:6px; background:var(--band); border-radius:3px; overflow:hidden; }
  .progress span { display:block; height:100%; width:0; background:var(--primary); }
  .count { color:var(--muted); font-variant-numeric:tabular-nums; }
  nav { padding:8px; max-height:80vh; overflow:auto; align-self:start; }
  nav h3 { font-size:.8rem; text-transform:uppercase; letter-spacing:.04em; color:var(--muted);
           margin:12px 8px 4px; }
  nav button { display:block; width:100%; text-align:left; border:0; background:none; padding:8px;
               min-height:40px; border-radius:6px; }
  nav button[aria-current="true"] { background:var(--band); font-weight:600; }
  .note { color:var(--muted); font-size:.9rem; margin-top:10px; }
</style>
</head>
<body>
<header>
  <h1>LocaControl — Guia visual narrado</h1>
  <p>Percurso pelas telas do sistema, com narração. As imagens usam dados de exemplo.</p>
</header>
<main>
  <section class="stage" aria-live="polite">
    <div class="kicker" id="kicker"></div>
    <h2 id="title"></h2>
    <img class="shot" id="shot" alt="">
    <p class="text" id="text"></p>
    <ul class="tips" id="tips"></ul>
    <div class="controls">
      <button id="prev">Anterior</button>
      <button id="play" class="primary">Reproduzir com narração</button>
      <button id="next">Próximo</button>
      <div class="progress" aria-hidden="true"><span id="bar"></span></div>
      <span class="count" id="count"></span>
    </div>
    <p class="note">Reproduzir avança sozinho ao fim de cada narração, como um vídeo. Use as setas do
      teclado para mudar de passo e a barra de espaço para pausar.</p>
    <audio id="audio" preload="auto"></audio>
  </section>
  <nav aria-label="Passos do guia" id="menu"></nav>
</main>
<script>
const steps = __STEPS__;
const $ = (id) => document.getElementById(id);
const audio = $('audio');
let index = 0, playing = false;

function show(i, autoplay) {
  index = Math.max(0, Math.min(steps.length - 1, i));
  const step = steps[index];
  $('kicker').textContent = step.section + ' · passo ' + (index + 1) + ' de ' + steps.length;
  $('title').textContent = step.title;
  $('shot').src = 'img/' + step.id + '.png';
  $('shot').alt = 'Tela do LocaControl: ' + step.title;
  $('text').textContent = step.text;
  $('tips').replaceChildren(...step.tips.map((tip) => {
    const item = document.createElement('li'); item.textContent = tip; return item;
  }));
  $('count').textContent = (index + 1) + ' / ' + steps.length;
  $('prev').disabled = index === 0;
  $('next').disabled = index === steps.length - 1;
  document.querySelectorAll('#menu button').forEach((button, n) => {
    button.setAttribute('aria-current', n === index ? 'true' : 'false');
  });
  audio.src = 'audio/' + step.id + '.wav';
  $('bar').style.width = '0';
  if (autoplay) audio.play().catch(() => setPlaying(false));
}

function setPlaying(value) {
  playing = value;
  $('play').textContent = playing ? 'Pausar' : 'Reproduzir com narração';
  if (playing) audio.play().catch(() => setPlaying(false)); else audio.pause();
}

audio.addEventListener('timeupdate', () => {
  if (audio.duration) $('bar').style.width = (100 * audio.currentTime / audio.duration) + '%';
});
audio.addEventListener('ended', () => {
  if (!playing) return;
  if (index < steps.length - 1) setTimeout(() => show(index + 1, true), 700);
  else setPlaying(false);
});
$('play').addEventListener('click', () => setPlaying(!playing));
$('prev').addEventListener('click', () => show(index - 1, playing));
$('next').addEventListener('click', () => show(index + 1, playing));
document.addEventListener('keydown', (event) => {
  if (event.target.closest('nav')) return;
  if (event.key === 'ArrowRight') show(index + 1, playing);
  if (event.key === 'ArrowLeft') show(index - 1, playing);
  if (event.key === ' ' && event.target.tagName !== 'BUTTON') { event.preventDefault(); setPlaying(!playing); }
});

let section = '';
steps.forEach((step, n) => {
  if (step.section !== section) {
    section = step.section;
    const heading = document.createElement('h3'); heading.textContent = section; $('menu').append(heading);
  }
  const button = document.createElement('button');
  button.textContent = (n + 1) + '. ' + step.title;
  button.addEventListener('click', () => show(n, playing));
  $('menu').append(button);
});
show(0, false);
</script>
</body>
</html>
"""

html = PAGE.replace("__STEPS__", json.dumps(steps, ensure_ascii=False))
(GUIDE / "index.html").write_text(html, encoding="utf-8", newline="\n")
print(f"index.html gerado com {len(steps)} passos")
