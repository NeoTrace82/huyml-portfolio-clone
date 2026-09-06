const projects = [
  { title: 'Lumen', year: '2026', role: 'Identity / Digital', description: 'A luminous identity for a new kind of creative technology studio.', colors: ['#f0b293','#efe4c0','#262a30'], image: 'https://images.unsplash.com/photo-1531058020387-3be344556be6?auto=format&fit=crop&w=1400&q=85' },
  { title: 'Field Notes', year: '2025', role: 'Editorial / Web', description: 'A tactile archive of places, people and the space between them.', colors: ['#152d3b','#d9d2c2','#d86d47'], image: 'https://images.unsplash.com/photo-1513364776144-60967b0f800f?auto=format&fit=crop&w=1400&q=85' },
  { title: 'Morrow', year: '2025', role: 'Brand / Direction', description: 'A quieter future for a studio making things by hand.', colors: ['#d7dbcb','#24312d','#ee9b4a'], image: 'https://images.unsplash.com/photo-1531058020387-3be344556be6?auto=format&fit=crop&w=1400&q=85&sat=-10' },
  { title: 'Common Ground', year: '2024', role: 'Digital / Campaign', description: 'Finding the warmth in a very functional digital service.', colors: ['#ff4f55','#161616','#f3e9dc'], image: 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=1400&q=85' },
  { title: 'Afterlight', year: '2024', role: 'Art Direction', description: 'A portfolio for images that refuse to stay still.', colors: ['#d8d2f5','#121217','#f28f9e'], image: 'https://images.unsplash.com/photo-1519608487953-e999c86e7455?auto=format&fit=crop&w=1400&q=85' },
  { title: 'Sonder', year: '2023', role: 'Strategy / Web', description: 'Making the complicated feel unexpectedly human.', colors: ['#9cd7b7','#ece3d2','#2f3b52'], image: 'https://images.unsplash.com/photo-1500534623283-312aade485b7?auto=format&fit=crop&w=1400&q=85' },
  { title: 'Soft Power', year: '2023', role: 'Identity / Launch', description: 'A visual language for the independent voices changing culture.', colors: ['#e6a4c2','#15151b','#b8dcf2'], image: 'https://images.unsplash.com/photo-1531058020387-3be344556be6?auto=format&fit=crop&w=1400&q=85&sat=-35' },
  { title: 'Northstar', year: '2022', role: 'Digital / Product', description: 'Helping a new platform look as ambitious as it feels.', colors: ['#d4ff4f','#343434','#f5f5f5'], image: 'https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1400&q=85' },
  { title: 'Commonplace', year: '2022', role: 'Editorial / Type', description: 'A small publication about the big things hiding in plain sight.', colors: ['#d08e58','#f2eadc','#353535'], image: 'https://images.unsplash.com/photo-1455390582262-044cdead277a?auto=format&fit=crop&w=1400&q=85' },
  { title: 'Nara', year: '2021', role: 'Portfolio / Web', description: 'A gentle digital home for a designer with a sharp point of view.', colors: ['#e9c8ad','#e6eef3','#22252a'], image: 'https://images.unsplash.com/photo-1497366811353-6870744d04b2?auto=format&fit=crop&w=1400&q=85' },
  { title: 'Good Intentions', year: '2021', role: 'Campaign / Film', description: 'A campaign that starts with a question, not an answer.', colors: ['#222a38','#f2d37e','#e9e5de'], image: 'https://images.unsplash.com/photo-1497366754035-f200968a6e72?auto=format&fit=crop&w=1400&q=85&sat=-35' },
  { title: 'Still / Moving', year: '2020', role: 'Art Direction', description: 'A study in contrast, rhythm and the beauty of a held breath.', colors: ['#d2d6d0','#171719','#e47a5f'], image: 'https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&w=1400&q=85&sat=-40' },
  { title: 'Melt', year: '2020', role: 'Packaging / Digital', description: 'A sweeter kind of system for a small-batch maker.', colors: ['#ffcb77','#fb7076','#57425e'], image: 'https://images.unsplash.com/photo-1531058020387-3be344556be6?auto=format&fit=crop&w=1400&q=85&hue=30' },
  { title: 'Ritual', year: '2019', role: 'Brand / Strategy', description: 'Building a daily practice into every detail of the experience.', colors: ['#c7a68f','#f1e9e1','#212121'], image: 'https://images.unsplash.com/photo-1500534623283-312aade485b7?auto=format&fit=crop&w=1400&q=85&sat=-40' },
  { title: 'Second Nature', year: '2019', role: 'Website / Direction', description: 'A more natural digital presence for a climate-minded collective.', colors: ['#9bb18f','#efeee7','#27352d'], image: 'https://images.unsplash.com/photo-1519608487953-e999c86e7455?auto=format&fit=crop&w=1400&q=85&sat=-25' },
  { title: 'Orbit', year: '2018', role: 'Identity / Web', description: 'A new identity for the people pushing beyond the obvious.', colors: ['#7045bd','#d5ff55','#17151e'], image: 'https://images.unsplash.com/photo-1531058020387-3be344556be6?auto=format&fit=crop&w=1400&q=85&hue=270' },
  { title: 'Tender', year: '2018', role: 'Photography / Web', description: 'A soft, cinematic frame for a collection of honest stories.', colors: ['#eeb3a7','#4e5665','#f1e4d6'], image: 'https://images.unsplash.com/photo-1513364776144-60967b0f800f?auto=format&fit=crop&w=1400&q=85&sat=-25' },
  { title: 'Good Form', year: '2017', role: 'Graphic / Print', description: 'A little discipline, a little mischief, and a lot of paper.', colors: ['#ede6d6','#ee454d','#262626'], image: 'https://images.unsplash.com/photo-1455390582262-044cdead277a?auto=format&fit=crop&w=1400&q=85&sat=-30' },
  { title: 'Huyml Vol.1', year: '2022', role: 'Portfolio / Digital', description: 'The first portfolio, and the one that changed everything.', colors: ['#1a1a1a','#c9c9c9','#ffffff'], image: 'https://images.unsplash.com/photo-1519608487953-e999c86e7455?auto=format&fit=crop&w=1400&q=85&sat=-70' }
];

const $ = (selector, parent = document) => parent.querySelector(selector);
const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const intro = $('.intro');
const site = $('.site');
const list = $('.project-list');
const preview = $('.work__preview');
let activeIndex = 0;

function projectMarkup(project, index) {
  return `<article class="project${index === 0 ? ' is-active' : ''}" data-index="${index}" role="listitem" tabindex="0" aria-label="Open ${project.title} project">
    <div><div class="project__title">${project.title}</div><div class="swatches">${project.colors.map(color => `<i style="--swatch:${color}"></i>`).join('')}</div></div>
    <div class="project__meta">${String(index + 1).padStart(2, '0')}<br />${project.year}</div>
    <div class="project__role">${project.role}</div>
    <div class="project__arrow">↗</div>
  </article>`;
}

// This is a fixed, local project catalogue; no user or network content is interpolated.
list.innerHTML = projects.map(projectMarkup).join('');
const projectEls = $$('.project');

function selectProject(index) {
  activeIndex = (index + projects.length) % projects.length;
  const project = projects[activeIndex];
  projectEls.forEach((el, i) => el.classList.toggle('is-active', i === activeIndex));
  $('.preview__index').textContent = `${String(activeIndex + 1).padStart(2, '0')} / 19`;
  $('.preview__title').textContent = project.title;
  $('.preview__type').textContent = project.role;
  $('.visual__label strong').textContent = String(activeIndex + 1).padStart(2, '0');
  $('.visual__project-name').innerHTML = `${project.title}<br /><span>${project.role}</span>`;
  $('.preview__image').style.backgroundImage = `linear-gradient(135deg, ${project.colors[0]}55, transparent 58%), url("${project.image}")`;
}

projectEls.forEach((el) => {
  const index = Number(el.dataset.index);
  el.addEventListener('mouseenter', () => selectProject(index));
  el.addEventListener('focus', () => selectProject(index));
  el.addEventListener('click', () => selectProject(index));
  el.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectProject(index); }
  });
});
$('.visual__next').addEventListener('click', () => selectProject(activeIndex + 1));
selectProject(0);

