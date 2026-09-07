const $ = (selector, parent = document) => parent.querySelector(selector);
const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
const COLOR_PATTERN = /^#[0-9a-f]{6}$/i;
const FALLBACK_IMAGE = 'linear-gradient(135deg, #ff4c52, #202426)';
let projects = [];
let projectEls = [];
let activeIndex = 0;

async function loadProjects() {
  for (const url of ['/api/projects', '/projects.json']) {
    try {
      const response = await fetch(url, { credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok) continue;
      const data = await response.json();
      if (Array.isArray(data) && data.length) return data;
    } catch (_) {
      // The bundled JSON fallback keeps local Vite previews useful without the CMS backend.
    }
  }
  throw new Error('Selected work could not be loaded.');
}

function safeColor(value, fallback) {
  return COLOR_PATTERN.test(String(value || '')) ? value : fallback;
}

function safeImageStyle(image, color) {
  if (!image) return FALLBACK_IMAGE;
  const safeUrl = JSON.stringify(String(image));
  return `linear-gradient(135deg, ${color}55, transparent 62%), url(${safeUrl})`;
}

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function buildProject(project, index) {
  const article = createElement('article', `project${index === 0 ? ' is-active' : ''}`);
  article.dataset.index = String(index);
  article.setAttribute('role', 'listitem');
  article.tabIndex = 0;
  article.setAttribute('aria-label', `Open ${project.title} project`);

  const identity = document.createElement('div');
  identity.append(createElement('div', 'project__title', project.title));
  const swatches = createElement('div', 'swatches');
  const colors = Array.isArray(project.colors) ? project.colors : [];
  colors.slice(0, 3).forEach((value, colorIndex) => {
    const swatch = document.createElement('i');
    swatch.style.setProperty('--swatch', safeColor(value, ['#ff4c52', '#f0f0ed', '#111111'][colorIndex]));
    swatches.append(swatch);
  });
  identity.append(swatches);

  const meta = createElement('div', 'project__meta');
  meta.append(document.createTextNode(String(index + 1).padStart(2, '0')), document.createElement('br'), document.createTextNode(project.year));
  article.append(identity, meta, createElement('div', 'project__role', project.role), createElement('div', 'project__arrow', '↗'));

  const select = () => selectProject(index);
  article.addEventListener('mouseenter', select);
  article.addEventListener('focus', select);
  article.addEventListener('click', select);
  article.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      select();
    }
  });
  return article;
}

function setProjectName(container, project) {
  const role = createElement('span', '', project.role);
  container.replaceChildren(document.createTextNode(project.title), document.createElement('br'), role);
}

function selectProject(index) {
  if (!projects.length) return;
  activeIndex = (index + projects.length) % projects.length;
  const project = projects[activeIndex];
  const colors = [
    safeColor(project.colors?.[0], '#ff4c52'),
    safeColor(project.colors?.[1], '#d4ff4f'),
    safeColor(project.colors?.[2], '#783bcd'),
  ];
  projectEls.forEach((element, itemIndex) => element.classList.toggle('is-active', itemIndex === activeIndex));
  $('.preview__index').textContent = `${String(activeIndex + 1).padStart(2, '0')} / ${projects.length}`;
  $('.preview__title').textContent = project.title;
  $('.preview__type').textContent = project.role;
  $('.preview__description').textContent = project.description;
  $('.visual__label strong').textContent = String(activeIndex + 1).padStart(2, '0');
  $('.visual__label small').textContent = `/${projects.length}`;
  setProjectName($('.visual__project-name'), project);
  const imageStyle = safeImageStyle(project.image, colors[0]);
  $('.preview__image').style.backgroundImage = imageStyle;
  $('.visual__image').style.backgroundImage = imageStyle;
  $('.visual__shape--one').style.background = colors[0];
  $('.visual__shape--two').style.background = colors[1];
  $('.visual__shape--three').style.background = colors[2];
}

function renderProjects() {
  const list = $('.project-list');
  list.replaceChildren(...projects.map(buildProject));
  projectEls = $$('.project', list);
  const total = String(projects.length).padStart(2, '0');
  const sectionCount = $('.section-intro .eyebrow span:last-child');
  if (sectionCount) sectionCount.textContent = `01 — ${total}`;
  selectProject(0);
}

function openPanel(name) {
  const panel = $(`[data-panel-view="${name}"]`);
  if (!panel) return;
  panel.classList.add('is-open');
  panel.removeAttribute('aria-hidden');
  panel.removeAttribute('inert');
  panel.querySelector('.panel__close').focus();
  $$('.panel').filter((other) => other !== panel).forEach((other) => {
    other.classList.remove('is-open');
    other.setAttribute('aria-hidden', 'true');
    other.setAttribute('inert', '');
  });
}

function closePanels() {
  $$('.panel').forEach((panel) => {
    panel.classList.remove('is-open');
    panel.setAttribute('aria-hidden', 'true');
    panel.setAttribute('inert', '');
  });
}

async function init() {
  try {
    projects = await loadProjects();
    renderProjects();
  } catch (error) {
    $('.project-list').append(createElement('p', 'project-load-error', error.message));
  }

  $('.visual__next').addEventListener('click', () => selectProject(activeIndex + 1));
  $$('[data-panel]').forEach((trigger) => trigger.addEventListener('click', () => openPanel(trigger.dataset.panel)));
  $$('.panel__close').forEach((button) => button.addEventListener('click', closePanels));
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') closePanels(); });

  const menuButton = $('.menu-button');
  menuButton.addEventListener('click', () => {
    const isOpen = $('.nav').classList.toggle('is-open');
    menuButton.setAttribute('aria-expanded', String(isOpen));
  });
  $$('.nav a, .nav button').forEach((link) => link.addEventListener('click', () => {
    $('.nav').classList.remove('is-open');
    menuButton.setAttribute('aria-expanded', 'false');
  }));
}

init();
