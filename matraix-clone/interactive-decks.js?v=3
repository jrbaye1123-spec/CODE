/**
 * Interactive example decks — pick concrete examples, infer canonical dimension values.
 * All user-facing copy supports { en, zh }. Code snippets may also use code: { en, zh }.
 */
window.INTERACTIVE_DECKS = {
  "Skills: Programming": {
    intro: {
      en: "Pick the code snippets that feel closest to your style. We'll infer the underlying attributes — no need to know the jargon.",
      zh: "选择最像你写法的代码示例即可，我们会自动推断对应属性，不必懂那些术语。"
    },
    questions: [
      {
        id: "comment_style",
        dimId: "code_comment_style",
        text: {
          en: "Which commenting style feels most like you?",
          zh: "哪种注释风格最像你？"
        },
        options: [
          {
            value: "extensive",
            label: { en: "Heavily commented", zh: "注释很多" },
            mapsTo: "Extensive inline comments",
            code: {
              en: `function monthlyPayment(principal, annualRate, months) {
  // Convert annual percentage rate to monthly decimal
  const rate = annualRate / 100 / 12;
  // Standard amortization formula
  const factor = Math.pow(1 + rate, months);
  return (principal * rate * factor) / (factor - 1);
}`,
              zh: `function monthlyPayment(principal, annualRate, months) {
  // 将年化利率转换为月利率（小数）
  const rate = annualRate / 100 / 12;
  // 标准等额本息公式
  const factor = Math.pow(1 + rate, months);
  return (principal * rate * factor) / (factor - 1);
}`
            }
          },
          {
            value: "sparse",
            label: { en: "Minimal comments", zh: "注释很少" },
            mapsTo: "Sparse inline comments",
            code: {
              en: `function monthlyPayment(principal, annualRate, months) {
  const rate = annualRate / 100 / 12;
  const factor = Math.pow(1 + rate, months);
  return (principal * rate * factor) / (factor - 1);
}`,
              zh: `function monthlyPayment(principal, annualRate, months) {
  const rate = annualRate / 100 / 12;
  const factor = Math.pow(1 + rate, months);
  return (principal * rate * factor) / (factor - 1);
}`
            }
          },
          {
            value: "docstring",
            label: { en: "Doc block at top", zh: "文件/函数顶部文档块" },
            mapsTo: "Docstring/documentation blocks only",
            code: {
              en: `/**
 * Compute fixed-rate monthly loan payment.
 * @param {number} principal - loan amount
 * @param {number} annualRate - APR percent
 * @param {number} months - term length
 */
function monthlyPayment(principal, annualRate, months) {
  const rate = annualRate / 100 / 12;
  const factor = Math.pow(1 + rate, months);
  return (principal * rate * factor) / (factor - 1);
}`,
              zh: `/**
 * 计算固定利率的月供。
 * @param {number} principal - 贷款本金
 * @param {number} annualRate - 年化利率（%）
 * @param {number} months - 期数（月）
 */
function monthlyPayment(principal, annualRate, months) {
  const rate = annualRate / 100 / 12;
  const factor = Math.pow(1 + rate, months);
  return (principal * rate * factor) / (factor - 1);
}`
            }
          },
          {
            value: "none",
            label: { en: "No comments", zh: "几乎不写注释" },
            mapsTo: "No comments",
            code: {
              en: `const monthlyPayment = (p, r, n) => {
  const m = r / 100 / 12;
  const f = (1 + m) ** n;
  return (p * m * f) / (f - 1);
};`,
              zh: `const monthlyPayment = (p, r, n) => {
  const m = r / 100 / 12;
  const f = (1 + m) ** n;
  return (p * m * f) / (f - 1);
};`
            }
          }
        ]
      },
      {
        id: "tldr_docs",
        dimId: "code_summary_documentation",
        text: {
          en: "How do you usually open a non-trivial source file?",
          zh: "打开一个稍复杂的源文件时，你通常怎么开头？"
        },
        options: [
          {
            value: "file_tldr",
            label: { en: "File-level summary at top", zh: "文件顶部有 TLDR/摘要" },
            mapsTo: "Always includes file-level TLDR",
            code: {
              en: `// TLDR: Parses CSV uploads, validates rows, writes to staging table.
// Entry: ingestCsv(path) -> { ok, rows, errors }
// Gotchas: empty headers, UTF-8 BOM, duplicate keys on retry.

import fs from "node:fs";
import { parse } from "csv-parse/sync";`,
              zh: `// 摘要：解析 CSV 上传、校验行、写入 staging 表。
// 入口：ingestCsv(path) -> { ok, rows, errors }
// 注意：空表头、UTF-8 BOM、重试时重复 key。

import fs from "node:fs";
import { parse } from "csv-parse/sync";`
            }
          },
          {
            value: "fn_tldr",
            label: { en: "Summary per function", zh: "每个函数前有简短说明" },
            mapsTo: "Always includes function-level TLDR",
            code: {
              en: `import fs from "node:fs";

/** Quick summary: stream-parse CSV and collect row errors without loading all rows. */
function ingestCsv(path) {
  // ...
}`,
              zh: `import fs from "node:fs";

/** 简要说明：流式解析 CSV，收集行级错误，避免一次性加载全部行。 */
function ingestCsv(path) {
  // ...
}`
            }
          },
          {
            value: "complex_only",
            label: { en: "Only when logic is tricky", zh: "只有复杂逻辑才写摘要" },
            mapsTo: "Includes TLDR for complex functions only",
            code: {
              en: `function ingestCsv(path) {
  const text = fs.readFileSync(path, "utf8");
  return parse(text, { columns: true });
}

/** Handles dedupe + merge when the same upload id is retried after partial failure. */
function reconcileRetry(batchId, rows) {
  // ...
}`,
              zh: `function ingestCsv(path) {
  const text = fs.readFileSync(path, "utf8");
  return parse(text, { columns: true });
}

/** 处理同一 upload id 部分失败后重试时的去重与合并。 */
function reconcileRetry(batchId, rows) {
  // ...
}`
            }
          },
          {
            value: "never",
            label: { en: "Jump straight into code", zh: "直接写代码，不加摘要" },
            mapsTo: "Never includes TLDR",
            code: {
              en: `import fs from "node:fs";
import { parse } from "csv-parse/sync";

function ingestCsv(path) {
  const text = fs.readFileSync(path, "utf8");
  return parse(text, { columns: true });
}`,
              zh: `import fs from "node:fs";
import { parse } from "csv-parse/sync";

function ingestCsv(path) {
  const text = fs.readFileSync(path, "utf8");
  return parse(text, { columns: true });
}`
            }
          }
        ]
      },
      {
        id: "naming",
        dimId: "code_naming_verbosity",
        text: {
          en: "Which naming feels most natural to you?",
          zh: "哪种命名方式你最顺手？"
        },
        options: [
          {
            value: "verbose",
            label: { en: "Long descriptive names", zh: "长而描述性的名字" },
            mapsTo: "Highly verbose (long descriptive names)",
            code: {
              en: `const calculateMonthlyPaymentAmount = (loanPrincipal, annualInterestRatePercent) => {
  const monthlyInterestRateDecimal = annualInterestRatePercent / 100 / 12;
  return loanPrincipal * monthlyInterestRateDecimal;
};`,
              zh: `const calculateMonthlyPaymentAmount = (loanPrincipal, annualInterestRatePercent) => {
  const monthlyInterestRateDecimal = annualInterestRatePercent / 100 / 12;
  return loanPrincipal * monthlyInterestRateDecimal;
};`
            }
          },
          {
            value: "moderate",
            label: { en: "Balanced names", zh: "适中长度" },
            mapsTo: "Moderately verbose",
            code: {
              en: `const monthlyPayment = (principal, annualRate) => {
  const monthlyRate = annualRate / 100 / 12;
  return principal * monthlyRate;
};`,
              zh: `const monthlyPayment = (principal, annualRate) => {
  const monthlyRate = annualRate / 100 / 12;
  return principal * monthlyRate;
};`
            }
          },
          {
            value: "terse",
            label: { en: "Short abbreviations", zh: "短名/缩写" },
            mapsTo: "Terse abbreviated names",
            code: {
              en: `const calcPmt = (p, r) => {
  const m = r / 100 / 12;
  return p * m;
};`,
              zh: `const calcPmt = (p, r) => {
  const m = r / 100 / 12;
  return p * m;
};`
            }
          },
          {
            value: "single",
            label: { en: "Single-letter locals in tight loops", zh: "循环里常用单字母" },
            mapsTo: "Single-letter names",
            code: {
              en: `const f = (p, r, n) => {
  let t = 0;
  for (let i = 0; i < n; i++) t += p * (r / 1200);
  return t;
};`,
              zh: `const f = (p, r, n) => {
  let t = 0;
  for (let i = 0; i < n; i++) t += p * (r / 1200);
  return t;
};`
            }
          }
        ]
      },
      {
        id: "indentation",
        dimId: "code_indentation_style",
        text: {
          en: "Which formatting matches your editor defaults?",
          zh: "哪种缩进/格式更像你的默认设置？"
        },
        options: [
          {
            value: "tabs",
            label: { en: "Tabs", zh: "Tab 缩进" },
            mapsTo: "Tabs (flexible width)",
            code: {
              en: `function ingest(path) {
\tconst raw = fs.readFileSync(path, "utf8");
\treturn raw.split("\\n").map(line => line.trim());
}`,
              zh: `function ingest(path) {
\tconst raw = fs.readFileSync(path, "utf8");
\treturn raw.split("\\n").map(line => line.trim());
}`
            }
          },
          {
            value: "two",
            label: { en: "2 spaces", zh: "2 空格" },
            mapsTo: "2 spaces",
            code: {
              en: `function ingest(path) {
  const raw = fs.readFileSync(path, "utf8");
  return raw.split("\\n").map(line => line.trim());
}`,
              zh: `function ingest(path) {
  const raw = fs.readFileSync(path, "utf8");
  return raw.split("\\n").map(line => line.trim());
}`
            }
          },
          {
            value: "four",
            label: { en: "4 spaces", zh: "4 空格" },
            mapsTo: "4 spaces",
            code: {
              en: `function ingest(path) {
    const raw = fs.readFileSync(path, "utf8");
    return raw.split("\\n").map(line => line.trim());
}`,
              zh: `function ingest(path) {
    const raw = fs.readFileSync(path, "utf8");
    return raw.split("\\n").map(line => line.trim());
}`
            }
          },
          {
            value: "mixed",
            label: { en: "Mixed / inconsistent", zh: "混用 / 不太统一" },
            mapsTo: "Inconsistent/mixed",
            code: {
              en: `function ingest(path) {
  const raw = fs.readFileSync(path, "utf8");
    return raw.split("\\n")
  .map(line => line.trim());
}`,
              zh: `function ingest(path) {
  const raw = fs.readFileSync(path, "utf8");
    return raw.split("\\n")
  .map(line => line.trim());
}`
            }
          }
        ]
      }
    ]
  }
};

