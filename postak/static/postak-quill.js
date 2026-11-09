/* eslint-disable no-unused-vars */
function postakQuillCreate(editorEl, placeholder) {
  return new Quill(editorEl, {
    theme: 'snow',
    modules: {
      toolbar: [
        ['bold', 'italic', 'underline'],
        [{ list: 'ordered' }, { list: 'bullet' }],
        [{ align: [] }],
        ['link'],
        ['clean'],
      ],
    },
    placeholder: placeholder || 'Napište text…',
  });
}

function postakQuillLoadInitial(quill, nodeId) {
  var initialNode = document.getElementById(nodeId);
  if (!initialNode || !initialNode.textContent) {
    return;
  }
  try {
    var initial = JSON.parse(initialNode.textContent) || '';
    if (initial) {
      quill.clipboard.dangerouslyPasteHTML(0, initial);
    }
  } catch (e) {
    /* ignore */
  }
}
