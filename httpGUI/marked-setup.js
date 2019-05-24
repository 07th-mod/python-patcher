'use strict';

const renderer = new marked.Renderer();
renderer.link = function newLinkBehavior(href, title, text) {
  const link = marked.Renderer.prototype.link.apply(this, arguments);
  return link.replace("<a", "<a target='_blank'");
};

marked.setOptions({
  renderer: renderer
});
