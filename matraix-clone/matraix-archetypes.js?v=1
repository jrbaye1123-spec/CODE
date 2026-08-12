/* ============================================================
   MatrAIx 36 — deterministic bilingual archetype reports
   6 core drives × 6 operating modes = 36 public archetypes.
   Matching is local, rule-based, explainable, and dependency-free.
   ============================================================ */

(() => {
  "use strict";

  const L = (en, zh) => ({ en, zh });

  const DRIVES = {
    discovery: {
      code: "DS",
      name: L("Discovery", "探索"),
      adjective: L("Curious", "求知"),
      essence: L(
        "You are energized by unanswered questions, fresh perspectives, and the moment a hidden pattern becomes visible. Understanding is not a detour from action for you; it is what makes action meaningful.",
        "未解的问题、新鲜的视角，以及隐藏规律突然显现的瞬间，会为你补充能量。对你而言，理解并不是行动的绕路，而是让行动真正有意义的前提。"
      ),
      strengths: [
        L("Notices possibilities and connections that conventional thinking can miss.", "能够发现惯性思维容易忽略的可能性与关联。"),
        L("Learns quickly when given room to investigate rather than memorize.", "在可以主动探究而不是机械记忆时，学习速度很快。"),
        L("Keeps ideas flexible long enough for a better explanation to emerge.", "愿意让想法保持开放，直到更好的解释出现。")
      ],
      blindSpots: [
        L("Can keep opening new questions after the original problem is already solvable.", "即使原问题已经可以解决，也可能继续打开新的问题。"),
        L("May undervalue repetition, maintenance, or proven routines once novelty fades.", "新鲜感消退后，可能低估重复、维护和成熟流程的价值。")
      ],
      relationships: L("You connect through shared curiosity. You feel closest to people who can explore an idea without demanding immediate agreement.", "你往往通过共同的好奇心建立联结，也更容易亲近那些可以一起探索观点、而不要求立刻达成一致的人。"),
      stress: L("Under pressure, curiosity can scatter into too many parallel possibilities, making closure feel artificially restrictive.", "在压力下，好奇心可能分散成过多并行可能，让收敛与定案显得像一种不必要的限制。"),
      growth: L("Choose one question worth closing. Define what evidence would be sufficient, then convert discovery into a decision or artifact.", "选择一个值得闭环的问题，先定义什么证据已经足够，再把探索转化为决定或实际产物。"),
      ai: L("Ask AI to surface alternatives, assumptions, and counterexamples, then require it to rank them so exploration still ends in movement.", "让 AI 提供替代方案、隐藏假设和反例，同时要求它进行排序，确保探索最终能够转化为行动。")
    },
    mastery: {
      code: "MS",
      name: L("Mastery", "精进"),
      adjective: L("Exacting", "精研"),
      essence: L(
        "You are motivated by competence, precision, and the satisfaction of making something measurably better. Standards matter because they turn effort into craft.",
        "能力、精确度，以及把事物切实做得更好的满足感，是你的主要动力。标准之所以重要，是因为它能把普通努力转化为真正的专业与技艺。"
      ),
      strengths: [
        L("Builds deep expertise instead of stopping at surface familiarity.", "倾向于建立深入专业能力，而不是停留在表面熟悉。"),
        L("Detects quality gaps and quietly raises the standard of the work.", "能够发现质量缺口，并在不张扬的情况下提高工作标准。"),
        L("Persists through the unglamorous practice required for reliable skill.", "能够坚持完成形成可靠能力所必需、却并不光鲜的练习。")
      ],
      blindSpots: [
        L("Can delay exposure to feedback until the work feels polished enough.", "可能会等到成果足够完善后才愿意接受外部反馈。"),
        L("May interpret an acceptable shortcut as a threat to quality rather than a context-sensitive choice.", "可能把合理的捷径视为对质量的威胁，而不是特定情境下的选择。")
      ],
      relationships: L("You show care through reliability, thoughtful effort, and remembering what good support looks like for a particular person.", "你常通过可靠、用心和记住对方真正需要怎样的支持来表达在意。"),
      stress: L("Under pressure, your standards can harden into perfectionism and make delegation feel riskier than doing everything yourself.", "在压力下，高标准可能固化为完美主义，使授权他人看起来比亲自完成更有风险。"),
      growth: L("Separate excellence from flawlessness. Ship at a declared quality bar, gather evidence, and reserve perfection for the few details that truly compound.", "区分卓越与毫无瑕疵：按照事先声明的质量线交付并收集反馈，只把极致投入留给真正会产生复利的少数细节。"),
      ai: L("Use AI as a rigorous reviewer: ask for edge cases, quality checks, and explicit uncertainty, but keep final standards under your control.", "把 AI 当作严格的审阅者：要求它寻找边界情况、执行质量检查并明确表达不确定性，但最终标准仍由你掌控。")
    },
    impact: {
      code: "IM",
      name: L("Impact", "影响"),
      adjective: L("Visionary", "远见"),
      essence: L(
        "You orient toward outcomes: movement, visible progress, and the chance to shape what happens next. An idea becomes exciting when it can alter reality.",
        "你天然关注结果、推进和可见的进展，也希望自己能够影响下一步会发生什么。一个想法真正令你兴奋，往往是因为它有机会改变现实。"
      ),
      strengths: [
        L("Turns ambition into direction and gives people a reason to move.", "能够把雄心转化为方向，并让他人看见行动的理由。"),
        L("Makes decisions when continued hesitation costs more than imperfect action.", "当持续犹豫的成本高于不完美行动时，能够及时做出决定。"),
        L("Maintains attention on consequential outcomes rather than ceremonial activity.", "更关注真正重要的结果，而不是形式化的忙碌。")
      ],
      blindSpots: [
        L("Can move faster than alignment, leaving quieter concerns undiscovered.", "推进速度可能快于共识形成，使较安静的担忧未被发现。"),
        L("May attach self-worth too closely to momentum, recognition, or measurable wins.", "可能把自我价值与推进速度、认可或可量化成果绑定得过紧。")
      ],
      relationships: L("You invest strongly in people and projects that feel consequential. Respect grows when commitments produce visible follow-through.", "你会强烈投入那些真正重要的人和项目，也更容易尊重能够把承诺转化为实际行动的人。"),
      stress: L("Under pressure, urgency can become control; slower processing may look like resistance even when it contains useful information.", "在压力下，紧迫感可能变成控制欲；即使较慢的思考包含重要信息，你也可能先把它理解为阻力。"),
      growth: L("Before accelerating, identify whose information is missing. Durable influence comes from combining direction with enough participation to make change stick.", "在加速前，先确认还缺少谁的信息。持久影响力来自明确方向，也来自足够的参与，让改变真正站得住。"),
      ai: L("Ask AI for decision briefs, leverage points, and next actions. Require success metrics so persuasive language never substitutes for actual impact.", "让 AI 提供决策简报、杠杆点和下一步行动，并要求明确成功指标，避免有说服力的文字取代真实影响。")
    },
    connection: {
      code: "CN",
      name: L("Connection", "联结"),
      adjective: L("Empathic", "共情"),
      essence: L(
        "You are guided by human meaning: trust, belonging, fairness, and the quality of the space between people. Progress matters most when people can remain whole inside it.",
        "信任、归属、公平，以及人与人之间关系的质量，会引导你的选择。进步固然重要，但你更关心人是否能在进步的过程中保持完整。"
      ),
      strengths: [
        L("Reads emotional and social context that purely technical analysis can miss.", "能够识别纯技术分析容易忽略的情绪与社会语境。"),
        L("Builds trust by making people feel heard without abandoning substance.", "让人感到被认真倾听，同时不牺牲实质内容，从而建立信任。"),
        L("Recognizes that durable cooperation depends on fairness and psychological safety.", "理解持久合作依赖公平感与心理安全。")
      ],
      blindSpots: [
        L("Can absorb other people's needs until your own position becomes difficult to locate.", "可能吸收过多他人的需求，以至于自己的立场变得难以辨认。"),
        L("May postpone necessary conflict in an attempt to preserve immediate harmony.", "为了维持眼前和谐，可能推迟必要的冲突。")
      ],
      relationships: L("You notice tone, reciprocity, and whether care is mutual. Honest warmth is more persuasive to you than polished performance.", "你会注意语气、互惠，以及关心是否双向。真诚的温度通常比精心设计的表现更能说服你。"),
      stress: L("Under pressure, sensitivity to others can become over-responsibility, emotional saturation, or indirect communication.", "在压力下，对他人的敏感可能变成过度负责、情绪饱和或间接表达。"),
      growth: L("Practice kind clarity: state the need, boundary, or disagreement early enough that the relationship does not have to carry hidden resentment.", "练习温和而清晰的表达：及时说出需求、边界或分歧，不让关系承担未说出口的怨气。"),
      ai: L("Ask AI to consider stakeholder impact and tone, but instruct it not to smooth away disagreement. Empathy is strongest when paired with truthful boundaries.", "让 AI 考虑利益相关者的影响与语气，但不要让它为了圆滑而抹去分歧。共情与真实边界结合时才最有力量。")
    },
    stability: {
      code: "ST",
      name: L("Stability", "稳定"),
      adjective: L("Grounded", "稳健"),
      essence: L(
        "You are motivated by continuity, responsibility, and systems people can safely rely on. You look beyond the exciting launch to ask what will still work later.",
        "连续性、责任，以及人们能够安全依赖的系统，是你的主要动力。你不会只关注令人兴奋的启动阶段，也会追问它在未来是否依然有效。"
      ),
      strengths: [
        L("Anticipates downstream consequences and protects against avoidable failure.", "能够预判后续影响，并防止本可避免的失败。"),
        L("Creates consistency that lets other people focus and perform with confidence.", "建立稳定一致的环境，使他人能够安心专注并发挥能力。"),
        L("Honors commitments even after attention and novelty move elsewhere.", "即使注意力和新鲜感已经转移，仍然愿意履行承诺。")
      ],
      blindSpots: [
        L("Can preserve a familiar system after its original purpose has disappeared.", "即使原本目的已经消失，也可能继续维护熟悉的系统。"),
        L("May overestimate the cost of experimentation and underestimate the cost of standing still.", "可能高估试验的成本，同时低估停滞不前的成本。")
      ],
      relationships: L("Trust is built through consistency, discretion, and actions that remain dependable when circumstances become inconvenient.", "对你来说，信任来自一致、分寸，以及在情况变得不方便时仍然可靠的行动。"),
      stress: L("Under pressure, responsible caution can become rigidity, repeated checking, or a need to control variables that cannot be controlled.", "在压力下，负责任的谨慎可能变成僵化、反复检查，或试图控制本来无法控制的变量。"),
      growth: L("Create a bounded experiment with a rollback plan. Safety does not require zero change; it requires making change observable and recoverable.", "设计一个有边界且可以回滚的实验。安全并不要求完全不变，而是让变化可观察、可恢复。"),
      ai: L("Ask AI for risk registers, assumptions, and fallback plans. Also ask what inaction costs, so caution evaluates both sides of the decision.", "让 AI 提供风险清单、假设与备选方案，同时询问不行动的代价，让谨慎能够评估决策的两面。")
    },
    autonomy: {
      code: "AU",
      name: L("Autonomy", "自主"),
      adjective: L("Independent", "自主"),
      essence: L(
        "You are motivated by agency: the freedom to form your own judgment, choose your method, and remain the author of your commitments. Ownership unlocks your best effort.",
        "自主判断、选择方法，并成为自己承诺的真正作者，是你的核心动力。当你拥有真实的所有权时，往往能投入最好的努力。"
      ),
      strengths: [
        L("Forms an original position instead of borrowing certainty from the group.", "能够形成自己的立场，而不是从群体中借用确定感。"),
        L("Works with unusual persistence when responsibility and authority are aligned.", "当责任与权限一致时，能够展现出非同寻常的持续投入。"),
        L("Protects space for unconventional methods and personally meaningful choices.", "愿意为非传统方法和真正重要的个人选择保留空间。")
      ],
      blindSpots: [
        L("Can resist useful structure when it arrives in the language of control.", "当有用的结构以控制的语言出现时，可能本能地抗拒。"),
        L("May wait too long to share work, ask for help, or make dependencies visible.", "可能过晚才分享进度、寻求帮助或暴露依赖关系。")
      ],
      relationships: L("You value closeness without possession. Respect for boundaries and voluntary commitment are central to your trust.", "你重视亲近但不接受占有。对边界的尊重和自愿承诺，是你建立信任的核心。"),
      stress: L("Under pressure, a need for agency can become withdrawal, oppositional reflexes, or carrying too much alone.", "在压力下，对自主的需要可能变成退缩、反射性反对，或独自承担过多。"),
      growth: L("Negotiate constraints instead of merely rejecting them. Make the outcome, decision rights, and check-in points explicit, then preserve freedom inside that frame.", "与其单纯拒绝限制，不如协商限制：明确结果、决策权和检查节点，再在这个框架内保留自由。"),
      ai: L("Use AI as an option generator rather than an authority. Ask for trade-offs and editable plans so the final judgment remains recognizably yours.", "把 AI 当作选项生成器而不是权威，要求它说明取舍并提供可编辑计划，让最终判断仍然清晰地属于你。")
    }
  };

  const MODES = {
    architect: {
      code: "AR",
      name: L("Architect", "架构者"),
      essence: L("Your natural move is to model the whole: clarify principles, identify dependencies, and design a structure before committing resources.", "你的自然动作是先建立整体模型：澄清原则、识别依赖，并在投入资源前设计结构。"),
      strengths: [
        L("Turns ambiguity into maps, frameworks, and coherent priorities.", "能够把模糊转化为地图、框架和连贯的优先级。"),
        L("Sees how local decisions interact across a larger system.", "能够看到局部决定如何在更大系统中相互作用。")
      ],
      blindSpots: [
        L("May design for edge cases before the central path has been tested.", "可能在核心路径尚未验证前，就开始为边界情况设计。"),
        L("Can mistake conceptual coherence for evidence that the system works in practice.", "可能把概念上的完整误认为系统在现实中有效的证据。")
      ],
      work: L("You do your best work with a meaningful problem, access to context, and permission to shape the system rather than merely execute isolated tasks.", "当问题具有意义、背景信息充分，并且你被允许塑造系统而不只是执行孤立任务时，最容易发挥优势。"),
      stress: L("You may retreat into more analysis and redesign when direct contact with reality would resolve uncertainty faster.", "当直接接触现实能更快消除不确定性时，你可能仍会退回更多分析与重新设计。"),
      growth: L("Test the load-bearing assumption first. A small live prototype can teach more than another complete diagram.", "先测试最关键的承重假设。一个小型真实原型，可能比另一张完整图表带来更多信息。"),
      ai: L("Ask for system maps, dependencies, failure modes, and architecture alternatives; then require one smallest testable path.", "要求 AI 提供系统地图、依赖、失败模式与架构备选方案，然后让它给出一条最小可验证路径。")
    },
    explorer: {
      code: "EX",
      name: L("Explorer", "探索者"),
      essence: L("Your natural move is to enter the unknown, sample the environment, and let new information reshape the route.", "你的自然动作是进入未知、感知环境，并允许新信息不断重塑路线。"),
      strengths: [
        L("Adapts quickly when reality refuses to follow the original plan.", "当现实不按原计划发展时，能够快速适应。"),
        L("Finds promising paths through experimentation and broad exposure.", "能够通过实验与广泛接触发现有潜力的路径。")
      ],
      blindSpots: [
        L("Can generate more starts than finishes.", "开始的事情可能多于真正完成的事情。"),
        L("May leave useful lessons undocumented while attention moves to the next frontier.", "当注意力转向下一个前沿时，可能没有记录已经获得的有用经验。")
      ],
      work: L("You thrive with room to investigate, short feedback loops, and goals that allow the route to change as evidence arrives.", "当你拥有探索空间、短反馈周期，并且目标允许路线随证据变化时，最容易进入状态。"),
      stress: L("You may escape a difficult middle by finding a more interesting beginning.", "面对困难的中间阶段时，你可能通过寻找一个更有趣的新开始来逃离。"),
      growth: L("Keep an exploration log and define a stopping rule. Curiosity compounds when discoveries become reusable knowledge.", "保留探索日志并定义停止规则。当发现能够沉淀为可复用知识时，好奇心才会产生复利。"),
      ai: L("Ask for hypotheses, experiments, and unusual analogies, followed by a checkpoint that decides whether to continue, pivot, or stop.", "要求 AI 提供假设、实验和不寻常的类比，并设置检查点来决定继续、转向或停止。")
    },
    builder: {
      code: "BU",
      name: L("Builder", "建造者"),
      essence: L("Your natural move is to make the idea tangible: assemble the parts, solve the practical constraints, and improve through use.", "你的自然动作是让想法变得可触摸：组装部件、解决实际限制，并在使用中持续改进。"),
      strengths: [
        L("Converts intention into concrete progress people can inspect and use.", "能够把意图转化为人们可以检查和使用的实际进展。"),
        L("Learns from friction and improves the work through iteration.", "能够从摩擦中学习，并通过迭代改进成果。")
      ],
      blindSpots: [
        L("Can optimize the current build before confirming it solves the right problem.", "可能在确认问题是否正确之前，就开始优化当前实现。"),
        L("May carry execution personally instead of investing in reusable systems or delegation.", "可能倾向于亲自承担执行，而不是投资可复用系统或授权。")
      ],
      work: L("You prefer clear ownership, visible progress, practical constraints, and enough continuity to turn prototypes into dependable outcomes.", "你偏好明确所有权、可见进展、现实约束，以及足够的连续性，把原型转化为可靠结果。"),
      stress: L("You may respond to uncertainty by working harder on the nearest task, even when the priority itself needs reconsideration.", "面对不确定性时，你可能在最近的任务上更加用力，即使真正需要重新考虑的是优先级本身。"),
      growth: L("Pause at milestones to ask whether the build still serves the outcome. Standardize what repeats and delegate what no longer requires your learning.", "在里程碑处暂停，确认当前实现是否仍服务于目标；标准化重复工作，并授权那些不再需要你亲自学习的部分。"),
      ai: L("Ask AI for implementation plans, checklists, examples, and tests. Keep outputs concrete enough to verify in the real workflow.", "让 AI 提供实施计划、清单、示例与测试，并确保输出足够具体，可以在真实流程中验证。")
    },
    catalyst: {
      code: "CA",
      name: L("Catalyst", "催化者"),
      essence: L("Your natural move is to create momentum: frame the opportunity, raise the energy, and help a group cross from intention into action.", "你的自然动作是创造动能：定义机会、提升能量，并帮助群体从意愿跨越到行动。"),
      strengths: [
        L("Makes change feel possible and gives uncertainty a direction.", "让改变显得可行，并为不确定性提供方向。"),
        L("Mobilizes attention, people, and decisions around a consequential moment.", "能够在关键时刻调动注意力、人员与决策。")
      ],
      blindSpots: [
        L("Can outrun operational detail or the quieter pace of genuine buy-in.", "推进速度可能超过运营细节，或超过真正形成认同所需要的较慢节奏。"),
        L("May experience steady maintenance as a loss of energy rather than the completion of change.", "可能把稳定维护体验为能量流失，而不是改变真正完成的一部分。")
      ],
      work: L("You are strongest where a team needs conviction, a stuck initiative needs movement, or a complex opportunity needs a compelling frame.", "当团队需要信心、停滞项目需要推进，或复杂机会需要有力叙事时，你最能发挥价值。"),
      stress: L("You may increase intensity when the real need is listening, sequencing, or operational patience.", "在真正需要倾听、排序或运营耐心时，你可能反而继续提高强度。"),
      growth: L("Pair every mobilizing message with an owner, a next checkpoint, and space for dissent. Momentum lasts when it can survive your absence.", "每个动员信息都配上负责人、下一个检查点和表达异议的空间。只有在你不在场时仍能持续，动能才真正稳固。"),
      ai: L("Ask AI to sharpen narratives, stakeholder calls to action, and decision cadence, then challenge it to expose adoption risks.", "让 AI 打磨叙事、利益相关者行动号召和决策节奏，同时要求它揭示采纳风险。")
    },
    connector: {
      code: "CO",
      name: L("Connector", "联结者"),
      essence: L("Your natural move is to bridge: translate across perspectives, find mutual interests, and create the trust required for coordination.", "你的自然动作是搭桥：翻译不同视角、寻找共同利益，并建立协作所需的信任。"),
      strengths: [
        L("Makes complex or divided groups more capable of understanding one another.", "能够帮助复杂或分裂的群体更好地理解彼此。"),
        L("Notices missing voices, relational friction, and opportunities for reciprocity.", "能够注意到缺席的声音、关系摩擦与互惠机会。")
      ],
      blindSpots: [
        L("Can spend too much energy maintaining relationships that no longer support the shared purpose.", "可能花费过多精力维护已经不再支持共同目标的关系。"),
        L("May translate disagreement so gently that the decision point becomes unclear.", "可能把分歧翻译得过于温和，以至于真正的决策点变得不清楚。")
      ],
      work: L("You excel in cross-functional work, facilitation, partnerships, and any setting where progress depends on trust across different languages or incentives.", "你擅长跨职能协作、引导、伙伴关系，以及任何依赖不同语言或激励之间建立信任才能推进的环境。"),
      stress: L("You may over-coordinate, seek universal agreement, or carry communication work that others need to own themselves.", "在压力下，你可能过度协调、追求所有人一致，或承担本应由他人负责的沟通工作。"),
      growth: L("Name the actual decision after building understanding. Connection is not the absence of tension; it is the capacity to move through tension without losing respect.", "在建立理解之后，明确真正需要做出的决定。联结并不是没有张力，而是在不失去尊重的前提下穿越张力。"),
      ai: L("Ask AI for audience-specific translations, meeting synthesis, and stakeholder maps, while preserving explicit disagreements and owners.", "让 AI 针对不同受众进行翻译、总结会议并绘制利益相关者地图，同时保留明确分歧和责任人。")
    },
    guardian: {
      code: "GU",
      name: L("Guardian", "守护者"),
      essence: L("Your natural move is to protect what must remain trustworthy: standards, people, continuity, and the boundaries that prevent avoidable harm.", "你的自然动作是保护那些必须保持可信的事物：标准、人员、连续性，以及防止可避免伤害的边界。"),
      strengths: [
        L("Detects risk, inconsistency, and neglected responsibilities before they become crises.", "能够在风险、不一致和被忽视的责任演变成危机前发现它们。"),
        L("Creates dependable boundaries without needing constant recognition.", "能够建立可靠边界，而不需要持续获得认可。")
      ],
      blindSpots: [
        L("Can make exceptions difficult even when context has genuinely changed.", "即使情境已经真正变化，也可能很难接受例外。"),
        L("May communicate the risk more clearly than the path that would make progress safe.", "可能比安全推进的路径更清楚地表达风险本身。")
      ],
      work: L("You are valuable wherever quality, ethics, safety, institutional memory, or long-term reliability cannot be left to chance.", "在质量、伦理、安全、组织记忆或长期可靠性不能依赖运气的地方，你具有重要价值。"),
      stress: L("You may tighten rules and monitoring when collaborative problem-solving would create stronger ownership.", "在协作解决问题能够建立更强所有权时，你可能反而收紧规则与监控。"),
      growth: L("Turn every objection into a safe-to-proceed condition. Protection becomes enabling when people know what evidence or safeguard will earn a yes.", "把每个反对意见转化为可以安全推进的条件。当人们知道什么证据或保障能够获得同意时，保护就会成为赋能。"),
      ai: L("Ask AI for audits, compliance checks, pre-mortems, and monitoring plans, plus a clear remediation path for each issue found.", "让 AI 执行审计、合规检查、事前验尸与监控计划，并为每个发现的问题提供明确修复路径。")
    }
  };

  const DRIVE_ORDER = ["discovery", "mastery", "impact", "connection", "stability", "autonomy"];
  const MODE_ORDER = ["architect", "explorer", "builder", "catalyst", "connector", "guardian"];

  const ARCHETYPES = [];
  for (const modeId of MODE_ORDER) {
    for (const driveId of DRIVE_ORDER) {
      const drive = DRIVES[driveId];
      const mode = MODES[modeId];
      ARCHETYPES.push({
        id: `${driveId}-${modeId}`,
        code: `${drive.code}-${mode.code}`,
        driveId,
        modeId,
        name: L(`${drive.adjective.en} ${mode.name.en}`, `${drive.adjective.zh}${mode.name.zh}`)
      });
    }
  }

  const CORE_VALUE_MAP = {
    achievement: "impact", security: "stability", autonomy: "autonomy",
    community: "connection", novelty: "discovery", tradition: "stability"
  };

  const DECISION_MODE_MAP = {
    analytical: "architect", intuitive: "explorer", "consensus-driven": "connector",
    directive: "catalyst", deliberative: "guardian"
  };

  const CHARACTER_DRIVES = {
    discovery: ["trait_curiosity", "trait_creativity", "trait_love_of_learning", "trait_open_mindedness", "trait_perspective", "trait_appreciation_of_beauty"],
    mastery: ["trait_perseverance", "trait_prudence", "trait_self_regulation", "trait_discipline", "trait_honesty"],
    impact: ["trait_bravery", "trait_zest", "trait_leadership", "trait_ambition", "trait_competitiveness", "trait_resilience"],
    connection: ["trait_capacity_for_love", "trait_kindness", "trait_social_intelligence", "trait_teamwork", "trait_fairness", "trait_empathy", "trait_generosity"],
    stability: ["trait_prudence", "trait_self_regulation", "trait_loyalty", "trait_humility", "trait_forgiveness"],
    autonomy: ["trait_bravery", "trait_adaptability", "trait_honesty", "trait_resilience"]
  };

  const VALUE_DRIVES = {
    discovery: ["val_knowledge_truth", "val_creativity_self_expression", "val_personal_growth", "val_adventure", "val_beauty_aesthetics"],
    mastery: ["val_order_structure", "val_integrity_honesty", "val_personal_growth", "val_knowledge_truth"],
    impact: ["val_career_success", "val_achievement", "val_power_influence", "val_recognition", "val_social_status", "val_wealth"],
    connection: ["val_family", "val_community", "val_helping_others", "val_equality", "val_justice_fairness", "val_loyalty"],
    stability: ["val_security_stability", "val_tradition", "val_health", "val_privacy", "val_order_structure", "val_loyalty"],
    autonomy: ["val_personal_freedom", "val_independence", "val_privacy", "val_creativity_self_expression"]
  };

  const BIG_FIVE_GROUPS = {
    openness: ["big5_imagination", "big5_artistic_interest", "big5_emotionality", "big5_adventurousness", "big5_intellect", "big5_liberalism"],
    conscientiousness: ["big5_self_efficacy", "big5_orderliness", "big5_dutifulness", "big5_achievement_striving", "big5_self_discipline", "big5_cautiousness"],
    extraversion: ["big5_friendliness", "big5_gregariousness", "big5_assertiveness", "big5_activity_level", "big5_excitement_seeking", "big5_cheerfulness"],
    agreeableness: ["big5_trust", "big5_morality", "big5_altruism", "big5_cooperation", "big5_modesty", "big5_sympathy"]
  };

  const RULE_DIMENSIONS = new Set([
    "dominant_trait", "risk_tolerance", "decision_style", "values_priority", "tone_expected", "trust_level",
    "intent", "modality_pref", "learning_style", "media_diet", "lstyle_social_battery", "lstyle_planning_horizon",
    "lstyle_punctuality", "lstyle_tidiness", "peeve_micromanagement",
    "cog_detail_orientation", "cog_abstraction", "cog_curiosity", "cog_skepticism", "cog_open_mindedness",
    "cog_assertiveness", "cog_emotional_expressiveness", "cog_conflict_approach", "cog_feedback_receptiveness",
    "cog_ambiguity_tolerance", "cog_perfectionism", "cog_multitasking", "cog_question_asking", "cog_decision_speed",
    "cog_big_picture_vs_detail", "cog_empathy_expression", "cog_storytelling", "cog_precision_of_language"
  ]);
  Object.values(CHARACTER_DRIVES).flat().forEach(id => RULE_DIMENSIONS.add(id));
  Object.values(VALUE_DRIVES).flat().forEach(id => RULE_DIMENSIONS.add(id));
  Object.values(BIG_FIVE_GROUPS).flat().forEach(id => RULE_DIMENSIONS.add(id));

  function normalized(value) {
    return String(value ?? "").trim().toLowerCase();
  }

  function scaleStrength(value) {
    const v = normalized(value);
    if (["signature", "core value", "very high", "major peeve"].includes(v)) return 1;
    if (["strong", "important", "high", "annoys"].includes(v)) return 0.72;
    if (["moderate", "average", "neutral", "balanced"].includes(v)) return 0.18;
    if (["slight", "minor", "low"].includes(v)) return 0.05;
    return 0;
  }

  function orderedScale(value) {
    const v = normalized(value);
    const map = { "very high": 1, high: 0.7, average: 0, moderate: 0, low: -0.7, "very low": -1, none: -1 };
    return map[v] ?? 0;
  }

  function emptyScores(keys) {
    return Object.fromEntries(keys.map(key => [key, 0]));
  }

  function addScore(scores, evidence, target, points, dimension, value) {
    if (!target || !Number.isFinite(points) || points <= 0) return;
    scores[target] += points;
    evidence.push({ target, points, dimension, value: String(value ?? "") });
  }

  function addStrengthRules(answers, scores, evidence, groups, weight) {
    for (const [target, ids] of Object.entries(groups)) {
      for (const id of ids) {
        const value = answers[id];
        const amount = scaleStrength(value);
        if (amount > 0) addScore(scores, evidence, target, amount * weight, id, value);
      }
    }
  }

  function addBigFiveRules(answers, driveScores, modeScores, evidence) {
    const averages = {};
    for (const [group, ids] of Object.entries(BIG_FIVE_GROUPS)) {
      const values = ids.filter(id => answers[id] != null).map(id => orderedScale(answers[id]));
      averages[group] = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0;
    }
    const o = averages.openness;
    if (o > 0) {
      addScore(driveScores, evidence, "discovery", o * 3.2, "big5_openness", "aggregate");
      addScore(modeScores, evidence, "explorer", o * 2.4, "big5_openness", "aggregate");
      addScore(modeScores, evidence, "architect", o * 1.2, "big5_openness", "aggregate");
    } else if (o < 0) {
      addScore(driveScores, evidence, "stability", -o * 2, "big5_openness", "aggregate");
      addScore(modeScores, evidence, "guardian", -o * 1.5, "big5_openness", "aggregate");
    }
    const c = averages.conscientiousness;
    if (c > 0) {
      addScore(driveScores, evidence, "mastery", c * 2.6, "big5_conscientiousness", "aggregate");
      addScore(driveScores, evidence, "stability", c * 1.4, "big5_conscientiousness", "aggregate");
      addScore(modeScores, evidence, "builder", c * 2, "big5_conscientiousness", "aggregate");
      addScore(modeScores, evidence, "guardian", c * 1.5, "big5_conscientiousness", "aggregate");
    }
    const e = averages.extraversion;
    if (e > 0) {
      addScore(driveScores, evidence, "impact", e * 2, "big5_extraversion", "aggregate");
      addScore(driveScores, evidence, "connection", e, "big5_extraversion", "aggregate");
      addScore(modeScores, evidence, "catalyst", e * 2.5, "big5_extraversion", "aggregate");
      addScore(modeScores, evidence, "connector", e * 1.2, "big5_extraversion", "aggregate");
    } else if (e < 0) {
      addScore(driveScores, evidence, "autonomy", -e * 1.3, "big5_extraversion", "aggregate");
      addScore(modeScores, evidence, "architect", -e * 1.2, "big5_extraversion", "aggregate");
    }
    const a = averages.agreeableness;
    if (a > 0) {
      addScore(driveScores, evidence, "connection", a * 3, "big5_agreeableness", "aggregate");
      addScore(modeScores, evidence, "connector", a * 2.3, "big5_agreeableness", "aggregate");
      addScore(modeScores, evidence, "guardian", a, "big5_agreeableness", "aggregate");
    }
  }

  function addExactRules(answers, driveScores, modeScores, evidence) {
    const coreValue = CORE_VALUE_MAP[normalized(answers.values_priority)];
    addScore(driveScores, evidence, coreValue, 6, "values_priority", answers.values_priority);

    const decisionMode = DECISION_MODE_MAP[normalized(answers.decision_style)];
    addScore(modeScores, evidence, decisionMode, 6, "decision_style", answers.decision_style);

    const dominant = normalized(answers.dominant_trait);
    if (dominant.includes("openness")) {
      addScore(driveScores, evidence, "discovery", 3, "dominant_trait", answers.dominant_trait);
      addScore(modeScores, evidence, "explorer", 2, "dominant_trait", answers.dominant_trait);
    } else if (dominant.includes("conscientiousness")) {
      addScore(driveScores, evidence, "mastery", 2.5, "dominant_trait", answers.dominant_trait);
      addScore(modeScores, evidence, "builder", 2, "dominant_trait", answers.dominant_trait);
    } else if (dominant.includes("extraversion")) {
      addScore(driveScores, evidence, "impact", 2, "dominant_trait", answers.dominant_trait);
      addScore(modeScores, evidence, "catalyst", 2.5, "dominant_trait", answers.dominant_trait);
    } else if (dominant.includes("agreeableness")) {
      addScore(driveScores, evidence, "connection", 3, "dominant_trait", answers.dominant_trait);
      addScore(modeScores, evidence, "connector", 2.5, "dominant_trait", answers.dominant_trait);
    }

    const risk = normalized(answers.risk_tolerance);
    if (risk === "risk-seeking" || risk === "risk-tolerant") {
      addScore(driveScores, evidence, "discovery", risk === "risk-seeking" ? 2.4 : 1.4, "risk_tolerance", answers.risk_tolerance);
      addScore(modeScores, evidence, "explorer", risk === "risk-seeking" ? 2.5 : 1.4, "risk_tolerance", answers.risk_tolerance);
      addScore(modeScores, evidence, "catalyst", 1.2, "risk_tolerance", answers.risk_tolerance);
    } else if (risk === "risk-averse" || risk === "cautious") {
      addScore(driveScores, evidence, "stability", risk === "risk-averse" ? 2.5 : 1.5, "risk_tolerance", answers.risk_tolerance);
      addScore(modeScores, evidence, "guardian", risk === "risk-averse" ? 2.5 : 1.5, "risk_tolerance", answers.risk_tolerance);
    }

    const tone = normalized(answers.tone_expected);
    if (tone.includes("warm")) {
      addScore(driveScores, evidence, "connection", 1.5, "tone_expected", answers.tone_expected);
      addScore(modeScores, evidence, "connector", 1.5, "tone_expected", answers.tone_expected);
    } else if (tone === "detailed" || tone === "formal") {
      addScore(driveScores, evidence, "mastery", 0.9, "tone_expected", answers.tone_expected);
      addScore(modeScores, evidence, "architect", 1, "tone_expected", answers.tone_expected);
    } else if (tone === "concise" || tone === "blunt") {
      addScore(driveScores, evidence, "impact", 0.8, "tone_expected", answers.tone_expected);
      addScore(modeScores, evidence, "builder", 0.8, "tone_expected", answers.tone_expected);
    } else if (tone === "playful") {
      addScore(driveScores, evidence, "discovery", 0.8, "tone_expected", answers.tone_expected);
      addScore(modeScores, evidence, "explorer", 0.8, "tone_expected", answers.tone_expected);
    }

    const trust = normalized(answers.trust_level);
    if (trust === "verifying" || trust === "skeptical") {
      addScore(driveScores, evidence, "mastery", 0.8, "trust_level", answers.trust_level);
      addScore(modeScores, evidence, "guardian", trust === "skeptical" ? 1.2 : 0.8, "trust_level", answers.trust_level);
    } else if (trust === "trusting") {
      addScore(driveScores, evidence, "connection", 0.8, "trust_level", answers.trust_level);
      addScore(modeScores, evidence, "connector", 0.6, "trust_level", answers.trust_level);
    }

    const intent = normalized(answers.intent);
    if (intent.includes("learn") || intent.includes("brainstorm")) {
      addScore(driveScores, evidence, "discovery", 1.2, "intent", answers.intent);
      addScore(modeScores, evidence, "explorer", 1, "intent", answers.intent);
    } else if (intent.includes("task") || intent.includes("debug")) {
      addScore(modeScores, evidence, "builder", 1.2, "intent", answers.intent);
    } else if (intent.includes("support")) {
      addScore(driveScores, evidence, "connection", 1, "intent", answers.intent);
      addScore(modeScores, evidence, "connector", 1, "intent", answers.intent);
    } else if (intent.includes("verify") || intent.includes("red-team")) {
      addScore(modeScores, evidence, "guardian", 1.2, "intent", answers.intent);
    }
  }

  function addCognitiveRules(answers, driveScores, modeScores, evidence) {
    const high = id => orderedScale(answers[id]);
    const positive = (id, targets, weight, scores) => {
      const amount = high(id);
      if (amount > 0) targets.forEach(([target, share]) => addScore(scores, evidence, target, amount * weight * share, id, answers[id]));
    };

    positive("cog_curiosity", [["discovery", 1]], 2, driveScores);
    positive("cog_open_mindedness", [["discovery", 1]], 1.6, driveScores);
    positive("cog_ambiguity_tolerance", [["discovery", 0.7], ["autonomy", 0.3]], 1.5, driveScores);
    positive("cog_detail_orientation", [["mastery", 1]], 1.7, driveScores);
    positive("cog_perfectionism", [["mastery", 1]], 1.3, driveScores);
    positive("cog_assertiveness", [["impact", 1]], 1.6, driveScores);
    positive("cog_emotional_expressiveness", [["connection", 1]], 1.1, driveScores);
    positive("cog_empathy_expression", [["connection", 1]], 1.8, driveScores);
    positive("cog_skepticism", [["mastery", 0.6], ["autonomy", 0.4]], 1.2, driveScores);

    positive("cog_abstraction", [["architect", 0.7], ["explorer", 0.3]], 1.8, modeScores);
    positive("cog_big_picture_vs_detail", [["architect", 1]], 1.3, modeScores);
    positive("cog_detail_orientation", [["architect", 0.5], ["guardian", 0.5]], 1.4, modeScores);
    positive("cog_curiosity", [["explorer", 1]], 1.5, modeScores);
    positive("cog_ambiguity_tolerance", [["explorer", 1]], 1.5, modeScores);
    positive("cog_assertiveness", [["catalyst", 1]], 1.6, modeScores);
    positive("cog_storytelling", [["catalyst", 0.6], ["connector", 0.4]], 1.3, modeScores);
    positive("cog_empathy_expression", [["connector", 1]], 1.6, modeScores);
    positive("cog_precision_of_language", [["architect", 0.5], ["guardian", 0.5]], 1.3, modeScores);
    positive("cog_perfectionism", [["guardian", 0.7], ["architect", 0.3]], 1.2, modeScores);

    const conflict = normalized(answers.cog_conflict_approach);
    const conflictMap = { confronting: "catalyst", collaborative: "connector", compromising: "connector", avoidant: "guardian", accommodating: "connector" };
    addScore(modeScores, evidence, conflictMap[conflict], 1.2, "cog_conflict_approach", answers.cog_conflict_approach);

    const modality = normalized(answers.modality_pref);
    if (["code", "step-by-step", "examples-first"].includes(modality)) addScore(modeScores, evidence, "builder", 1, "modality_pref", answers.modality_pref);
    if (["visual / diagram", "tabular"].includes(modality)) addScore(modeScores, evidence, "architect", 1, "modality_pref", answers.modality_pref);

    const social = normalized(answers.lstyle_social_battery);
    if (social.includes("extrovert")) {
      addScore(modeScores, evidence, "catalyst", 1.2, "lstyle_social_battery", answers.lstyle_social_battery);
      addScore(modeScores, evidence, "connector", 1, "lstyle_social_battery", answers.lstyle_social_battery);
    } else if (social.includes("introvert")) {
      addScore(modeScores, evidence, "architect", 1, "lstyle_social_battery", answers.lstyle_social_battery);
      addScore(driveScores, evidence, "autonomy", 0.8, "lstyle_social_battery", answers.lstyle_social_battery);
    }

    const planning = normalized(answers.lstyle_planning_horizon);
    if (planning === "multi-year" || planning === "yearly") addScore(modeScores, evidence, "architect", 1.2, "lstyle_planning_horizon", answers.lstyle_planning_horizon);
    if (planning === "day-to-day" || planning === "weekly") addScore(modeScores, evidence, "builder", 0.8, "lstyle_planning_horizon", answers.lstyle_planning_horizon);

    const micromanagement = scaleStrength(answers.peeve_micromanagement);
    if (micromanagement > 0) addScore(driveScores, evidence, "autonomy", micromanagement * 1.8, "peeve_micromanagement", answers.peeve_micromanagement);
  }

  function ranked(scores, order) {
    return order.map((id, index) => ({ id, score: scores[id], index }))
      .sort((a, b) => b.score - a.score || a.index - b.index);
  }

  function signatureFor(answers, primary, secondary) {
    const stable = Object.keys(answers).sort().map(key => `${key}:${answers[key] ?? ""}`).join("|");
    let hash = 2166136261;
    for (let i = 0; i < stable.length; i += 1) {
      hash ^= stable.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    const suffix = (hash >>> 0).toString(16).toUpperCase().padStart(8, "0").slice(0, 4);
    return `MX-${primary.code}-${secondary.code}-${suffix}`;
  }

  function match(answers = {}, options = {}) {
    const driveScores = emptyScores(DRIVE_ORDER);
    const modeScores = emptyScores(MODE_ORDER);
    const evidence = [];

    addExactRules(answers, driveScores, modeScores, evidence);
    addStrengthRules(answers, driveScores, evidence, CHARACTER_DRIVES, 1.35);
    addStrengthRules(answers, driveScores, evidence, VALUE_DRIVES, 1.5);
    addBigFiveRules(answers, driveScores, modeScores, evidence);
    addCognitiveRules(answers, driveScores, modeScores, evidence);

    const drives = ranked(driveScores, DRIVE_ORDER);
    const modes = ranked(modeScores, MODE_ORDER);
    const candidates = ARCHETYPES.map(archetype => ({
      ...archetype,
      rawScore: driveScores[archetype.driveId] + modeScores[archetype.modeId]
    })).sort((a, b) => b.rawScore - a.rawScore || ARCHETYPES.findIndex(item => item.id === a.id) - ARCHETYPES.findIndex(item => item.id === b.id));

    const primary = candidates[0];
    const secondary = candidates.find(item => item.id !== primary.id && (item.driveId !== primary.driveId || item.modeId !== primary.modeId)) || candidates[1];
    const maxCandidate = primary.rawScore || 1;

    const relevantAnswered = [...RULE_DIMENSIONS].filter(id => answers[id] != null && answers[id] !== "").length;
    const totalAnswered = Object.values(answers).filter(value => value != null && value !== "").length;
    const coverage = relevantAnswered / RULE_DIMENSIONS.size;
    const driveMargin = drives[0].score > 0 ? (drives[0].score - drives[1].score) / drives[0].score : 0;
    const modeMargin = modes[0].score > 0 ? (modes[0].score - modes[1].score) / modes[0].score : 0;
    const skippedGroups = Number(options.skippedGroups || 0);
    const confidence = Math.max(18, Math.min(96, Math.round(35 + coverage * 45 + (driveMargin + modeMargin) * 10 - skippedGroups * 1.5)));
    const separation = (driveMargin + modeMargin) / 2;
    primary.match = primary.rawScore > 0
      ? Math.min(98, Math.round(68 + separation * 20 + coverage * 10))
      : 50;
    const secondaryRelative = primary.rawScore > 0 ? secondary.rawScore / maxCandidate : 1;
    secondary.match = primary.rawScore > 0
      ? Math.max(40, Math.min(primary.match - 2, Math.round(42 + secondaryRelative * 38)))
      : 50;

    const topEvidence = evidence.sort((a, b) => b.points - a.points).slice(0, 12);
    const result = {
      version: "1.0",
      primary,
      secondary,
      drives,
      modes,
      confidence,
      coverage: Math.round(coverage * 100),
      relevantAnswered,
      totalAnswered,
      skippedGroups,
      evidence: topEvidence
    };
    result.signature = signatureFor(answers, primary, secondary);
    return result;
  }

  function localize(item, lang) {
    return item?.[lang] || item?.en || "";
  }

  function reportFor(result, lang = "en") {
    const primary = result.primary;
    const secondary = result.secondary;
    const drive = DRIVES[primary.driveId];
    const mode = MODES[primary.modeId];
    const secondaryDrive = DRIVES[secondary.driveId];
    const secondaryMode = MODES[secondary.modeId];
    const tr = item => localize(item, lang);
    const blendName = `${tr(secondaryDrive.adjective)}${lang === "zh" ? "" : " "}${tr(secondaryMode.name)}`;
    return {
      name: tr(primary.name),
      englishName: primary.name.en,
      code: primary.code,
      blendName,
      blendEnglishName: secondary.name.en,
      tagline: lang === "zh"
        ? `由${tr(drive.name)}驱动，以${tr(mode.name)}的方式将意图转化为行动。`
        : `Driven by ${tr(drive.name).toLowerCase()}, expressed through the ${tr(mode.name).toLowerCase()} mode.`,
      overview: `${tr(drive.essence)} ${tr(mode.essence)}`,
      strengths: [...drive.strengths.slice(0, 2).map(tr), ...mode.strengths.map(tr)],
      blindSpots: [...drive.blindSpots.map(tr), ...mode.blindSpots.slice(0, 1).map(tr)],
      work: tr(mode.work),
      relationships: tr(drive.relationships),
      underPressure: `${tr(drive.stress)} ${tr(mode.stress)}`,
      growth: `${tr(drive.growth)} ${tr(mode.growth)}`,
      aiCollaboration: `${tr(drive.ai)} ${tr(mode.ai)}`,
      blend: lang === "zh"
        ? `你的次级原型是${blendName}。这意味着在特定情境下，你会在主要的${tr(drive.name)}动机与${tr(mode.name)}方式之外，调用${tr(secondaryDrive.name)}动机和${tr(secondaryMode.name)}方式。`
        : `Your secondary archetype is the ${blendName}. In some contexts, you supplement your primary ${tr(drive.name).toLowerCase()} drive and ${tr(mode.name).toLowerCase()} mode with ${tr(secondaryDrive.name).toLowerCase()} and ${tr(secondaryMode.name).toLowerCase()} patterns.`,
      disclaimer: lang === "zh"
        ? "MatrAIx 结果用于自我反思与协作设计，不是临床诊断，也不应被用于限制个人机会。人格会随情境与经历变化。"
        : "MatrAIx is designed for reflection and collaboration, not clinical diagnosis or limiting personal opportunities. People change across contexts and over time."
    };
  }

  const MATCHING_RULES = {
    model: "highest weighted core drive × highest weighted operating mode",
    coreDrives: DRIVE_ORDER,
    operatingModes: MODE_ORDER,
    directRules: {
      values_priority: CORE_VALUE_MAP,
      decision_style: DECISION_MODE_MAP
    },
    weightedDimensionGroups: {
      character: CHARACTER_DRIVES,
      values: VALUE_DRIVES,
      bigFive: BIG_FIVE_GROUPS
    },
    tieBreak: "fixed published order for deterministic results",
    excludedFromCoreType: ["demographics", "medical/neurotype", "politics", "religion", "current emotional state", "skills and entertainment preferences"]
  };

  window.MATRAIX_ARCHETYPES = {
    version: "1.0",
    archetypes: ARCHETYPES,
    drives: DRIVES,
    modes: MODES,
    matchingRules: MATCHING_RULES,
    match,
    reportFor
  };
})();
