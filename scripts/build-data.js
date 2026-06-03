/**
 * build-data.js — 健壮的 data.js 构建脚本
 *
 * 功能：
 *   1. 校验 JSON 合法性
 *   2. 检测字符串内的 ASCII 双引号（常见 Bug：中文引号被误存为 " 导致 JSON 断裂）
 *   3. 自动修复：将字符串值内的 ASCII " 替换为中文引号「」
 *   4. 生成 data.js
 *
 * 用法：
 *   node scripts/build-data.js
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..');
const INDICATORS_PATH = path.join(ROOT, 'data', 'indicators.json');
const TIMELINE_PATH = path.join(ROOT, 'data', 'timeline.json');
const DATA_JS_PATH = path.join(ROOT, 'data', 'data.js');

let errors = 0;
let warnings = 0;
let fixes = 0;

// ── Step 1: 读取并校验 JSON ──────────────────────────────

function loadAndValidate(filePath, label) {
  const raw = fs.readFileSync(filePath, 'utf8');

  // 尝试解析 JSON
  let data;
  try {
    data = JSON.parse(raw);
    console.log(`  ✓ ${label} — JSON 解析通过`);
  } catch (e) {
    console.error(`  ✗ ${label} — JSON 解析失败:`, e.message);
    errors++;
    return null;
  }
  return { data, raw };
}

// ── Step 2: 检测字符串值中的 ASCII 双引号 ──────────────────

function scanForAsciiQuotes(value, path) {
  if (typeof value === 'string') {
    // 统计 ASCII 双引号数量（引号在 JSON key/value 中是分隔符，不应出现在值内部）
    const asciiQuotes = (value.match(/\u0022/g) || []).length;
    if (asciiQuotes > 0) {
      console.warn(`  ⚠ 警告: "${path}" 中包含 ${asciiQuotes} 个 ASCII 双引号 (U+0022)`);
      warnings++;
      return true;
    }
  } else if (Array.isArray(value)) {
    value.forEach((item, i) => scanForAsciiQuotes(item, `${path}[${i}]`));
  } else if (value && typeof value === 'object') {
    Object.entries(value).forEach(([k, v]) => scanForAsciiQuotes(v, `${path}.${k}`));
  }
  return false;
}

// ── Step 3: 自动修复 — 字符串值内 ASCII " → 「」 ─────────

function fixAsciiQuotesInStrings(data) {
  let fixed = 0;
  const jsonStr = JSON.stringify(data, null, 2);

  // 策略：JSON stringify 后，值中的字面 " 会被转义为 \"，
  // 但对于本来就是内容中的 "，stringify 也会转义。
  // 更可靠的做法：递归遍历原始对象，在写入前替换。

  function traverse(obj) {
    if (typeof obj === 'string') {
      const before = obj;
      // 交替替换为中文书名号风格的引号：第一个 " → 「，第二个 " → 」
      let count = 0;
      const after = obj.replace(/\u0022/g, () => {
        count++;
        return count % 2 === 1 ? '\u300C' : '\u300D'; // 「 and 」
      });
      if (count > 0) {
        fixed++;
        return after;
      }
      return obj;
    }
    if (Array.isArray(obj)) {
      return obj.map(traverse);
    }
    if (obj && typeof obj === 'object') {
      const result = {};
      for (const [k, v] of Object.entries(obj)) {
        result[k] = traverse(v);
      }
      return result;
    }
    return obj;
  }

  return { data: traverse(JSON.parse(JSON.stringify(data))), fixed };
}

// ── Main ─────────────────────────────────────────────────

console.log('\n🔧 build-data.js — 开始构建\n');

// 1. 校验
console.log('── Step 1: JSON 校验 ──');
const indicators = loadAndValidate(INDICATORS_PATH, 'indicators.json');
const timeline = loadAndValidate(TIMELINE_PATH, 'timeline.json');

if (!indicators || !timeline) {
  console.error('\n❌ JSON 校验未通过，中止构建。请先修复数据文件。\n');
  process.exit(1);
}

// 2. 检测
console.log('\n── Step 2: ASCII 引号检测 ──');
scanForAsciiQuotes(indicators.data, 'indicators');
scanForAsciiQuotes(timeline.data, 'timeline');

// 3. 自动修复
if (warnings > 0) {
  console.log('\n── Step 3: 自动修复 ──');

  const fixI = fixAsciiQuotesInStrings(indicators.data);
  const fixT = fixAsciiQuotesInStrings(timeline.data);

  if (fixI.fixed > 0) {
    fs.writeFileSync(INDICATORS_PATH, JSON.stringify(fixI.data, null, 2), 'utf8');
    console.log(`  ✓ indicators.json: 修复 ${fixI.fixed} 处`);
  }
  if (fixT.fixed > 0) {
    fs.writeFileSync(TIMELINE_PATH, JSON.stringify(fixT.data, null, 2), 'utf8');
    console.log(`  ✓ timeline.json: 修复 ${fixT.fixed} 处`);
  }
  fixes = fixI.fixed + fixT.fixed;
} else {
  console.log('  ✓ 未检测到 ASCII 引号问题');
}

// 4. 重新读取（可能已被修复）
const finalIndicators = fs.readFileSync(INDICATORS_PATH, 'utf8').trim();
const finalTimeline = fs.readFileSync(TIMELINE_PATH, 'utf8').trim();

// 5. 生成 data.js
console.log('\n── Step 4: 生成 data.js ──');
const output = [
  'var __INDICATORS__ = ' + finalIndicators + ';',
  '',
  'var __TIMELINE__ = ' + finalTimeline + ';',
  '',
].join('\n');

fs.writeFileSync(DATA_JS_PATH, output, 'utf8');

// 6. 最终验证 — 用 Node.js 执行 data.js 确认无语法错误
console.log('\n── Step 5: 语法验证 ──');
const vm = require('vm');
const ctx = {};
vm.createContext(ctx);
try {
  vm.runInContext(output, ctx);
  console.log('  ✓ data.js 语法正确');
  console.log(`    - 指数: ${ctx.__INDICATORS__.dashboard.indices.length} 个`);
  console.log(`    - 宏观指标: ${ctx.__INDICATORS__.dashboard.macroCards.length} 个`);
  console.log(`    - 时间线日期: ${ctx.__TIMELINE__.timeline.length} 组`);
} catch (e) {
  console.error('  ✗ data.js 语法错误:', e.message);
  errors++;
  process.exit(1);
}

// 7. 汇总
console.log('\n═══════════════════════════════════');
if (errors === 0) {
  console.log('✅ 构建成功！');
  if (fixes > 0) console.log(`  自动修复了 ${fixes} 处 ASCII 引号问题`);
  if (warnings > fixes) console.log(`  ⚠ 有 ${warnings - fixes} 处警告需人工检查`);
} else {
  console.log(`❌ 构建失败，${errors} 个错误`);
  process.exit(1);
}
console.log('═══════════════════════════════════\n');
