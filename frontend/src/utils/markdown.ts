// 文件名：frontend/src/utils/markdown.ts
// 作者：zcl
// 日期：2026-01-27
// 描述：Markdown 渲染配置

import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css'; // 选择一个代码高亮主题

const md = new MarkdownIt({
  html: false, // 禁用 HTML 标签以防 XSS
  linkify: true, // 自动识别链接
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return '<pre class="hljs"><code>' +
               hljs.highlight(str, { language: lang, ignoreIllegals: true }).value +
               '</code></pre>';
      } catch (__) {}
    }

    return '<pre class="hljs"><code>' + md.utils.escapeHtml(str) + '</code></pre>';
  }
});

export function renderMarkdown(content: string) {
  return md.render(content || '');
}
