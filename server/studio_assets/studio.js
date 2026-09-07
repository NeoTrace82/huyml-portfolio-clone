const forms = [...document.querySelectorAll('.project-form')];

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
  const previewTitle = card.querySelector('.editor-preview strong');
  const fileInput = form.querySelector('input[type="file"]');
  const button = form.querySelector('button[type="submit"]');
  const status = form.querySelector('.save-status');
  let objectUrl = null;

  fileInput.addEventListener('change', () => {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    const file = fileInput.files[0];
    if (!file) return;
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
      previewTitle.textContent = project.title;
      form.querySelector('[name="image_url"]').value = project.image.startsWith('/media/') ? '' : project.image;
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
