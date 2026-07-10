/**
 * Clean HTML content from Greenhouse job descriptions
 * Preserves readable formatting while removing raw HTML tags
 */

export function cleanHtmlContent(html) {
  if (!html) return '';

  let content = html;

  // Decode common HTML entities
  const entities = {
    '&amp;': '&',
    '&lt;': '<',
    '&gt;': '>',
    '&quot;': '"',
    '&#39;': "'",
    '&#x27;': "'",
    '&nbsp;': ' ',
    '&ndash;': '-',
    '&mdash;': '-',
    '&rsquo;': "'",
    '&lsquo;': "'",
    '&rdquo;': '"',
    '&ldquo;': '"',
  };

  for (const [entity, char] of Object.entries(entities)) {
    content = content.replace(new RegExp(entity, 'g'), char);
  }

  // Convert block elements to preserve structure
  content = content.replace(/<\/p>/gi, '\n\n');
  content = content.replace(/<br\s*\/?>/gi, '\n');
  content = content.replace(/<\/div>/gi, '\n');
  content = content.replace(/<\/li>/gi, '\n');

  // Preserve list markers
  content = content.replace(/<li[^>]*>/gi, '• ');

  // Add spacing for headings
  content = content.replace(/<\/h[1-6]>/gi, '\n\n');
  content = content.replace(/<h[1-6][^>]*>/gi, '\n');

  // Remove all remaining HTML tags
  content = content.replace(/<[^>]+>/g, '');

  // Clean up excessive whitespace
  content = content.replace(/\n{3,}/g, '\n\n');
  content = content.replace(/[ \t]+/g, ' ');
  content = content.trim();

  // Decode numeric entities
  content = content.replace(/&#(\d+);/g, (match, num) => String.fromCharCode(num));
  content = content.replace(/&#x([0-9a-f]+);/gi, (match, num) => String.fromCharCode(parseInt(num, 16)));

  return content;
}

export function getPreviewText(content, maxLength = 200) {
  if (!content) return '';

  const cleaned = cleanHtmlContent(content);
  if (cleaned.length <= maxLength) return cleaned;

  // Find a good break point
  let breakPoint = maxLength;
  const lastSpace = cleaned.lastIndexOf(' ', maxLength);
  const lastSentence = cleaned.lastIndexOf('.', maxLength);

  if (lastSentence > maxLength * 0.7) {
    breakPoint = lastSentence + 1;
  } else if (lastSpace > maxLength * 0.7) {
    breakPoint = lastSpace;
  }

  return cleaned.substring(0, breakPoint).trim() + '...';
}