function enterSite() {
  intro.classList.add('is-done');
  site.classList.add('is-ready');
  site.removeAttribute('aria-hidden');
  window.setTimeout(() => intro.remove(), 900);
}
window.setTimeout(enterSite, reduceMotion ? 0 : 4300);
$('.intro__skip').addEventListener('click', enterSite);

function openPanel(name) {
  const panel = $(`[data-panel-view="${name}"]`);
  panel.classList.add('is-open');
  panel.removeAttribute('aria-hidden');
  panel.removeAttribute('inert');
  panel.querySelector('.panel__close').focus();
  $$('.panel').filter(other => other !== panel).forEach(other => { other.classList.remove('is-open'); other.setAttribute('aria-hidden', 'true'); other.setAttribute('inert', ''); });
}
function closePanels() {
  $$('.panel').forEach(panel => { panel.classList.remove('is-open'); panel.setAttribute('aria-hidden', 'true'); panel.setAttribute('inert', ''); });
}
$$('[data-panel]').forEach(trigger => trigger.addEventListener('click', () => openPanel(trigger.dataset.panel)));
$$('.panel__close').forEach(button => button.addEventListener('click', closePanels));
document.addEventListener('keydown', event => { if (event.key === 'Escape') closePanels(); });

const menuButton = $('.menu-button');
menuButton.addEventListener('click', () => {
  const isOpen = $('.nav').classList.toggle('is-open');
  menuButton.setAttribute('aria-expanded', String(isOpen));
});
$$('.nav a, .nav button').forEach(link => link.addEventListener('click', () => { $('.nav').classList.remove('is-open'); menuButton.setAttribute('aria-expanded', 'false'); }));