/** Per-category skip hints — shown above the skip button in each group tab. */
window.SKIP_GROUP_HINTS = {
  "Skills: Programming": {
    en: "Don't write code? Skip this category — we'll use neutral defaults.",
    zh: "不会编程？可跳过本类别，我们会填入中性默认值。"
  },
  "Skills: Tools": {
    en: "Unfamiliar with these tools? Skip and use defaults.",
    zh: "不熟悉这些工具？可跳过并使用默认值。"
  },
  "Developer: Professional Context": {
    en: "Not a developer? Skip this entire section.",
    zh: "不是开发者？可跳过整个类别。"
  },
  "Developer: AI Adoption": {
    en: "Skip if you don't use AI coding tools.",
    zh: "不使用 AI 编程工具？可跳过。"
  },
  "Developer: Agent Adoption": {
    en: "Skip if you haven't used coding agents.",
    zh: "没用过编程 Agent？可跳过。"
  },
  "Developer: AI Workflow Tasks": {
    en: "Skip if these workflows don't apply to you.",
    zh: "这些工作流不适用？可跳过。"
  },
  "Developer: Technology Evaluation": {
    en: "Skip if you don't evaluate dev tools.",
    zh: "不评估开发工具？可跳过。"
  },
  "Developer: Community Behavior": {
    en: "Skip if you're not active in dev communities.",
    zh: "不参与开发者社区？可跳过。"
  },
  "Developer: Open Source Behavior": {
    en: "Skip if open source doesn't apply.",
    zh: "与开源无关？可跳过。"
  },
  "Developer: Code Maintenance": {
    en: "Skip if you don't maintain codebases.",
    zh: "不维护代码库？可跳过。"
  },
  _default: {
    en: "Not familiar with this topic? Skip this category and use defaults.",
    zh: "不熟悉这个主题？可跳过本类别并使用默认值。"
  }
};
