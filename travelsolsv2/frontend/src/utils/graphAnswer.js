const cleanText = (value) => String(value).replace(/\s+/g, ' ').trim();
const fieldLabel = (key) => key.replace(/([a-z])([A-Z])/g, '$1 $2').replaceAll('_', ' ').toLowerCase();
const sentence = (value) => `${cleanText(value).replace(/[.]+$/, '')}.`;
const excerpt = (value) => {
  const text = cleanText(value);
  return text.length > 1200 ? `${text.slice(0, 1200)}… (excerpt shortened)` : text;
};

export function graphRecords(value) {
  if (typeof value === 'string') {
    try {
      return graphRecords(JSON.parse(value));
    } catch {
      return [];
    }
  }
  if (Array.isArray(value)) return value;
  if (value && typeof value === 'object') return Array.isArray(value.results) ? value.results : [value];
  return [];
}

function readableValue(value, depth = 0) {
  if (value === null || value === undefined) return 'not recorded';
  if (typeof value === 'boolean') return value ? 'yes' : 'no';
  if (typeof value === 'number') return value.toLocaleString('en-US');
  if (typeof value !== 'object') return excerpt(value);
  if (depth >= 3) return 'additional properties available in technical details';
  if (Array.isArray(value)) return value.slice(0, 12).map((item) => readableValue(item, depth + 1)).join(', ') || 'none recorded';
  return Object.entries(value).filter(([key]) => !key.startsWith('_'))
    .map(([key, item]) => `${fieldLabel(key)} is ${readableValue(item, depth + 1)}`).join('; ') || 'no readable properties';
}

function describeProperties(properties) {
  const sentences = [];
  const identifier = properties.id || properties.code;
  if (properties.name) sentences.push(sentence(`${properties.name}${identifier ? ` (${identifier})` : ''} is recorded in the graph`));
  else if (identifier) sentences.push(sentence(`The record identifier is ${identifier}`));
  for (const [key, value] of Object.entries(properties)) {
    if (key.startsWith('_') || ['name', 'id', 'code'].includes(key) || value === null || value === undefined || value === '') continue;
    const actual = readableValue(value);
    if (key === 'allowed_cabins') sentences.push(sentence(`Travel is permitted in ${actual.replaceAll('_', ' ').toLowerCase().replace(/\b\w/g, (letter) => letter.toUpperCase())}`));
    else if (key === 'allowed_fare_classes') sentences.push(sentence(`Permitted fare codes are ${actual}`));
    else if (key === 'preferred_airlines') sentences.push(sentence(`Preferred airline codes are ${actual}`));
    else if (['max_fare_inr', 'max_fare'].includes(key)) sentences.push(sentence(`The maximum fare is INR ${actual}`));
    else if (['price_inr', 'total_fare_inr'].includes(key)) sentences.push(sentence(`The recorded fare is INR ${actual}`));
    else if (key === 'requires_approval_above_inr') sentences.push(sentence(`Approval is required for fares above INR ${actual}`));
    else if (key === 'min_advance_days') sentences.push(sentence(`Bookings must be made at least ${actual} days before departure`));
    else if (key === 'requires_approval' && typeof value === 'boolean') sentences.push(value ? 'This record requires approval.' : 'This record does not require approval.');
    else if (key === 'snippet') sentences.push(sentence(excerpt(value)));
    else sentences.push(sentence(`The recorded ${fieldLabel(key)} is ${actual}`));
  }
  return sentences.join(' ');
}

function describeRecord(record) {
  if (!record || typeof record !== 'object') return record === null ? '' : sentence(`The returned value is ${readableValue(record)}`);
  if ('PolicySnippet' in record || 'SectionTitle' in record) {
    const title = record.SectionTitle ? `${cleanText(record.SectionTitle)}: ` : '';
    const page = record.PageNumber && record.PageNumber !== '0' ? ` (page ${readableValue(record.PageNumber)})` : '';
    return sentence(`${title}${record.PolicySnippet ? excerpt(record.PolicySnippet) : 'No excerpt was recorded for this section'}${page}`);
  }
  const nested = [];
  const flat = {};
  for (const [key, value] of Object.entries(record)) {
    if (key.startsWith('_') || value === null || value === undefined) continue;
    if (typeof value === 'object' && !Array.isArray(value)) nested.push(describeProperties(value));
    else flat[key] = value;
  }
  return [...nested, describeProperties(flat)].filter(Boolean).join(' ');
}

export function recordsToParagraphs(results) {
  const records = graphRecords(results);
  if (!records.length) return 'No matching records were returned by the graph.';
  const paragraphs = [...new Set(records.slice(0, 15).map(describeRecord).filter(Boolean))];
  if (!paragraphs.length) return 'The returned records contain no readable properties to explain.';
  if (records.length > 15) paragraphs.push(`This explanation covers the first 15 of ${records.length} records. The rest are available in technical details.`);
  return paragraphs.join('\n\n');
}

export function graphAnswerParagraphs(answer, results) {
  const text = typeof answer === 'string' ? answer.trim() : '';
  const countOnly = /^(?:found \d+ (?:records|rows)(?: matching your query)?|(?:the )?query returned \d+ (?:records|rows)|successfully executed cypher query\.\s*found \d+ rows)[.!]?$/i.test(text);
  const rawData = /^[{[]/.test(text) || text.includes('```') || /\{\s*"[^"\n]+"\s*:/.test(text);
  if (!text || countOnly || rawData) return recordsToParagraphs(results);
  return text;
}
