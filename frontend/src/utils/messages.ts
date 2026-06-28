import { cleanDisplayMarkdown } from './markdown';
import { compact, escapeRegExp } from './text';

export interface ParsedUserMessage {
  title: string;
  tags: string[];
  requirement: string;
  materials: string;
}

// 这组字段需要和 App.vue 里的 buildUserMessage 保持一致，聊天区才能把用户输入还原成结构化任务卡片。
const MESSAGE_FIELD_LABELS = ['功能', '标题', '类型', '字数', '深度打磨', '要求', '内容/资料', '原文', '知识库'];
const LEGACY_DEFAULT_WORD_COUNT = '1000 字';

export function parsedUserMessage(content: string): ParsedUserMessage | null {
  // 新消息按“字段：内容”解析；旧历史可能只保存了四行纯文本，需要兜底还原成同样的任务卡片。
  const parsed = parseMessageFields(content);
  if (!parsed['标题'] && !parsed['功能'] && !parsed['要求']) {
    return parseLegacyUserMessage(content);
  }
  const tags = [
    parsed['功能'],
    parsed['类型'],
    parsed['字数'] ? `${parsed['字数']} 字` : '',
    parsed['深度打磨'] === '开启' ? '深度打磨' : '',
    parsed['知识库'],
  ].filter(Boolean);
  return {
    title: parsed['标题'] || '新的写作任务',
    tags,
    requirement: parsed['要求'] || '',
    materials: parsed['内容/资料'] || parsed['原文'] || '',
  };
}

function parseLegacyUserMessage(content: string): ParsedUserMessage | null {
  const lines = (content || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length < 2) return null;
  const title = lines[0] || '新的写作任务';
  const assignmentType = lines[1] || '';
  const requirement = lines[2] || '';
  const materials = lines.slice(3).join('\n');
  // 早期版本只把“标题/类型/要求/材料”四行写入 SQLite，没有保存功能和字数。
  // 这里补齐展示标签，让刷新后的历史消息和新消息保持同一种任务卡片观感。
  const tags = ['生成文章', assignmentType, LEGACY_DEFAULT_WORD_COUNT].filter(Boolean);
  return {
    title,
    tags,
    requirement,
    materials,
  };
}

export function parseMessageFields(content: string) {
  const nextLabelPattern = new RegExp(`\\n(?=${MESSAGE_FIELD_LABELS.map(escapeRegExp).join('|')}：)`, 'g');
  return (content || '')
    .split(nextLabelPattern)
    .reduce<Record<string, string>>((acc, block) => {
      const match = /^([^：\n]+)：([\s\S]*)$/.exec(block.trim());
      if (match) acc[match[1]] = match[2].trim();
      return acc;
    }, {});
}

export function isArticleContent(content: string) {
  // 只把真正的正文放进文章列表，错误提示、节点过程和短回复继续按普通消息展示。
  const clean = cleanDisplayMarkdown(content || '');
  if (!clean || clean.length < 40) return false;
  if (/^(执行失败|工作流执行失败|请求失败|该轮没有生成)/.test(clean)) return false;
  return /^#\s+.+$/m.test(clean) || /(?:一、|二、|三、|引言|结语|润色目标)/.test(clean);
}

export function extractArticleTitle(markdown: string) {
  const clean = (markdown || '').trim();
  const heading = /^#\s+(.+)$/m.exec(clean);
  if (heading?.[1]) {
    return heading[1].replace(/\[\^\d+\]/g, '').trim();
  }
  const firstTextLine = clean
    .split(/\r?\n/)
    .map((line) => line.trim())
    .find((line) => line && !line.startsWith('[^') && !line.startsWith('<!--'));
  return firstTextLine ? compact(firstTextLine.replace(/^#+\s*/, ''), 36) : '';
}
