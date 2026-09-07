const forms = [...document.querySelectorAll('.project-form')];
const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

function detailFromResponse(response, fallback) {
  return response.json().then((body) => body.detail || fallback).catch(() => fallback);
}

function extensionForType(type) {
  return {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
    'image/heic': 'heic',
    'image/heif': 'heif',
  }[type] || 'jpg';
}

async function formDataWithMaterializedPicture(form, fileInput) {
  const data = new FormData(form);
  const file = fileInput.files[0];
  if (!file) return data;
  if (typeof file.arrayBuffer !== 'function') throw new Error('This browser cannot prepare the selected picture. Try dragging the image into the picker.');
  const bytes = await file.arrayBuffer();
  if (!bytes.byteLength) throw new Error('The selected picture is empty. Export it to Finder or try dragging it into the picker.');
  const filename = file.name || `portfolio-photo.${extensionForType(file.type)}`;
  const materialized = new File([bytes], filename, {
    type: file.type,
    lastModified: file.lastModified || Date.now(),
  });
  data.delete(fileInput.name);
  data.append(fileInput.name, materialized);
  return data;
}

forms.forEach((form) => {
  const card = form.closest('.editor-card');
  const preview = card.querySelector('.editor-preview img');
  const previewTitle = card.querySelector('.editor-preview h2');
  const titleInput = form.querySelector('[name="title"]');
  const fileInput = form.querySelector('input[type="file"]');
  const button = form.querySelector('button[type="submit"]');
  const status = form.querySelector('.save-status');
  let objectUrl = null;
  let savedImage = preview.getAttribute('src');

  titleInput.addEventListener('input', () => {
    const title = titleInput.value.trim() || 'Untitled';
    previewTitle.textContent = title;
    button.setAttribute('aria-label', `Save ${title} project`);
  });

  fileInput.addEventListener('change', () => {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null;
    const file = fileInput.files[0];
    if (!file) {
      preview.src = savedImage;
      return;
    }
    if (file.size > MAX_UPLOAD_BYTES) {
      fileInput.value = '';
      preview.src = savedImage;
      status.textContent = 'Pictures must be 50 MB or smaller.';
      status.classList.add('is-error');
      return;
    }
    status.textContent = 'Preview uses the top-centered square crop.';
    status.classList.remove('is-error');
    objectUrl = URL.createObjectURL(file);
    preview.src = objectUrl;
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    button.disabled = true;
    status.classList.remove('is-error');
    status.textContent = fileInput.files[0] ? 'Preparing picture…' : 'Saving…';
    try {
      const data = await formDataWithMaterializedPicture(form, fileInput);
      status.textContent = 'Saving…';
      const response = await fetch(form.action, {
        method: 'POST',
        body: data,
        credentials: 'same-origin',
      });
      if (!response.ok) throw new Error(await detailFromResponse(response, `Save failed (${response.status})`));
      const project = await response.json();
      preview.src = project.image;
      savedImage = project.image;
      previewTitle.textContent = project.title;
      button.setAttribute('aria-label', `Save ${project.title} project`);
      status.textContent = 'Saved — public site updated';
      fileInput.value = '';
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
        objectUrl = null;
      }
    } catch (error) {
      status.textContent = error.message;
      status.classList.add('is-error');
    } finally {
      button.disabled = false;
    }
  });
});
