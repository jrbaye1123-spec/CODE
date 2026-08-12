/**
 * Smart inference scenarios for Values & Motivation (46 dimensions).
 * Each option maps directly to canonical dimension values.
 */
window.VALUES_MOTIVATION_SMART = {
  intro: {
    en: "Answer a few life-tradeoff scenarios (work, money, relationships, meaning). We'll infer all 46 value and motivation dimensions — not just two generic questions.",
    zh: "回答若干生活取舍情境（工作、金钱、关系、意义等），我们会推断全部 46 个价值观与动机维度，而不只是两道泛化题。"
  },
  questions: [
    {
      id: "weekend_priority",
      text: {
        en: "You unexpectedly get a free Saturday with zero obligations. You most likely:",
        zh: "你意外得到一个完全空闲的周六、没有任何安排。你最可能："
      },
      options: [
        {
          value: "family",
          label: { en: "Spend it with family or partner", zh: "与家人/伴侣度过" },
          example: { en: "\"That's rare — I'd protect it for people closest to me.\"", zh: "「这种日子很少——我会留给最亲近的人。」" },
          maps: {
            val_family: "Core value",
            val_community: "Important",
            val_fun_enjoyment: "Important",
            val_loyalty: "Important",
            sdt_need_relatedness: "Very high",
            schwartz_value_benevolence: "High",
            schwartz_value_hedonism: "Average",
            val_career_success: "Moderate",
            val_adventure: "Moderate"
          }
        },
        {
          value: "explore",
          label: { en: "Explore somewhere new or try an experience", zh: "去新地方或尝试新体验" },
          example: { en: "\"If I'm free, I want novelty — even a small adventure counts.\"", zh: "「有空就想找点新意——小冒险也算。」" },
          maps: {
            val_adventure: "Core value",
            val_fun_enjoyment: "Important",
            val_personal_freedom: "Important",
            values_priority: "Novelty",
            schwartz_value_stimulation: "Very high",
            schwartz_value_self_direction: "High",
            sdt_need_autonomy: "High",
            val_tradition: "Minor",
            val_security_stability: "Moderate"
          }
        },
        {
          value: "grow",
          label: { en: "Deep work on a personal project or learning", zh: "投入个人项目或深度学习" },
          example: { en: "\"Free time is for compounding skills — I'll disappear into a book or build.\"", zh: "「空闲时间用来积累能力——读书或做项目。」" },
          maps: {
            val_personal_growth: "Core value",
            val_knowledge_truth: "Important",
            val_achievement: "Important",
            val_creativity_self_expression: "Important",
            need_for_cognition: "Very high",
            schwartz_value_self_direction: "Very high",
            sdt_need_competence: "Very high",
            schwartz_value_achievement: "High",
            val_fun_enjoyment: "Moderate"
          }
        },
        {
          value: "rest",
          label: { en: "Rest, routines, and recharge at home", zh: "在家休息、按routine恢复精力" },
          example: { en: "\"I guard downtime — predictable rest keeps me functional.\"", zh: "「我会守住休息时间——稳定恢复才能持续。」" },
          maps: {
            val_health: "Core value",
            val_security_stability: "Important",
            val_order_structure: "Important",
            schwartz_value_security: "Very high",
            schwartz_value_conformity: "Average",
            val_adventure: "Minor",
            schwartz_value_stimulation: "Low",
            sdt_need_relatedness: "Average"
          }
        }
      ]
    },
    {
      id: "job_offer",
      text: {
        en: "Two offers: (A) higher title/pay but rigid culture, (B) lower pay but high trust and flexibility. You pick:",
        zh: "两个机会：(A) 职级/薪资更高但文化僵化，(B) 薪资较低但高度信任与灵活。你会选："
      },
      options: [
        {
          value: "prestige",
          label: { en: "A — prestige and compensation", zh: "A — 声望与薪酬" },
          example: { en: "\"I'll tolerate structure if the ladder and paycheck are real.\"", zh: "「只要晋升和收入到位，结构僵化也能忍。」" },
          maps: {
            val_career_success: "Core value",
            val_wealth: "Important",
            val_achievement: "Important",
            val_recognition: "Important",
            val_social_status: "Important",
            values_priority: "Achievement",
            economic_motivation: "Premium-seeking",
            schwartz_value_achievement: "Very high",
            schwartz_value_power: "High",
            val_personal_freedom: "Moderate",
            sdt_need_autonomy: "Low"
          }
        },
        {
          value: "freedom",
          label: { en: "B — autonomy and flexibility", zh: "B — 自主与灵活" },
          example: { en: "\"I optimize for control over my time and how I work.\"", zh: "「我更优化对时间和工作方式的掌控。」" },
          maps: {
            val_personal_freedom: "Core value",
            val_independence: "Important",
            values_priority: "Autonomy",
            sdt_need_autonomy: "Very high",
            schwartz_value_self_direction: "Very high",
            val_career_success: "Moderate",
            val_wealth: "Moderate",
            schwartz_value_conformity: "Low",
            val_order_structure: "Minor"
          }
        },
        {
          value: "mission",
          label: { en: "Whichever mission aligns — pay is secondary", zh: "哪个使命更契合选哪个——收入其次" },
          example: { en: "\"I'll join the team whose problem I believe in, even if it's messy.\"", zh: "「我会加入我相信其问题意义的团队，哪怕混乱。」" },
          maps: {
            val_helping_others: "Important",
            val_integrity_honesty: "Important",
            val_justice_fairness: "Important",
            values_priority: "Community",
            economic_motivation: "Value-driven",
            schwartz_value_universalism: "High",
            schwartz_value_benevolence: "High",
            val_wealth: "Minor",
            schwartz_value_power: "Low"
          }
        },
        {
          value: "safe",
          label: { en: "Whichever is more stable long-term", zh: "哪个长期更稳定选哪个" },
          example: { en: "\"I weigh benefits, runway, and downside — not just headline pay.\"", zh: "「我会看福利、缓冲和下行风险——不只看 headline 薪资。」" },
          maps: {
            val_security_stability: "Core value",
            values_priority: "Security",
            schwartz_value_security: "Very high",
            val_health: "Important",
            economic_motivation: "Cost-sensitive",
            val_adventure: "Minor",
            schwartz_value_stimulation: "Low",
            val_wealth: "Important"
          }
        }
      ]
    },
    {
      id: "discretionary_spend",
      text: {
        en: "You get an unexpected bonus. Your first instinct:",
        zh: "你收到一笔意外奖金。第一反应是："
      },
      options: [
        {
          value: "save",
          label: { en: "Save or invest most of it", zh: "大部分存起来或投资" },
          example: { en: "\"Windfalls go to runway — I sleep better with a buffer.\"", zh: "「意外之财先增加缓冲——有储备才睡得着。」" },
          maps: {
            val_wealth: "Important",
            val_security_stability: "Important",
            economic_motivation: "Cost-sensitive",
            schwartz_value_security: "High",
            val_fun_enjoyment: "Moderate",
            schwartz_value_hedonism: "Low"
          }
        },
        {
          value: "experience",
          label: { en: "Spend on experiences with people you care about", zh: "花在所在乎的人身上的体验" },
          example: { en: "\"Money is for memories and shared moments.\"", zh: "「钱是用来制造回忆和共同体验的。」" },
          maps: {
            val_fun_enjoyment: "Important",
            val_family: "Important",
            val_community: "Important",
            economic_motivation: "Value-driven",
            schwartz_value_hedonism: "High",
            schwartz_value_benevolence: "High",
            val_wealth: "Moderate"
          }
        },
        {
          value: "quality",
          label: { en: "Buy something high-quality you've wanted", zh: "买一件想要已久的高品质东西" },
          example: { en: "\"I'll pay for craftsmanship or performance that lasts.\"", zh: "「愿意为做工或性能付溢价。」" },
          maps: {
            val_beauty_aesthetics: "Important",
            economic_motivation: "Premium-seeking",
            val_wealth: "Moderate",
            val_fun_enjoyment: "Important",
            schwartz_value_hedonism: "Average"
          }
        },
        {
          value: "indifferent",
          label: { en: "Doesn't change much — money isn't a motivator", zh: "影响不大——钱不是主要驱动力" },
          example: { en: "\"Nice, but it won't reshape my week or identity.\"", zh: "「不错，但不会改变我的节奏或自我认同。」" },
          maps: {
            economic_motivation: "Indifferent",
            val_wealth: "Minor",
            val_social_status: "Minor",
            schwartz_value_power: "Low",
            schwartz_value_achievement: "Average"
          }
        }
      ]
    },
    {
      id: "community_ask",
      text: {
        en: "Your neighborhood group asks for weekly help on a local cause you partly care about. You:",
        zh: "社区小组请你每周参与一项你有些在意的本地事务。你会："
      },
      options: [
        {
          value: "lead",
          label: { en: "Step up to organize or lead", zh: "站出来组织或牵头" },
          example: { en: "\"If I commit, I want impact — I'll run the thing properly.\"", zh: "「既然参与就要有影响——我会认真把它做起来。」" },
          maps: {
            val_helping_others: "Core value",
            val_community: "Core value",
            val_achievement: "Important",
            val_power_influence: "Important",
            schwartz_value_benevolence: "Very high",
            sdt_need_relatedness: "High",
            sdt_need_competence: "High",
            val_recognition: "Moderate"
          }
        },
        {
          value: "help",
          label: { en: "Show up reliably but in a support role", zh: "稳定参与但做支持角色" },
          example: { en: "\"I'll be the dependable helper — not the face of it.\"", zh: "「我会是可靠帮手——不当出头的人。」" },
          maps: {
            val_helping_others: "Important",
            val_loyalty: "Important",
            val_community: "Important",
            schwartz_value_benevolence: "High",
            sdt_need_relatedness: "High",
            val_power_influence: "Minor",
            val_recognition: "Minor"
          }
        },
        {
          value: "justice",
          label: { en: "Join only if the cause is clearly fair/inclusive", zh: "只有明确公平/包容才加入" },
          example: { en: "\"I need to believe it's just — not just feel-good busywork.\"", zh: "「我得相信它公正——不是自我感觉良好的忙。」" },
          maps: {
            val_justice_fairness: "Core value",
            val_equality: "Important",
            val_sustainability: "Important",
            schwartz_value_universalism: "Very high",
            val_patriotism: "Moderate",
            val_loyalty: "Moderate"
          }
        },
        {
          value: "decline",
          label: { en: "Decline — guard personal time and boundaries", zh: "婉拒——守住个人时间与边界" },
          example: { en: "\"My bandwidth is limited; I choose causes very selectively.\"", zh: "「精力有限，我会非常挑 causes。」" },
          maps: {
            val_privacy: "Important",
            val_independence: "Important",
            val_personal_freedom: "Important",
            val_community: "Minor",
            val_helping_others: "Moderate",
            sdt_need_autonomy: "High",
            sdt_need_relatedness: "Low"
          }
        }
      ]
    },
    {
      id: "spiritual_life",
      text: {
        en: "When you think about spirituality, religion, or meaning beyond work:",
        zh: "想到灵性、宗教或工作之外的意义时："
      },
      options: [
        {
          value: "devout",
          label: { en: "Active faith practice shapes daily choices", zh: "活跃的信仰实践影响日常选择" },
          example: { en: "\"My tradition guides ethics, calendar, and community.\"", zh: "「传统指导我的伦理、日程与社群。」" },
          maps: {
            religiosity: "Devout",
            val_spirituality_faith: "Core value",
            val_tradition: "Important",
            schwartz_value_tradition: "Very high",
            schwartz_value_conformity: "High",
            schwartz_value_self_direction: "Low",
            val_adventure: "Minor"
          }
        },
        {
          value: "spiritual",
          label: { en: "Spiritual but not tied to one institution", zh: "有灵性追求但不绑定单一机构" },
          example: { en: "\"I meditate/pray on my own terms — organized religion is optional.\"", zh: "「按自己的方式冥想/反思——组织宗教非必须。」" },
          maps: {
            religiosity: "Spiritual",
            val_spirituality_faith: "Important",
            val_personal_freedom: "Important",
            schwartz_value_self_direction: "High",
            schwartz_value_tradition: "Average",
            schwartz_value_universalism: "Average",
            val_tradition: "Moderate"
          }
        },
        {
          value: "secular",
          label: { en: "Mostly secular — ethics from reason and people", zh: "大体世俗——伦理来自理性与人" },
          example: { en: "\"I don't look to doctrine; I look to evidence and harm.\"", zh: "「我不靠教义；我看证据与伤害。」" },
          maps: {
            religiosity: "Secular",
            val_knowledge_truth: "Important",
            val_justice_fairness: "Important",
            val_spirituality_faith: "Minor",
            schwartz_value_tradition: "Low",
            schwartz_value_conformity: "Low",
            need_for_cognition: "High"
          }
        },
        {
          value: "private",
          label: { en: "Prefer not to discuss or label it", zh: "不愿讨论或贴标签" },
          example: { en: "\"That's private — I'd rather not answer surveys about it.\"", zh: "「这很私人——不想在问卷里回答。」" },
          maps: {
            religiosity: "Prefer not to say",
            val_spirituality_faith: "Moderate",
            val_privacy: "Important",
            val_tradition: "Moderate",
            schwartz_value_tradition: "Average"
          }
        }
      ]
    },
    {
      id: "learning_pull",
      text: {
        en: "A topic fascinates you but has no clear career payoff. You:",
        zh: "有个话题很吸引你，但没有明确职业回报。你会："
      },
      options: [
        {
          value: "deep_dive",
          label: { en: "Go deep anyway — curiosity is enough", zh: "仍然深入——好奇心本身就够了" },
          example: { en: "\"I'll rabbit-hole for weeks if the puzzle is good.\"", zh: "「只要 puzzle 够好，我能钻研好几周。」" },
          maps: {
            need_for_cognition: "Very high",
            val_knowledge_truth: "Core value",
            val_personal_growth: "Important",
            schwartz_value_self_direction: "Very high",
            schwartz_value_stimulation: "High",
            sdt_need_competence: "High",
            val_wealth: "Minor"
          }
        },
        {
          value: "practical",
          label: { en: "Learn only if it might compound professionally", zh: "只有可能叠加职业价值才学" },
          example: { en: "\"Interesting — but I budget learning like an investment.\"", zh: "「有意思——但我把学习当投资来分配。」" },
          maps: {
            val_career_success: "Important",
            val_achievement: "Important",
            need_for_cognition: "Average",
            schwartz_value_achievement: "High",
            sdt_need_competence: "High",
            val_knowledge_truth: "Important"
          }
        },
        {
          value: "social",
          label: { en: "Explore it with friends or a study group", zh: "和朋友或学习小组一起探索" },
          example: { en: "\"Learning sticks when we argue about it together.\"", zh: "「一起讨论、争论时学得最牢。」" },
          maps: {
            sdt_need_relatedness: "Very high",
            val_community: "Important",
            need_for_cognition: "High",
            schwartz_value_benevolence: "Average",
            val_knowledge_truth: "Important"
          }
        },
        {
          value: "skip",
          label: { en: "Usually skip — not enough bandwidth", zh: "通常跳过——精力不够" },
          example: { en: "\"I admire curiosity in others; I protect focus elsewhere.\"", zh: "「我欣赏别人的好奇心；但我把专注用在别处。」" },
          maps: {
            need_for_cognition: "Low",
            val_knowledge_truth: "Moderate",
            val_order_structure: "Important",
            schwartz_value_security: "Average",
            schwartz_value_stimulation: "Low"
          }
        }
      ]
    },
    {
      id: "micromanagement",
      text: {
        en: "Your manager starts requiring detailed logs and sign-offs for small tasks. You feel:",
        zh: "经理开始要求小任务也写详细日志并签字。你的感受："
      },
      options: [
        {
          value: "suffocated",
          label: { en: "Suffocated — I need trust and room", zh: "窒息——我需要信任与空间" },
          example: { en: "\"Treat me like an adult or I'll disengage.\"", zh: "「把我当成年人对待，否则我会消极。」" },
          maps: {
            sdt_need_autonomy: "Very high",
            val_independence: "Core value",
            val_personal_freedom: "Important",
            schwartz_value_self_direction: "Very high",
            schwartz_value_conformity: "Low",
            val_order_structure: "Minor"
          }
        },
        {
          value: "fine",
          label: { en: "Fine — clarity and process help me execute", zh: "没问题——清晰流程帮我执行" },
          example: { en: "\"If the checklist reduces mistakes, I'll use it.\"", zh: "「如果 checklist 能减少错误，我会用。」" },
          maps: {
            val_order_structure: "Important",
            schwartz_value_conformity: "High",
            schwartz_value_security: "High",
            sdt_need_competence: "High",
            sdt_need_autonomy: "Low",
            val_independence: "Moderate"
          }
        },
        {
          value: "negotiate",
          label: { en: "Negotiate lighter process if results stay strong", zh: "若结果好就协商更轻流程" },
          example: { en: "\"I'll comply short-term, then prove outcomes buy flexibility.\"", zh: "「短期配合，再用结果换灵活。」" },
          maps: {
            sdt_need_competence: "Very high",
            val_achievement: "Important",
            sdt_need_autonomy: "Average",
            schwartz_value_achievement: "High",
            schwartz_value_power: "Average"
          }
        },
        {
          value: "team",
          label: { en: "Accept it for team harmony", zh: "为团队和谐接受" },
          example: { en: "\"Not my favorite, but I won't be the friction point.\"", zh: "「不是最喜欢，但不想成为摩擦点。」" },
          maps: {
            val_loyalty: "Important",
            sdt_need_relatedness: "High",
            schwartz_value_conformity: "High",
            schwartz_value_benevolence: "High",
            sdt_need_autonomy: "Low"
          }
        }
      ]
    },
    {
      id: "public_praise",
      text: {
        en: "Your work is praised publicly in front of peers. Honestly, you:",
        zh: "你的工作在同事面前被公开表扬。老实说，你："
      },
      options: [
        {
          value: "love_it",
          label: { en: "Love it — visibility fuels me", zh: "很享受——可见度激励我" },
          example: { en: "\"Recognition in the room matters; I'll perform for it.\"", zh: "「当场认可很重要——我会为此表现。」" },
          maps: {
            val_recognition: "Core value",
            val_social_status: "Important",
            val_achievement: "Important",
            schwartz_value_achievement: "Very high",
            schwartz_value_power: "High",
            sdt_need_relatedness: "Average"
          }
        },
        {
          value: "quiet",
          label: { en: "Prefer private praise — public feels awkward", zh: "更喜欢私下表扬——公开不自在" },
          example: { en: "\"Tell me in a 1:1; don't make me center stage.\"", zh: "「私下告诉我就好；别把我推到中心。」" },
          maps: {
            val_privacy: "Important",
            val_recognition: "Moderate",
            val_social_status: "Minor",
            sdt_need_relatedness: "Average",
            schwartz_value_power: "Low"
          }
        },
        {
          value: "team_credit",
          label: { en: "Redirect credit to the team", zh: "把功劳归于团队" },
          example: { en: "\"Win together — I'd rather celebrate collaborators.\"", zh: "「一起赢——我更想庆祝合作者。」" },
          maps: {
            val_helping_others: "Important",
            val_loyalty: "Important",
            val_community: "Important",
            schwartz_value_benevolence: "Very high",
            val_recognition: "Moderate",
            schwartz_value_power: "Low"
          }
        },
        {
          value: "results",
          label: { en: "Care only if outcomes improved — applause is noise", zh: "只在乎结果是否更好——掌声是噪音" },
          example: { en: "\"Ship the thing; skip the ceremony.\"", zh: "「把事做成；仪式可以省略。」" },
          maps: {
            val_integrity_honesty: "Important",
            val_achievement: "Important",
            val_recognition: "Minor",
            schwartz_value_achievement: "High",
            schwartz_value_hedonism: "Low",
            val_social_status: "Minor"
          }
        }
      ]
    },
    {
      id: "friend_wrong",
      text: {
        en: "A close friend cuts corners on something that could hurt a third party. You:",
        zh: "好友在某事上偷工减料，可能伤害第三方。你会："
      },
      options: [
        {
          value: "call_out",
          label: { en: "Call it out directly — truth over comfort", zh: "直接指出——真相高于舒适" },
          example: { en: "\"I'll risk the friendship before I risk someone else.\"", zh: "「宁可伤友情，也不让别人受害。」" },
          maps: {
            val_integrity_honesty: "Core value",
            val_justice_fairness: "Important",
            val_loyalty: "Moderate",
            schwartz_value_universalism: "High",
            schwartz_value_benevolence: "Average"
          }
        },
        {
          value: "loyal",
          label: { en: "Back them privately, fix it quietly together", zh: "私下支持，一起悄悄补救" },
          example: { en: "\"Loyalty first — we'll make it right without drama.\"", zh: "「忠诚优先——我们悄悄纠正，不闹大。」" },
          maps: {
            val_loyalty: "Core value",
            val_family: "Important",
            schwartz_value_benevolence: "High",
            val_justice_fairness: "Moderate",
            val_integrity_honesty: "Important"
          }
        },
        {
          value: "distance",
          label: { en: "Distance yourself — boundaries matter", zh: "拉开距离——边界很重要" },
          example: { en: "\"I can't be close to people who normalize harm.\"", zh: "「我不能与把伤害正常化的人走太近。」" },
          maps: {
            val_integrity_honesty: "Important",
            val_independence: "Important",
            val_justice_fairness: "Important",
            val_loyalty: "Minor",
            sdt_need_autonomy: "High"
          }
        },
        {
          value: "avoid",
          label: { en: "Avoid conflict — not my battle", zh: "回避冲突——不是我的战场" },
          example: { en: "\"I pick battles carefully; this isn't one.\"", zh: "「我会挑战场；这不是。」" },
          maps: {
            val_loyalty: "Important",
            val_justice_fairness: "Minor",
            schwartz_value_conformity: "Average",
            schwartz_value_security: "Average",
            val_integrity_honesty: "Moderate"
          }
        }
      ]
    },
    {
      id: "national_debate",
      text: {
        en: "In a heated debate about national policy vs global cooperation, you lean:",
        zh: "在激烈的国家政策 vs 全球合作辩论中，你倾向："
      },
      options: [
        {
          value: "patriot",
          label: { en: "Prioritize national interest and identity", zh: "优先本国利益与认同" },
          example: { en: "\"My country first — solidarity starts at home.\"", zh: "「本国优先——团结从家开始。」" },
          maps: {
            val_patriotism: "Core value",
            val_tradition: "Important",
            schwartz_value_tradition: "High",
            schwartz_value_universalism: "Low",
            val_equality: "Moderate"
          }
        },
        {
          value: "global",
          label: { en: "Prioritize global equity and shared problems", zh: "优先全球公平与共同问题" },
          example: { en: "\"Climate and human rights don't stop at borders.\"", zh: "「气候与人权不因国界而停止。」" },
          maps: {
            val_equality: "Core value",
            val_sustainability: "Important",
            val_justice_fairness: "Important",
            schwartz_value_universalism: "Very high",
            val_patriotism: "Moderate",
            schwartz_value_tradition: "Low"
          }
        },
        {
          value: "balanced",
          label: { en: "Balance — local loyalty with global responsibility", zh: "平衡——本地忠诚与全球责任" },
          example: { en: "\"Both matter; I hate false binaries.\"", zh: "「两者都重要；我讨厌虚假二元对立。」" },
          maps: {
            val_patriotism: "Important",
            val_equality: "Important",
            schwartz_value_universalism: "High",
            schwartz_value_tradition: "Average",
            val_justice_fairness: "Important"
          }
        },
        {
          value: "disengage",
          label: { en: "Disengage from politics — focus on what you control", zh: "远离政治——专注可控范围" },
          example: { en: "\"I'll vote, but my meaning is local and personal.\"", zh: "「我会投票，但意义在本地与个人生活。」" },
          maps: {
            val_patriotism: "Minor",
            val_equality: "Moderate",
            val_personal_freedom: "Important",
            schwartz_value_self_direction: "High",
            schwartz_value_power: "Low"
          }
        }
      ]
    },
    {
      id: "living_space",
      text: {
        en: "You can redesign your workspace/home with one priority:",
        zh: "你可以重新设计工作/居住空间，只能优先一项："
      },
      options: [
        {
          value: "beautiful",
          label: { en: "Beauty, art, and sensory calm", zh: "美感、艺术与感官平静" },
          example: { en: "\"If it doesn't feel beautiful, I can't think straight.\"", zh: "「不美就没办法好好思考。」" },
          maps: {
            val_beauty_aesthetics: "Core value",
            val_creativity_self_expression: "Important",
            schwartz_value_stimulation: "Average",
            val_order_structure: "Moderate"
          }
        },
        {
          value: "organized",
          label: { en: "Organization, labels, and zero friction", zh: "井井有条、标签化、零摩擦" },
          example: { en: "\"Everything in its place — chaos drains me.\"", zh: "「物有其位——混乱会耗尽我。」" },
          maps: {
            val_order_structure: "Core value",
            schwartz_value_security: "High",
            schwartz_value_conformity: "Average",
            val_beauty_aesthetics: "Moderate"
          }
        },
        {
          value: "private",
          label: { en: "Privacy, soundproofing, and control of access", zh: "隐私、隔音、掌控进出" },
          example: { en: "\"I need a door that closes — physically and socially.\"", zh: "「我需要一扇能关上的门——物理上也社交上也一样。」" },
          maps: {
            val_privacy: "Core value",
            val_independence: "Important",
            sdt_need_autonomy: "High",
            sdt_need_relatedness: "Low",
            val_community: "Minor"
          }
        },
        {
          value: "welcoming",
          label: { en: "Welcoming to guests and community drop-ins", zh: "欢迎访客与社区串门" },
          example: { en: "\"Open layout — people should feel at home here.\"", zh: "「开放布局——大家来了要像在家。」" },
          maps: {
            val_community: "Important",
            val_family: "Important",
            sdt_need_relatedness: "Very high",
            val_privacy: "Moderate",
            schwartz_value_benevolence: "High"
          }
        }
      ]
    },
    {
      id: "life_principle",
      text: {
        en: "If you had to defend one principle when everything else conflicts, it would be:",
        zh: "若其他一切都冲突，你只能捍卫一条原则，会是："
      },
      options: [
        {
          value: "growth",
          label: { en: "Keep growing — stagnation is failure", zh: "持续成长——停滞即失败" },
          example: { en: "\"I'd rather be learning than comfortable.\"", zh: "「宁可学习，也不要舒适。」" },
          maps: {
            values_priority: "Novelty",
            val_personal_growth: "Core value",
            schwartz_value_stimulation: "Very high",
            schwartz_value_self_direction: "Very high",
            sdt_need_competence: "Very high",
            val_security_stability: "Minor"
          }
        },
        {
          value: "care",
          label: { en: "Take care of people who depend on you", zh: "照顾依赖你的人" },
          example: { en: "\"Achievement means nothing if my people are neglected.\"", zh: "「若忽视重要的人，成就毫无意义。」" },
          maps: {
            values_priority: "Community",
            val_family: "Core value",
            val_helping_others: "Core value",
            schwartz_value_benevolence: "Very high",
            sdt_need_relatedness: "Very high",
            schwartz_value_hedonism: "Low"
          }
        },
        {
          value: "honesty",
          label: { en: "Tell the truth even when costly", zh: "即使代价高也说实话" },
          example: { en: "\"I can recover from failure; I can't recover from self-betrayal.\"", zh: "「失败可恢复；自我背叛不行。」" },
          maps: {
            val_integrity_honesty: "Core value",
            val_knowledge_truth: "Important",
            schwartz_value_universalism: "High",
            val_loyalty: "Moderate",
            schwartz_value_conformity: "Low"
          }
        },
        {
          value: "stability",
          label: { en: "Protect stability for yourself and dependents", zh: "为自己与受养者守住稳定" },
          example: { en: "\"Bold moves are fine — but not if they crater the foundation.\"", zh: "「可以大胆——但不能动摇根基。」" },
          maps: {
            values_priority: "Security",
            val_security_stability: "Core value",
            val_health: "Important",
            schwartz_value_security: "Very high",
            val_adventure: "Minor",
            schwartz_value_stimulation: "Low"
          }
        }
      ]
    }
  ]
};
