import { compact, escapeHtml } from './text';

export interface CitationItem {
  id: number;
  source: string;
  content: string;
  score?: number | null;
}

export function markdownToHtml(markdown: string) {
  // 这里保持轻量 Markdown 渲染，避免为了预览和脚注交互额外引入编辑器级依赖。
  const parsed = parseCitationMarkdown(markdown);
  const lines = parsed.markdown.split(/\r?\n/);
  const citations = parsed.citations;
  const html: string[] = [];
  let inList = false;
  let inCode = false;
  let codeLines: string[] = [];
  let inCitationSection = false;

  const closeList = () => {
    if (inList) {
      html.push('</ul>');
      inList = false;
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.replace(/\s+$/, '');
    if (line.trim().startsWith('```')) {
      if (inCode) {
        html.push(`<pre><code>${codeLines.join('\n')}</code></pre>`);
        codeLines = [];
        inCode = false;
      } else {
        closeList();
        inCode = true;
      }
      continue;
    }

    if (inCode) {
      codeLines.push(escapeHtml(line));
      continue;
    }

    if (!line.trim()) {
      closeList();
      continue;
    }

    if (/^[-*_]{3,}$/.test(line.trim())) {
      closeList();
      html.push('<hr />');
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      closeList();
      const level = heading[1].length;
      const headingText = heading[2].trim();
      inCitationSection = /引用|知识库|参考材料|参考资料/.test(headingText);
      html.push(`<h${level}>${renderInlineMarkdown(headingText, citations)}</h${level}>`);
      continue;
    }

    const bullet = /^\s*(?:[-*]|\d+\.)\s+(.+)$/.exec(line);
    if (bullet) {
      if (!inList) {
        html.push('<ul>');
        inList = true;
      }
      html.push(`<li>${renderInlineMarkdown(bullet[1], citations)}</li>`);
      continue;
    }

    const quote = /^>\s?(.+)$/.exec(line);
    if (quote) {
      closeList();
      const quoteText = quote[1].trim();
      const className = inCitationSection || /^(来源|引用|材料|知识库|片段)[:：]/.test(quoteText)
        ? ' class="citation-block"'
        : '';
      html.push(`<blockquote${className}>${renderInlineMarkdown(quoteText, citations)}</blockquote>`);
      continue;
    }

    closeList();
    html.push(`<p${inCitationSection ? ' class="citation-paragraph"' : ''}>${renderInlineMarkdown(line, citations)}</p>`);
  }

  closeList();
  if (inCode) {
    html.push(`<pre><code>${codeLines.join('\n')}</code></pre>`);
  }
  return html.join('\n') || '<p class="empty-preview">暂无 Markdown 内容。</p>';
}

export function parseCitationMarkdown(markdown: string): { markdown: string; citations: CitationItem[] } {
  // 后端可能返回隐藏 JSON 元数据，也可能返回标准 Markdown 脚注，这里统一成前端可渲染的数据结构。
  const citations: CitationItem[] = [];
  let clean = (markdown || '').replace(/<!--DEEPPEN_CITATIONS\s*([\s\S]*?)\s*DEEPPEN_CITATIONS-->/g, (_match, raw) => {
    try {
      const parsed = JSON.parse(raw.trim());
      if (Array.isArray(parsed)) {
        parsed.forEach((item, index) => {
          citations.push({
            id: Number(item.id) || index + 1,
            source: String(item.source || item.document_name || '知识库片段'),
            content: String(item.content || ''),
            score: typeof item.score === 'number' ? item.score : null,
          });
        });
      }
    } catch {
      // 隐藏引用元数据解析失败时，仅隐藏原始块，正文仍正常显示。
    }
    return '';
  });
  clean = clean.replace(
    /^\[\^(\d+)\]:\s*(.+?)(?:\n[ \t]{2,}([^\n]+))?\s*$/gm,
    (_match, rawId, rawMeta, rawContent = '') => {
      const id = Number(rawId);
      const meta = String(rawMeta || '').trim();
      const content = String(rawContent || '').trim();
      const scoreMatch = /(?:·\s*)?相关度\s*([0-9.]+)/.exec(meta);
      const source = meta
        .replace(/(?:·\s*)?相关度\s*[0-9.]+/g, '')
        .replace(/(?:·\s*)?切片\s*[^·]+/g, '')
        .trim() || '知识库片段';
      const existing = citations.find((item) => item.id === id);
      if (!existing) {
        citations.push({
          id,
          source,
          content,
          score: scoreMatch ? Number(scoreMatch[1]) : null,
        });
      }
      return '';
    },
  );
  clean = cleanDisplayMarkdown(clean);
  return renumberParsedCitations(clean, citations);
}

export function renumberParsedCitations(markdown: string, citations: CitationItem[]): { markdown: string; citations: CitationItem[] } {
  if (!citations.length) return { markdown, citations };
  // 展示层按正文首次出现顺序重排编号，避免用户看到知识库切片原始编号跳号。
  const byId = new Map(citations.map((item) => [item.id, item]));
  const ordered: CitationItem[] = [];
  const oldToNew = new Map<number, number>();
  const clean = markdown.replace(/\[\^(\d+)\]/g, (match, rawId) => {
    const oldId = Number(rawId);
    const citation = byId.get(oldId);
    if (!citation) return match;
    if (!oldToNew.has(oldId)) {
      const nextId = oldToNew.size + 1;
      oldToNew.set(oldId, nextId);
      ordered.push({ ...citation, id: nextId });
    }
    return `[^${oldToNew.get(oldId)}]`;
  });
  return { markdown: clean, citations: ordered };
}

export function cleanDisplayMarkdown(markdown: string) {
  // LLM 偶尔会把“修改提示/参考文献占位/待补充项”写进正文，预览前统一清掉，保证右侧只显示可提交文本。
  return markdown
    .replace(/\n*##\s*知识库引用[\s\S]*?(?=\n##\s*深度打磨记录|\n#\s|$)/g, '')
    .replace(/\n*#{1,6}\s*(?:📝\s*)?(?:定稿)?修改提示[\s\S]*$/gi, '')
    .replace(/\n*#{1,6}\s*(?:📚\s*)?参考文献[\s\S]*$/gi, '')
    .replace(/\n*#{1,6}\s*(?:修改说明|给同学的修改提示|待确认素材|素材补充建议)[\s\S]*$/gi, '')
    .replace(/[\[【（(]\s*(?:请|可|建议|此处|这里|待)\s*(?:填入|补充|替换|加入|搜索)[^\]】）)]*[\]】）)]/g, '')
    .replace(/\*?\s*此处可补充[^。；;\n]*(?:。)?/g, '')
    .replace(/参考输入摘要[:：][\s\S]*?(?=\n#{1,3}\s|\n质量自检|\n修改建议|$)/g, '')
    .replace(/你是课程作业[\s\S]*?(?=\n\n|$)/g, '')
    .replace(/请把下面写作任务拆解为[\s\S]*?(?=\n\n|$)/g, '')
    .replace(/请评估下面初稿[\s\S]*?(?=\n\n|$)/g, '')
    .replace(/这是本地演示模型生成的可编辑文本。\s*/g, '')
    .trim();
}

export function markdownToPlainText(markdown: string) {
  // 一键复制使用纯文本输出：去掉 Markdown 样式，但保留引用编号和引用来源，便于直接粘贴到文档里。
  const parsed = parseCitationMarkdown(markdown || '');
  const body = parsed.markdown
    .split(/\r?\n/)
    .map((line) => markdownLineToPlainText(line))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  const usedIds = Array.from(new Set(
    [...(parsed.markdown.matchAll(/\[\^(\d+)\]/g))].map((match) => Number(match[1])),
  ));
  const citations = parsed.citations.filter((item) => usedIds.length === 0 || usedIds.includes(item.id));
  if (!citations.length) return body;

  const citationText = citations
    .map((item) => {
      const scoreText = typeof item.score === 'number' ? `，相关度 ${item.score.toFixed(3)}` : '';
      const content = compact(item.content || '', 360);
      return `引用 ${item.id}：${item.source || '知识库片段'}${scoreText}\n${content}`;
    })
    .join('\n\n');
  return `${body}\n\n引用来源\n${citationText}`;
}

function markdownLineToPlainText(line: string) {
  const trimmed = line.trim();
  if (!trimmed) return '';
  return trimmed
    .replace(/^#{1,6}\s+/, '')
    .replace(/^>\s?/, '')
    .replace(/^[-*]\s+/, '')
    .replace(/^\d+\.\s+/, '')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')
    .replace(/\[\^(\d+)\]/g, '$1')
    .replace(/<[^>]+>/g, '')
    .trim();
}

function renderInlineMarkdown(text: string, citations: CitationItem[] = []) {
  return escapeHtml(text)
    .replace(/\[\^(\d+)\]/g, (_match, rawId) => renderCitationBadge(Number(rawId), citations))
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>');
}

function renderCitationBadge(id: number, citations: CitationItem[]) {
  const citation = citations.find((item) => item.id === id);
  if (!citation) {
    return `<span class="citation-ref missing" tabindex="0"><span class="citation-number">${id}</span></span>`;
  }
  // 引用内容放在 hover tooltip 里，正文只露出绿色编号，避免知识库片段打断文章阅读节奏。
  const scoreText = typeof citation.score === 'number' ? `相关度 ${citation.score.toFixed(3)}` : '知识库引用';
  const source = escapeHtml(citation.source || '知识库片段');
  const content = escapeHtml(compact(citation.content || '', 320));
  return [
    `<span class="citation-ref" tabindex="0" aria-label="引用 ${id}：${source}">`,
    `<span class="citation-number">${id}</span>`,
    '<span class="citation-tooltip">',
    `<strong>${source}</strong>`,
    `<small>${scoreText}</small>`,
    `<span>${content}</span>`,
    '</span>',
    '</span>',
  ].join('');
}
