/**
 * Smart inference scenarios for Linguistic: Communication.
 * Loaded before play.js — merged via getSmartQuestionsForCategory().
 */
window.COMMUNICATION_SMART = {
  intro: {
    en: "Pick the replies that sound most like you. We'll infer tone, formality, verbosity, and the rest — no need to rate yourself on abstract scales.",
    zh: "选择最像你平时说法的回复即可，我们会推断语气、正式度、详略等属性，不必对着抽象量表自评。"
  },
  questions: [
    {
      id: "deadline_nudge",
      text: {
        en: "A teammate missed a deadline and you're unblocking others. Your first message is closest to:",
        zh: "同事错过了 deadline，其他人被卡住。你的第一条消息更像："
      },
      options: [
        {
          value: "blunt",
          label: { en: "Direct and short", zh: "直接简短" },
          example: {
            en: "\"We're blocked on your PR. Need it today — what's realistic?\"",
            zh: "「我们被你的 PR 卡住了。今天能给出吗？现实时间点是什么？」"
          },
          maps: {
            tone_expected: "Blunt",
            cog_directness: "Blunt",
            cog_verbosity: "Terse",
            cog_formality: "Casual",
            cog_politeness: "Brusque"
          }
        },
        {
          value: "warm",
          label: { en: "Warm but clear", zh: "温和但清楚" },
          example: {
            en: "\"Hey — totally get you're swamped. Could we aim for EOD? Happy to help cut scope.\"",
            zh: "「嗨，知道你手头很满。今晚前有机会吗？需要的话我可以帮你砍范围。」"
          },
          maps: {
            tone_expected: "Warm / empathetic",
            cog_directness: "Indirect",
            cog_verbosity: "Concise",
            cog_formality: "Casual",
            cog_empathy_expression: "High",
            cog_politeness: "Polite"
          }
        },
        {
          value: "formal",
          label: { en: "Formal and structured", zh: "正式且有结构" },
          example: {
            en: "\"Following up on the delivery date for ticket #482. Please confirm revised ETA by 3pm.\"",
            zh: "「跟进工单 #482 的交付日期。请在下午 3 点前确认修订后的 ETA。」"
          },
          maps: {
            tone_expected: "Formal",
            cog_directness: "Direct",
            cog_verbosity: "Concise",
            cog_formality: "Formal",
            cog_politeness: "Polite"
          }
        },
        {
          value: "playful",
          label: { en: "Light / playful", zh: "轻松/带点玩笑" },
          example: {
            en: "\"Friendly ping 👋 — any chance that patch lands today? No rush if you're buried in prod fires.\"",
            zh: "「友好 ping 👋 — 今天有机会合那个 patch 吗？如果在救火不急。」"
          },
          maps: {
            tone_expected: "Playful",
            cog_humor: "Playful",
            cog_directness: "Balanced",
            cog_emoji_use: "Moderate",
            cog_formality: "Casual"
          }
        }
      ]
    },
    {
      id: "explain_technical",
      text: {
        en: "Explaining a technical idea to a smart non-expert, you usually:",
        zh: "向聪明但非专业的同事解释技术概念时，你通常："
      },
      options: [
        {
          value: "analogy",
          label: { en: "Analogy-first, minimal jargon", zh: "先打比方，少术语" },
          example: {
            en: "\"Think of the cache like a desk drawer — you keep frequent items close so you don't walk to the warehouse each time.\"",
            zh: "「把缓存想成抽屉——常用东西放近处，不用每次都去仓库拿。」"
          },
          maps: {
            cog_abstraction: "Abstract",
            cog_use_of_jargon: "Avoids jargon",
            cog_detail_orientation: "Moderate",
            cog_precision_of_language: "Average",
            cog_storytelling: "High"
          }
        },
        {
          value: "precise",
          label: { en: "Precise definitions", zh: "精确定义" },
          example: {
            en: "\"Latency is time-to-first-byte; throughput is requests handled per second under load.\"",
            zh: "「Latency 是首字节时间；throughput 是负载下每秒处理的请求数。」"
          },
          maps: {
            cog_abstraction: "Concrete",
            cog_use_of_jargon: "Moderate",
            cog_detail_orientation: "High",
            cog_precision_of_language: "Precise",
            cog_verbosity: "Concise"
          }
        },
        {
          value: "deep",
          label: { en: "Deep dive with details", zh: "深入细节" },
          example: {
            en: "\"There are three layers — ingestion, normalization, and serving — each with retries, idempotency keys, and backpressure...\"",
            zh: "「分三层——摄入、规范化、服务——每层都有重试、幂等键和背压……」"
          },
          maps: {
            cog_abstraction: "Highly abstract",
            cog_detail_orientation: "Very high",
            cog_verbosity: "Wordy",
            cog_precision_of_language: "Very precise",
            tone_expected: "Detailed"
          }
        },
        {
          value: "visual",
          label: { en: "Sketch / diagram first", zh: "先画示意图" },
          example: {
            en: "\"Let me draw the boxes — data flows left to right, failures retry here...\"",
            zh: "「我先画几个框——数据从左到右流，失败在这里重试……」"
          },
          maps: {
            cog_visual_vs_verbal: "Strongly visual",
            cog_abstraction: "Balanced",
            cog_detail_orientation: "Moderate",
            cog_storytelling: "Moderate"
          }
        }
      ]
    },
    {
      id: "disagreement",
      text: {
        en: "In a meeting, you disagree with the proposed approach. You tend to:",
        zh: "会议上你不同意 proposed 方案时，通常会："
      },
      options: [
        {
          value: "confront",
          label: { en: "State disagreement plainly", zh: "直说不同意" },
          example: {
            en: "\"I don't think this will work — the migration path is too risky. Here's why...\"",
            zh: "「我觉得这行不通——迁移路径风险太高。原因是……」"
          },
          maps: {
            cog_conflict_approach: "Confronting",
            cog_assertiveness: "High",
            cog_directness: "Direct",
            cog_skepticism: "High"
          }
        },
        {
          value: "collaborate",
          label: { en: "Propose an alternative together", zh: "一起提出替代方案" },
          example: {
            en: "\"I see the goal — what if we pilot on one service first and compare error budgets?\"",
            zh: "「我理解目标——要不要先在一个服务上试点，对比 error budget？」"
          },
          maps: {
            cog_conflict_approach: "Collaborative",
            cog_assertiveness: "Moderate",
            cog_open_mindedness: "High",
            cog_politeness: "Polite"
          }
        },
        {
          value: "avoid",
          label: { en: "Stay quiet, follow up 1:1", zh: "会上不说，私下跟进" },
          example: {
            en: "(Say little in the room; later DM: \"Can we revisit the rollout plan? I have concerns.\")",
            zh: "（会上少说话；之后私聊：「能再讨论下发布计划吗？我有些顾虑。」）"
          },
          maps: {
            cog_conflict_approach: "Avoidant",
            cog_assertiveness: "Low",
            cog_directness: "Indirect",
            cog_patience: "High"
          }
        },
        {
          value: "accommodate",
          label: { en: "Defer to the group", zh: "先随大流" },
          example: {
            en: "\"Okay — if the team wants to ship this way, I'll support and help debug fallout.\"",
            zh: "「好——如果团队想这样上，我会配合并帮忙善后。」"
          },
          maps: {
            cog_conflict_approach: "Accommodating",
            cog_assertiveness: "Low",
            cog_politeness: "Very polite",
            cog_empathy_expression: "High"
          }
        }
      ]
    },
    {
      id: "async_message",
      text: {
        en: "Your typical Slack / chat message to a cross-functional partner looks like:",
        zh: "你发给跨职能同事的 Slack/聊天消息通常像："
      },
      options: [
        {
          value: "emoji_casual",
          label: { en: "Casual + emoji", zh: "口语 + 表情" },
          example: {
            en: "\"Hey! 👋 Quick q — do you have 5 min to sanity-check this spec? No worries if later 🙏\"",
            zh: "「嗨！👋 问个小事——能帮我看下这个 spec 吗？晚点也行 🙏」"
          },
          maps: {
            cog_emoji_use: "Heavy",
            cog_formality: "Casual",
            tone_expected: "Playful",
            cog_humor: "Playful"
          }
        },
        {
          value: "neutral_brief",
          label: { en: "Neutral and brief", zh: "中性简洁" },
          example: {
            en: "\"Can you review the spec linked below? Need feedback by Thursday. Thanks.\"",
            zh: "「能看下下面链接的 spec 吗？周四前需要反馈。谢谢。」"
          },
          maps: {
            cog_emoji_use: "Never",
            cog_formality: "Neutral",
            tone_expected: "Concise",
            cog_verbosity: "Concise"
          }
        },
        {
          value: "formal_context",
          label: { en: "Formal with context", zh: "正式带背景" },
          example: {
            en: "\"Context: Q3 launch dependency. Request: review attached spec sections 2–4 for compliance gaps.\"",
            zh: "「背景：Q3 上线依赖。请求：审阅附件 spec 第 2–4 节是否有合规缺口。」"
          },
          maps: {
            cog_formality: "Very formal",
            tone_expected: "Formal",
            cog_verbosity: "Balanced",
            cog_detail_orientation: "High"
          }
        },
        {
          value: "dry_sarcasm",
          label: { en: "Dry / sarcastic edge", zh: "冷幽默/略带讽刺" },
          example: {
            en: "\"Another 'quick fix' that touches 14 services — mind giving it a glance before we bless prod?\"",
            zh: "「又一个动 14 个服务的『小修复』——上线前帮瞄一眼？」"
          },
          maps: {
            cog_humor: "Sarcastic",
            cog_formality: "Casual",
            cog_skepticism: "Moderate",
            tone_expected: "Blunt"
          }
        }
      ]
    },
    {
      id: "feedback_style",
      text: {
        en: "Reviewing someone's draft doc, your comment style is closest to:",
        zh: "审阅别人的文档草稿时，你的评论风格更像："
      },
      options: [
        {
          value: "direct_bullets",
          label: { en: "Bullet fixes", zh: "条目式直接改" },
          example: {
            en: "• Sec 2 unclear — define SLA\n• Chart axis wrong\n• Cut appendix B",
            zh: "• 第 2 节不清楚——请定义 SLA\n• 图表坐标轴有误\n• 删掉附录 B"
          },
          maps: {
            cog_directness: "Blunt",
            cog_verbosity: "Terse",
            cog_precision_of_language: "Precise",
            cog_assertiveness: "High"
          }
        },
        {
          value: "sandwich",
          label: { en: "Praise + suggestions", zh: "先肯定再建议" },
          example: {
            en: "\"Strong framing in the intro. Two tweaks: clarify SLA in §2 and fix the chart axis.\"",
            zh: "「开头 framing 很好。两处小改：§2 写清 SLA，修正图表坐标轴。」"
          },
          maps: {
            cog_directness: "Balanced",
            cog_empathy_expression: "High",
            cog_politeness: "Very polite",
            tone_expected: "Warm / empathetic"
          }
        },
        {
          value: "questions",
          label: { en: "Questions over edits", zh: "用提问代替直接改" },
          example: {
            en: "\"What audience is §2 written for? Should SLA mean p99 or p50 here?\"",
            zh: "「§2 的目标读者是谁？这里的 SLA 是指 p99 还是 p50？」"
          },
          maps: {
            cog_question_asking: "Asks often",
            cog_directness: "Indirect",
            cog_curiosity: "High",
            cog_open_mindedness: "High"
          }
        },
        {
          value: "minimal",
          label: { en: "Only blockers", zh: "只提阻塞问题" },
          example: {
            en: "\"LGTM except compliance blocker in §4 — must fix before ship.\"",
            zh: "「除 §4 合规阻塞外 LGTM——上线前必须修。」"
          },
          maps: {
            cog_verbosity: "Terse",
            cog_detail_orientation: "Low",
            cog_perfectionism: "Moderate",
            cog_decision_speed: "Quick"
          }
        }
      ]
    },
    {
      id: "learn_format",
      text: {
        en: "When learning something new for work, you prefer:",
        zh: "为工作学习新东西时，你更偏好："
      },
      options: [
        {
          value: "read_docs",
          label: { en: "Read docs / long articles", zh: "读文档/长文" },
          example: {
            en: "Skim official docs, then a deep-dive blog post with code samples.",
            zh: "先扫官方文档，再读一篇带代码示例的深度文章。"
          },
          maps: {
            cog_reading_vs_watching: "Strongly prefers reading",
            cog_learning_pace: "Deliberate",
            cog_attention_span: "Long",
            cog_patience: "High"
          }
        },
        {
          value: "watch_demo",
          label: { en: "Watch demos / videos", zh: "看演示/视频" },
          example: {
            en: "Watch a 10-minute walkthrough, pause to replicate steps locally.",
            zh: "看 10 分钟 walkthrough，暂停后在本地复现步骤。"
          },
          maps: {
            cog_reading_vs_watching: "Prefers video",
            cog_learning_pace: "Fast",
            cog_multitasking: "Some",
            cog_curiosity: "High"
          }
        },
        {
          value: "pair_ask",
          label: { en: "Pair / ask live", zh: "结对/当场提问" },
          example: {
            en: "Book 30 minutes with someone who've done it; ask 'why' until the model clicks.",
            zh: "约 30 分钟找做过的人；不断问「为什么」直到理解模型。"
          },
          maps: {
            cog_question_asking: "Asks constantly",
            cog_learning_pace: "Fast",
            cog_empathy_expression: "Moderate",
            cog_open_mindedness: "Very high"
          }
        },
        {
          value: "experiment",
          label: { en: "Experiment first", zh: "先动手试" },
          example: {
            en: "Spin a sandbox, break things, read errors, then search for answers.",
            zh: "搭 sandbox，先折腾、看报错，再搜索答案。"
          },
          maps: {
            cog_risk_framing: "Opportunity-focused",
            cog_decision_speed: "Snap decisions",
            cog_skepticism: "Moderate",
            cog_procrastination: "Low"
          }
        }
      ]
    }
  ]
};

window.SKIP_GROUP_HINTS = {
  ...(window.SKIP_GROUP_HINTS || {}),
  "Linguistic: Communication": {
    en: "Not sure about communication style? Skip to use neutral defaults, or answer a few scenario questions above.",
    zh: "不确定沟通风格？可跳过使用中性默认值，或先回答上方几个情境题。"
  }
};
