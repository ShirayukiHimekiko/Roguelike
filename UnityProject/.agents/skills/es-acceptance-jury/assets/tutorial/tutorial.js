(() => {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const scenes = [...document.querySelectorAll('.scene')];
  const links = [...document.querySelectorAll('.scene-nav a')];
  const media = window.matchMedia('(prefers-reduced-motion: reduce)');
  const captions = {
    install: ['交给 AI', '一句安装', '确认可用'],
    use: ['接住目标', '各自核查', '继续推进'],
    join: ['接当前任务', '指出问题', '修后继续'],
    close: ['看成果', '找反例', '核回结果'],
    consider: ['你的想法', '本人回应', '接回行动'],
    core: ['当前任务', '指出负担', '核因续作']
  };
  const coreFeatures = {
    quality: { name: '品质', title: '拒绝无效堆叠。\n修问题，不停摆。', hint: '依据断裂就查因改法，目标与未闭仍接回。正常路径继续，目标不被偷换。', steps: ['当前任务', '指出负担', '核因续作'] },
    plan: { name: '同版', title: '同一版方案。\n两位各自核。', hint: '双方看同一版原话与方案，工作 AI 接住第一项动作，再开始制作。', steps: ['对齐对象', '发现错版', '接回制作'], preamble: '同一份原话，分别核对', tiles: [['F', '功能视角', 'v1'], ['v1', '当前方案', '核范围'], ['A', '架构视角', 'v1']], outcome: ['先把对象与范围对齐', 'v1 和 v2 不能拼成双通过', '同版核回后，工作端接住第一步'], note: '同版机制演示，不代表已取得真实方案票' },
    evidence: { name: '证据', title: '依据对得上。\n结论有边界。', hint: '不同问题，需要不同证据。源码、画面和真实过程，各自证明对应结果。', steps: ['核源码', '看画面', '验过程'], preamble: '这句话，凭什么成立？', tiles: [['{ }', '源码', '计算与关系'], ['▧', '画面', '主次与辨识'], ['↗', '过程', '操作与后继']], outcome: ['源码能定位真实计算关系', '画面要亲看，不能只看代码', '动态结果，需要对应的过程'], note: '示意图不补视频、声音或实际操作感知' },
    advance: { name: '推进', title: '一边持续制作。\n一边主动查漏。', hint: '工作 AI 连续做，陪审主动查。必要问题即时接回，不让无关工作陪着停。', steps: ['交清目标', '并行推进', '及时接回'], preamble: '共同目标，独立职责', outcome: ['交清当前任务与必要未闭', '持续制作，也持续查漏', '修对应问题，就绪工作继续'], note: '进度条是协作示意，不是实际任务完成率' },
    resources: { name: '资源', title: '缺什么就找。\n拿到还要会用。', hint: '主动找参考、工具和合适资源。需要外部生图协助时，先问你再精备材料。', steps: ['找缺口', '查供给', '验采用'], preamble: '从当前任务缺什么出发', tiles: [['↗', '参考', '看真实对象'], ['⌁', '工具', '核可调用性'], ['▧', '图像', '服务当前目标']], outcome: ['先查决定下一步的缺口', '找到文件，不等于能用', '接入当前任务，再看真实效果'], note: '资源路径示意，不代表本机已有这些供给' },
    handoff: { name: '接续', title: '接得住原话。\n续得上工作。', hint: '从项目真实接点继续。原话、当前产物和必要未闭，都有下一位能找到的位置。', steps: ['找接点', '核当前', '继续做'], preamble: '从真实项目接点进入', tiles: [['↳', '原目标', '保真实修订'], ['▤', '当前源', '核版本归属'], ['…', '必要未闭', '不假装消失']], outcome: ['先找到现在实际做到哪', '回到原件，核当前版本', '下一位接住原话和未闭继续'], note: '接续示意，不创建记录、角色或后台' }
  };
  const coreVisual = $('core').querySelector('.visual');
  const qualityMarkup = coreVisual.innerHTML;
  const state = { key: '', step: 0, playing: true, manualReduced: false, feature: 'quality' };
  let timer = null, toastTimer = null, navFocusKey = null;
  function reduced() { return media.matches || state.manualReduced; }
  function cancelTimer() { if (timer !== null) { clearTimeout(timer); timer = null; } }
  function scene() { return $(state.key); }
  function notify(message) {
    clearTimeout(toastTimer); $('toast').textContent = message; $('toast').classList.add('show');
    toastTimer = setTimeout(() => $('toast').classList.remove('show'), 3400);
  }
  function syncPlayback() {
    cancelTimer();
    const active = scene();
    const runnable = Boolean(active);
    const running = runnable && state.playing && !reduced() && !document.hidden;
    scenes.forEach((item) => item.classList.toggle('playing', item === active && running));
    document.body.classList.toggle('no-motion', reduced());
    $('motion-toggle').setAttribute('aria-pressed', String(reduced()));
    $('play-toggle').textContent = reduced() ? '→' : state.playing ? 'Ⅱ' : '▶';
    $('play-toggle').setAttribute('aria-label', reduced() ? '看下一步' : state.playing ? '暂停演示' : '播放演示');
    $('play-status').textContent = reduced() ? '已减弱动画，可直接选一步看。' : running ? '可暂停，也可直接选一步看。' : document.hidden ? '页面隐藏，演示已暂停。' : '当前停在这一刻，随时继续。';
    if (running) timer = setTimeout(() => {
      timer = null;
      if (state.step < 2) { state.step += 1; render(); }
      else { state.playing = false; syncPlayback(); }
    }, 3400);
  }
  function render() {
    const active = scene(); if (!active) return;
    active.dataset.step = String(state.step);
    links.forEach((link) => {
      const current = link.dataset.scene === state.key;
      if (current) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    });
    $('current-scene-name').textContent = links.find((link) => link.dataset.scene === state.key).querySelector('.nav-full').textContent.trim();
    document.querySelectorAll('.phase-picker button').forEach((button, i) => {
      button.querySelector('b').textContent = captions[state.key][i];
      button.setAttribute('aria-label', captions[state.key][i]);
      if (state.step === i) button.setAttribute('aria-current', 'step'); else button.removeAttribute('aria-current');
    });
    if (state.key === 'core' && state.feature === 'plan') {
      const tiles = coreVisual.querySelectorAll('.core-tile');
      tiles[0].querySelector('span').textContent = state.step === 2 ? 'v2' : 'v1';
      tiles[1].querySelector('b').textContent = state.step === 0 ? 'v1' : 'v2';
      tiles[2].querySelector('span').textContent = state.step === 0 ? 'v1' : 'v2';
    }
    syncPlayback();
  }
  function chooseFeature(key) {
    const feature = coreFeatures[key]; if (!feature) return;
    state.feature = key; state.step = 0; state.playing = !reduced();
    $('core-topic').textContent = '设计内核 / ' + feature.name;
    const core = $('core');
    const command = core.querySelector('[data-command]'); command.replaceChildren();
    feature.title.split('\n').forEach((line, index) => { if (index) command.append(document.createElement('br')); command.append(document.createTextNode(line)); });
    core.querySelector('.lesson-hint').textContent = feature.hint;
    document.querySelectorAll('.core-tabs button').forEach((button) => button.setAttribute('aria-pressed', String(button.dataset.feature === key)));
    captions.core = feature.steps;
    coreVisual.dataset.art = key === 'quality' ? 'join' : 'core-' + key;
    if (key === 'quality') coreVisual.innerHTML = qualityMarkup;
    else {
      const diagram = key === 'advance'
        ? '<div class="parallel-rows"><div><strong>工作 AI</strong><span class="parallel-track"><i></i></span></div><div><strong>F 查结果</strong><span class="parallel-track"><i></i></span></div><div><strong>A 查关系</strong><span class="parallel-track"><i></i></span></div></div>'
        : '<div class="core-tiles">' + feature.tiles.map((tile) => '<div class="core-tile"><b>' + tile[0] + '</b><strong>' + tile[1] + '</strong><span>' + tile[2] + '</span></div>').join('') + '</div>';
      coreVisual.innerHTML = '<div class="visual-label"><span class="live-dot"></span>设计内核 / ' + feature.name + '</div><div class="core-preamble">' + feature.preamble + '</div>' + diagram + '<div class="core-outcome">' + feature.outcome.map((text, i) => '<span class="phase-text" data-phase="' + i + '">' + text + '</span>').join('') + '</div><div class="result-strip"><span class="result-mark">↳</span>' + feature.steps.map((text, i) => '<span class="phase-text" data-phase="' + i + '">' + text + '</span>').join('') + '</div><span class="demo-note">' + feature.note + '</span>';
    }
    render();
  }
  function readLocation() {
    const key = location.hash.slice(1);
    const next = scenes.some((item) => item.id === key) ? key : 'use';
    if (next !== state.key) {
      cancelTimer(); state.key = next; state.step = 0; state.playing = !reduced(); render();
    }
    if (navFocusKey) {
      links.find((link) => link.dataset.scene === navFocusKey).focus({preventScroll: true});
      navFocusKey = null;
    }
  }
  links.forEach((link, i) => link.addEventListener('keydown', (event) => {
    if (!['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) return;
    event.preventDefault();
    const index = event.key === 'Home' ? 0 : event.key === 'End' ? links.length - 1 : (i + (event.key === 'ArrowDown' ? 1 : links.length - 1)) % links.length;
    navFocusKey = links[index].dataset.scene;
    if (location.hash === '#' + navFocusKey) readLocation();
    else location.hash = navFocusKey;
  }));
  $('play-toggle').addEventListener('click', () => {
    if (reduced()) { state.step = (state.step + 1) % 3; state.playing = false; render(); return; }
    if (!state.playing && state.step === 2) state.step = 0;
    state.playing = !state.playing; render();
  });
  $('replay').addEventListener('click', () => { state.step = 0; state.playing = !reduced(); render(); });
  document.querySelectorAll('.phase-picker button').forEach((button) => button.addEventListener('click', () => { state.playing = false; state.step = Number(button.dataset.step); render(); }));
  $('motion-toggle').addEventListener('click', () => {
    if (media.matches) { notify('正在遵循系统的减弱动画设置。'); return; }
    state.manualReduced = !state.manualReduced; state.playing = false; render();
  });
  if (media.addEventListener) media.addEventListener('change', () => { state.playing = false; render(); });
  document.querySelectorAll('.copy-button').forEach((button) => button.addEventListener('click', async () => {
    const command = button.closest('.scene').querySelector('[data-command]');
    try {
      if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('Clipboard unavailable');
      await navigator.clipboard.writeText(command.textContent.trim());
      notify('已复制。回到当前 AI 对话，直接发送。');
    } catch (_) {
      const selection = window.getSelection(), range = document.createRange(); range.selectNodeContents(command);
      if (selection) { selection.removeAllRanges(); selection.addRange(range); }
      notify('已选中文字，请按 Ctrl+C / ⌘C 或长按复制。');
    }
  }));
  document.querySelectorAll('[data-close-mode]').forEach((button) => button.addEventListener('click', () => {
    const isDebate = button.dataset.closeMode === 'debate';
    $('close').querySelector('[data-command]').textContent = isDebate ? '开始辩论' : '开始收尾';
    document.querySelectorAll('[data-close-mode]').forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
    state.step = 0; state.playing = !reduced(); render();
  }));
  document.querySelectorAll('.core-tabs button').forEach((button) => button.addEventListener('click', () => chooseFeature(button.dataset.feature)));
  $('about').addEventListener('click', () => $('about-dialog').showModal());
  document.querySelector('.dialog-close').addEventListener('click', () => $('about-dialog').close());
  $('about-dialog').addEventListener('click', (event) => { if (event.target === $('about-dialog')) $('about-dialog').close(); });
  window.addEventListener('hashchange', readLocation);
  document.addEventListener('visibilitychange', syncPlayback);
  window.addEventListener('pagehide', () => { state.playing = false; cancelTimer(); clearTimeout(toastTimer); });
  readLocation();
  document.documentElement.classList.remove('no-js');
})();
