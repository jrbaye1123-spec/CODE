/**
 * Smart inference scenarios for Developer: Agent Adoption.
 * Loaded before play.js — merged via getSmartQuestionsForCategory().
 */
window.AGENT_ADOPTION_SMART = {
  intro: {
    en: "Answer a few work scenarios about coding agents (Cursor, Copilot Agent, etc.). We'll infer usage, autonomy, trust, and integration preferences — no jargon sliders.",
    zh: "回答几个关于编程 Agent（如 Cursor、Copilot Agent 等）的真实工作情境，我们会推断使用频率、自主程度、信任与集成偏好，不必对着术语量表自评。"
  },
  questions: [
    {
      id: "usage_level",
      text: {
        en: "In the last month, how do coding agents fit into your real dev work?",
        zh: "过去一个月里，编程 Agent 在你实际开发中的位置更像："
      },
      options: [
        {
          value: "daily",
          label: { en: "Daily driver", zh: "每天在用" },
          example: {
            en: "Agent is open most days — refactors, tests, boilerplate, exploration.",
            zh: "几乎每天开着 Agent——重构、测试、样板代码、探索方案。"
          },
          maps: {
            coding_agent_usage_frequency: "Daily",
            coding_agent_workflow_impact: "Major productivity increase",
            coding_agent_adoption_barrier: "No barrier"
          }
        },
        {
          value: "weekly",
          label: { en: "Weekly helper", zh: "每周几次" },
          example: {
            en: "Reach for an agent a few times a week for scoped tasks.",
            zh: "每周用几次，处理有边界的小任务。"
          },
          maps: {
            coding_agent_usage_frequency: "Weekly",
            coding_agent_workflow_impact: "Moderate productivity increase",
            coding_agent_adoption_barrier: "No barrier"
          }
        },
        {
          value: "experimental",
          label: { en: "Experimenting", zh: "偶尔试验" },
          example: {
            en: "Tried agents on side tasks; not part of the main workflow yet.",
            zh: "在边角任务上试过，还没进主流程。"
          },
          maps: {
            coding_agent_usage_frequency: "Experimental only",
            coding_agent_workflow_impact: "Small targeted improvement",
            coding_agent_adoption_barrier: "Lack of clear use case"
          }
        },
        {
          value: "interested",
          label: { en: "Curious, not using yet", zh: "感兴趣但还没用" },
          example: {
            en: "Read demos and threads; waiting for the right moment or policy.",
            zh: "看过演示和讨论，在等合适场景或公司政策。"
          },
          maps: {
            coding_agent_usage_frequency: "Not yet but interested",
            coding_agent_workflow_impact: "No clear change",
            coding_agent_failure_tolerance: "Does not use agents"
          }
        },
        {
          value: "no_plans",
          label: { en: "Not planning to use", zh: "暂无使用计划" },
          example: {
            en: "Prefer manual coding or other tools; agents aren't on the roadmap.",
            zh: "更倾向手写或用其他工具，Agent 不在计划里。"
          },
          maps: {
            coding_agent_usage_frequency: "No plans",
            coding_agent_workflow_impact: "No clear change",
            coding_agent_failure_tolerance: "Does not use agents",
            coding_agent_autonomy_preference: "No agent autonomy"
          }
        }
      ]
    },
    {
      id: "task_delegation",
      text: {
        en: "You need a multi-file change. You tell the agent to:",
        zh: "要做跨多个文件的改动时，你会让 Agent："
      },
      options: [
        {
          value: "autonomous",
          label: { en: "Run end-to-end", zh: "端到端自主完成" },
          example: {
            en: "\"Implement the feature, update tests, and run the suite — ping me when green.\"",
            zh: "「实现功能、更新测试、跑完测试套件——绿了再叫我。」"
          },
          maps: {
            coding_agent_autonomy_preference: "Autonomous execution",
            coding_agent_control_expectation: "Agent may run broad tasks autonomously"
          }
        },
        {
          value: "plan_first",
          label: { en: "Plan, then execute with checkpoints", zh: "先规划，检查点后再执行" },
          example: {
            en: "\"Draft a plan and wait for my OK before editing each module.\"",
            zh: "「先写计划，每个模块改之前等我确认。」"
          },
          maps: {
            coding_agent_autonomy_preference: "Plan-then-act with checkpoints",
            coding_agent_control_expectation: "Approval before risky edits only"
          }
        },
        {
          value: "pair",
          label: { en: "Pair step-by-step", zh: "逐步结对" },
          example: {
            en: "\"Let's go file by file — suggest a patch, I'll apply or tweak.\"",
            zh: "「一个文件一个文件来——给 patch，我来应用或微调。」"
          },
          maps: {
            coding_agent_autonomy_preference: "Step-by-step pair programming",
            coding_agent_control_expectation: "Agent may edit within scoped files"
          }
        },
        {
          value: "suggest_only",
          label: { en: "Suggest only — I edit", zh: "只给建议，我自己改" },
          example: {
            en: "\"Show me what you'd change, but don't touch the repo.\"",
            zh: "「告诉我你会怎么改，但不要动仓库。」"
          },
          maps: {
            coding_agent_autonomy_preference: "Suggest-only assistant",
            coding_agent_control_expectation: "Requires explicit approval before edits"
          }
        },
        {
          value: "read_only",
          label: { en: "Read-only / explain", zh: "只读/解释，不改动" },
          example: {
            en: "\"Explain this module and point to risks — no edits.\"",
            zh: "「解释这个模块、指出风险——不要改代码。」"
          },
          maps: {
            coding_agent_autonomy_preference: "No agent autonomy",
            coding_agent_control_expectation: "Read-only assistance preferred"
          }
        }
      ]
    },
    {
      id: "context_sharing",
      text: {
        en: "What context are you comfortable giving a coding agent on a typical work task?",
        zh: "日常工作任务中，你愿意给编程 Agent 多少上下文？"
      },
      options: [
        {
          value: "full_repo",
          label: { en: "Full repo / workspace", zh: "完整仓库/工作区" },
          example: {
            en: "Index the whole project; agent can browse freely (within policy).",
            zh: "索引整个项目；Agent 可在政策允许范围内自由浏览。"
          },
          maps: {
            coding_agent_context_sharing_comfort: "Comfortable sharing full repo",
            coding_agent_security_expectation: "Security review only for sensitive areas"
          }
        },
        {
          value: "selected_files",
          label: { en: "Selected files only", zh: "仅选定文件" },
          example: {
            en: "Attach 3–5 relevant files; keep the rest out of scope.",
            zh: "附上 3–5 个相关文件，其余不在范围内。"
          },
          maps: {
            coding_agent_context_sharing_comfort: "Shares selected files only",
            coding_agent_security_expectation: "Expects basic secret / privacy checks"
          }
        },
        {
          value: "snippets",
          label: { en: "Redacted snippets", zh: "脱敏代码片段" },
          example: {
            en: "Paste sanitized snippets with secrets and customer data stripped.",
            zh: "粘贴去掉密钥和客户数据的脱敏片段。"
          },
          maps: {
            coding_agent_context_sharing_comfort: "Shares sanitized snippets",
            coding_agent_security_expectation: "Requires strict security review"
          }
        },
        {
          value: "description",
          label: { en: "Natural-language description only", zh: "仅自然语言描述" },
          example: {
            en: "Describe the bug and stack in prose — no source attached.",
            zh: "用文字描述 bug 和堆栈——不上传源码。"
          },
          maps: {
            coding_agent_context_sharing_comfort: "Shares natural-language descriptions only",
            coding_agent_security_expectation: "Relies on human review"
          }
        },
        {
          value: "avoid_proprietary",
          label: { en: "Avoid proprietary code entirely", zh: "完全不上专有代码" },
          example: {
            en: "Use agents only on OSS, toy repos, or public docs.",
            zh: "只在开源、玩具项目或公开文档上用 Agent。"
          },
          maps: {
            coding_agent_context_sharing_comfort: "Avoids sharing proprietary code",
            coding_agent_security_expectation: "Requires strict security review",
            coding_agent_adoption_barrier: "Security / privacy / compliance"
          }
        }
      ]
    },
    {
      id: "explanation_style",
      text: {
        en: "While the agent works, the explanation style you want is closest to:",
        zh: "Agent 工作时，你希望的解释方式更像："
      },
      options: [
        {
          value: "concise",
          label: { en: "Short summary at the end", zh: "最后简短总结" },
          example: {
            en: "\"Done — changed 4 files, added 2 tests. Ready for review.\"",
            zh: "「完成——改了 4 个文件，加了 2 个测试。可以 review。」"
          },
          maps: {
            coding_agent_explanation_preference: "Concise summary only",
            coding_agent_memory_preference: "Prefers stateless interactions"
          }
        },
        {
          value: "tradeoffs",
          label: { en: "Decisions and tradeoffs", zh: "说明决策与权衡" },
          example: {
            en: "\"Chose approach B — simpler rollback, slightly slower path.\"",
            zh: "「选了方案 B——回滚更简单，路径稍慢。」"
          },
          maps: {
            coding_agent_explanation_preference: "Explain decisions and tradeoffs",
            coding_agent_memory_preference: "Wants task-scoped memory"
          }
        },
        {
          value: "detailed",
          label: { en: "Step-by-step reasoning", zh: "逐步推理过程" },
          example: {
            en: "\"Step 1: traced auth flow… Step 2: added guard… Step 3: …\"",
            zh: "「步骤 1：追踪 auth 流程… 步骤 2：加 guard… 步骤 3：…」"
          },
          maps: {
            coding_agent_explanation_preference: "Detailed step-by-step reasoning",
            coding_agent_memory_preference: "Wants persistent project memory"
          }
        },
        {
          value: "diffs_first",
          label: { en: "Show diffs / tests first", zh: "先看 diff/测试" },
          example: {
            en: "Minimal prose — highlight the diff and failing test output up front.",
            zh: "少废话——先把 diff 和失败测试输出亮出来。"
          },
          maps: {
            coding_agent_explanation_preference: "Show diffs / tests first",
            coding_agent_memory_preference: "Wants explicit opt-in memory"
          }
        },
        {
          value: "minimal",
          label: { en: "Quiet unless I ask", zh: "除非我问，否则少说" },
          example: {
            en: "Work silently; I'll ask if something looks off.",
            zh: "安静干活；有问题我再问。"
          },
          maps: {
            coding_agent_explanation_preference: "Minimal explanation unless asked",
            coding_agent_memory_preference: "Prefers stateless interactions"
          }
        }
      ]
    },
    {
      id: "wrong_output",
      text: {
        en: "The agent's patch breaks tests or needs heavy rework. You usually:",
        zh: "Agent 的 patch 搞挂测试或需要大改时，你通常："
      },
      options: [
        {
          value: "zero_tolerance",
          label: { en: "Stop using it for that task", zh: "这类任务不再用" },
          example: {
            en: "Rollback immediately; finish manually or with tighter scope.",
            zh: "立刻回滚；改用手写或更小范围。"
          },
          maps: {
            coding_agent_failure_tolerance: "Very low tolerance"
          }
        },
        {
          value: "rollback_ok",
          label: { en: "Rollback and retry once", zh: "回滚再试一次" },
          example: {
            en: "Easy git revert; try again with clearer instructions.",
            zh: "git 回滚很方便；指令写清楚再试一次。"
          },
          maps: {
            coding_agent_failure_tolerance: "Low tolerance with easy rollback"
          }
        },
        {
          value: "prototype_ok",
          label: { en: "OK for prototypes / spikes", zh: "原型/spike 可以接受" },
          example: {
            en: "Messy first pass is fine if it saves thinking time on throwaway code.",
            zh: "一次性代码乱一点也行，能省思考时间。"
          },
          maps: {
            coding_agent_failure_tolerance: "Moderate tolerance for prototypes"
          }
        },
        {
          value: "experiment_ok",
          label: { en: "High tolerance — iterate freely", zh: "高容忍，随意迭代" },
          example: {
            en: "Expect several rounds; treat agent output as clay to reshape.",
            zh: "预期多轮修改；把 Agent 输出当可塑的草稿。"
          },
          maps: {
            coding_agent_failure_tolerance: "High tolerance for experimental work"
          }
        },
        {
          value: "dont_use",
          label: { en: "I don't use agents for this", zh: "这类事不用 Agent" },
          example: {
            en: "Never delegate changes that could break CI — manual only.",
            zh: "可能搞挂 CI 的改动从不委托——只用手写。"
          },
          maps: {
            coding_agent_failure_tolerance: "Does not use agents"
          }
        }
      ]
    },
    {
      id: "agent_surface",
      text: {
        en: "Where do you most want a coding agent to live?",
        zh: "你最希望编程 Agent 出现在哪里？"
      },
      options: [
        {
          value: "ide",
          label: { en: "Inside the IDE", zh: "IDE 里" },
          example: {
            en: "Cursor / VS Code panel — inline edits while coding.",
            zh: "Cursor / VS Code 面板——编码时 inline 修改。"
          },
          maps: {
            coding_agent_tool_integration_preference: "IDE-integrated"
          }
        },
        {
          value: "github",
          label: { en: "GitHub / PR flow", zh: "GitHub / PR 流程" },
          example: {
            en: "Bot opens PRs, replies on review threads, fixes CI.",
            zh: "Bot 开 PR、回复 review、修 CI。"
          },
          maps: {
            coding_agent_tool_integration_preference: "GitHub / PR integrated"
          }
        },
        {
          value: "cli",
          label: { en: "Terminal / CLI", zh: "终端 / CLI" },
          example: {
            en: "`agent run fix-tests` from the shell in any repo.",
            zh: "在任意仓库 shell 里 `agent run fix-tests`。"
          },
          maps: {
            coding_agent_tool_integration_preference: "CLI / terminal integrated"
          }
        },
        {
          value: "chat",
          label: { en: "Chat / browser", zh: "聊天 / 浏览器" },
          example: {
            en: "Separate chat tab; copy patches in and out.",
            zh: "独立聊天页；patch 复制粘贴进出。"
          },
          maps: {
            coding_agent_tool_integration_preference: "Chat / browser integrated"
          }
        },
        {
          value: "cicd",
          label: { en: "CI/CD pipeline", zh: "CI/CD 流水线" },
          example: {
            en: "Agent step in pipeline for migrations, docs, or test fixes.",
            zh: "流水线里的 Agent 步骤——迁移、文档或修测试。"
          },
          maps: {
            coding_agent_tool_integration_preference: "CI/CD integrated"
          }
        },
        {
          value: "no_pref",
          label: { en: "No strong preference", zh: "无强烈偏好" },
          example: {
            en: "Whatever integrates with team workflow.",
            zh: "跟团队工作流集成好就行。"
          },
          maps: {
            coding_agent_tool_integration_preference: "No strong preference"
          }
        }
      ]
    },
    {
      id: "main_blocker",
      text: {
        en: "If you haven't gone all-in on coding agents, the main blocker is:",
        zh: "如果你还没全面用上编程 Agent，最大阻碍是："
      },
      options: [
        {
          value: "accuracy",
          label: { en: "Accuracy / reliability", zh: "准确度/可靠性" },
          example: {
            en: "Too many subtle bugs or wrong assumptions in generated changes.",
            zh: "生成改动里 subtle bug 或错误假设太多。"
          },
          maps: {
            coding_agent_adoption_barrier: "Accuracy / reliability concerns"
          }
        },
        {
          value: "security",
          label: { en: "Security / privacy / compliance", zh: "安全/隐私/合规" },
          example: {
            en: "Can't send repo context to third-party models.",
            zh: "不能把仓库上下文发给第三方模型。"
          },
          maps: {
            coding_agent_adoption_barrier: "Security / privacy / compliance"
          }
        },
        {
          value: "integration",
          label: { en: "Tool integration", zh: "工具集成" },
          example: {
            en: "Doesn't fit IDE, CI, or ticket workflow yet.",
            zh: "还没融入 IDE、CI 或工单流程。"
          },
          maps: {
            coding_agent_adoption_barrier: "Integration with existing tools"
          }
        },
        {
          value: "setup",
          label: { en: "Learning / setup cost", zh: "学习/配置成本" },
          example: {
            en: "Prompting, rules, and context setup feel like overhead.",
            zh: "写 prompt、规则、配上下文感觉开销太大。"
          },
          maps: {
            coding_agent_adoption_barrier: "Learning / setup effort"
          }
        },
        {
          value: "cost",
          label: { en: "Cost", zh: "成本" },
          example: {
            en: "Seats or token spend hard to justify vs. manual time.",
            zh: "席位或 token 费用相对手写时间难以 justify。"
          },
          maps: {
            coding_agent_adoption_barrier: "Cost"
          }
        },
        {
          value: "policy",
          label: { en: "Company policy", zh: "公司政策" },
          example: {
            en: "Approved tools list or legal review blocks agents.",
            zh: "工具白名单或法务审查不允许用 Agent。"
          },
          maps: {
            coding_agent_adoption_barrier: "Company policy"
          }
        },
        {
          value: "no_blocker",
          label: { en: "Nothing major — already adopting", zh: "没有大阻碍——已在推进" },
          example: {
            en: "Blockers are minor; main limit is time to expand use cases.",
            zh: "阻碍不大；主要是没时间扩展使用场景。"
          },
          maps: {
            coding_agent_adoption_barrier: "No barrier"
          }
        }
      ]
    }
  ]
};

window.SKIP_GROUP_HINTS = {
  ...(window.SKIP_GROUP_HINTS || {}),
  "Developer: Agent Adoption": {
    en: "Haven't used coding agents? Skip for neutral defaults, or answer a few scenarios above.",
    zh: "没用过编程 Agent？可跳过使用默认值，或先回答上方几个情境题。"
  }
};
