/**
 * Smart inference scenarios for Worldview: Beliefs.
 * Each option maps directly to canonical dimension values.
 */
window.WORLDVIEW_SMART = {
  intro: {
    en: "Pick the reactions closest to yours across tech, politics, work, and daily life. We'll infer your belief and attitude profile — not just two generic questions.",
    zh: "选择最贴近你真实反应的情境（科技、政治、工作、日常生活等），我们会推断信念与态度画像，而不只是两道泛化题。"
  },
  questions: [
    {
      id: "ai_regulation",
      text: {
        en: "A major AI product launches with little oversight. Your gut reaction:",
        zh: "一个重磅 AI 产品几乎无监管就上线了。你的第一反应："
      },
      options: [
        {
          value: "embrace",
          label: { en: "Ship fast — we'll adapt", zh: "快速上线，社会会适应" },
          example: {
            en: "\"Let builders build; regulation always lags anyway.\"",
            zh: "「让创新者去做，监管本来就跟不上。」"
          },
          maps: {
            att_ai: "Enthusiast",
            att_automation: "Enthusiast",
            att_new_technology: "Enthusiast",
            att_rapid_change: "Enthusiast",
            att_self_driving_cars: "Positive",
            att_open_source: "Positive",
            att_space_exploration: "Positive"
          }
        },
        {
          value: "cautious",
          label: { en: "Useful, but guardrails first", zh: "有用，但要先有护栏" },
          example: {
            en: "\"Excited for tools, but want audits before wide rollout.\"",
            zh: "「对工具兴奋，但大规模铺开前要有审计。」"
          },
          maps: {
            att_ai: "Positive",
            att_automation: "Positive",
            att_new_technology: "Positive",
            att_rapid_change: "Neutral",
            att_self_driving_cars: "Neutral",
            att_data_privacy: "Positive",
            att_surveillance: "Skeptical"
          }
        },
        {
          value: "skeptical",
          label: { en: "Benefits overstated", zh: "好处被夸大了" },
          example: {
            en: "\"Another hype cycle — show me durable value first.\"",
            zh: "「又是 hype 周期——先证明长期价值。」"
          },
          maps: {
            att_ai: "Skeptical",
            att_automation: "Skeptical",
            att_new_technology: "Skeptical",
            att_rapid_change: "Skeptical",
            att_self_driving_cars: "Skeptical",
            att_influencers: "Skeptical",
            att_advertising: "Skeptical"
          }
        },
        {
          value: "oppose",
          label: { en: "Slow or stop it", zh: "应放缓或叫停" },
          example: {
            en: "\"The risks to jobs and truth outweigh the upside.\"",
            zh: "「对就业和真相的风险大于收益。」"
          },
          maps: {
            att_ai: "Opposed",
            att_automation: "Opposed",
            att_new_technology: "Opposed",
            att_rapid_change: "Opposed",
            att_self_driving_cars: "Opposed",
            att_surveillance: "Opposed"
          }
        }
      ]
    },
    {
      id: "privacy_app",
      text: {
        en: "An app you rely on asks for always-on location + contacts to \"personalize.\" You:",
        zh: "常用 App 要求常开定位+通讯录来「个性化」。你会："
      },
      options: [
        {
          value: "deny",
          label: { en: "Hard no — delete or switch", zh: "坚决拒绝，删或换" },
          example: {
            en: "\"Not worth it. I'll pay or use a privacy-first alternative.\"",
            zh: "「不值得。宁可付费或用隐私优先的替代品。」"
          },
          maps: {
            att_data_privacy: "Enthusiast",
            att_privacy_vs_security: "Enthusiast",
            att_surveillance: "Opposed",
            att_social_media: "Skeptical",
            trust_level: "Skeptical",
            safety_sensitivity: "Sensitive personal"
          }
        },
        {
          value: "limited",
          label: { en: "Minimal sharing only", zh: "只给最小权限" },
          example: {
            en: "\"Maybe coarse location while using — nothing in background.\"",
            zh: "「使用时给粗略定位——不要后台常开。」"
          },
          maps: {
            att_data_privacy: "Positive",
            att_privacy_vs_security: "Positive",
            att_surveillance: "Skeptical",
            att_social_media: "Neutral",
            trust_level: "Verifying",
            att_online_reviews: "Positive"
          }
        },
        {
          value: "tradeoff",
          label: { en: "Accept if product is great", zh: "产品好就接受" },
          example: {
            en: "\"Convenience wins — I trust they'll handle data responsibly.\"",
            zh: "「便利优先——相信他们会负责任地用数据。」"
          },
          maps: {
            att_data_privacy: "Neutral",
            att_privacy_vs_security: "Neutral",
            att_surveillance: "Neutral",
            att_social_media: "Positive",
            trust_level: "Trusting",
            att_subscription_services: "Positive",
            att_brand_loyalty: "Positive"
          }
        },
        {
          value: "security_first",
          label: { en: "Fine — safety over privacy here", zh: "可以——这里安全优先于隐私" },
          example: {
            en: "\"If it reduces fraud/abuse, share what they need.\"",
            zh: "「若能减少欺诈/滥用，需要啥给啥。」"
          },
          maps: {
            att_data_privacy: "Skeptical",
            att_privacy_vs_security: "Skeptical",
            att_surveillance: "Positive",
            trust_level: "Trusting",
            att_authority: "Positive",
            safety_sensitivity: "High-stakes (medical/legal/financial)"
          }
        }
      ]
    },
    {
      id: "economy_debate",
      text: {
        en: "In a policy debate, which frame resonates most?",
        zh: "政策辩论里，哪种框架最贴近你："
      },
      options: [
        {
          value: "progressive",
          label: { en: "Stronger public safety net", zh: "更强公共保障" },
          example: {
            en: "\"UBI, unions, regulation — markets need guardrails.\"",
            zh: "「UBI、工会、监管——市场需要护栏。」"
          },
          maps: {
            political_lean: "Center-left",
            att_government_regulation: "Positive",
            att_labor_unions: "Positive",
            att_universal_basic_income: "Positive",
            att_free_markets: "Skeptical",
            att_the_gig_economy: "Skeptical",
            att_globalization: "Neutral",
            fam_political_science: "Familiar",
            acad_political_theory: "Interested"
          }
        },
        {
          value: "market",
          label: { en: "Free markets & innovation", zh: "自由市场与创新" },
          example: {
            en: "\"Cut red tape; competition and crypto experiments welcome.\"",
            zh: "「减监管；欢迎竞争和 crypto 试验。」"
          },
          maps: {
            political_lean: "Center-right",
            att_free_markets: "Enthusiast",
            att_government_regulation: "Skeptical",
            att_cryptocurrency: "Positive",
            att_labor_unions: "Skeptical",
            att_universal_basic_income: "Opposed",
            att_globalization: "Positive",
            att_globalized_supply_chains: "Positive"
          }
        },
        {
          value: "center",
          label: { en: "Case-by-case pragmatism", zh: "具体问题具体分析" },
          example: {
            en: "\"Neither ideology — show me the evidence per sector.\"",
            zh: "「不搞意识形态——分行业看证据。」"
          },
          maps: {
            political_lean: "Center",
            att_free_markets: "Neutral",
            att_government_regulation: "Neutral",
            att_labor_unions: "Neutral",
            att_universal_basic_income: "Neutral",
            att_cryptocurrency: "Neutral",
            att_globalization: "Neutral",
            fam_political_science: "Aware"
          }
        },
        {
          value: "disengaged",
          label: { en: "Politics isn't my lane", zh: "政治不是我的事" },
          example: {
            en: "\"I tune out — too noisy, little personal impact.\"",
            zh: "「不看了——太吵，对我影响小。」"
          },
          maps: {
            political_lean: "Apolitical",
            att_free_markets: "Neutral",
            att_government_regulation: "Neutral",
            att_labor_unions: "Neutral",
            fam_political_science: "None",
            acad_political_theory: "Indifferent",
            trust_level: "Verifying"
          }
        }
      ]
    },
    {
      id: "climate_city",
      text: {
        en: "Your city proposes: more transit, EV incentives, and one new nuclear plant. You:",
        zh: "城市提案：加强公交、EV 补贴、新建一座核电站。你的态度："
      },
      options: [
        {
          value: "all_in",
          label: { en: "Strong yes — act fast", zh: "强烈支持，快做" },
          example: {
            en: "\"Climate is urgent — nuclear + renewables + density.\"",
            zh: "「气候紧迫——核电+可再生+高密度。」"
          },
          maps: {
            att_climate_action: "Enthusiast",
            att_renewable_energy: "Enthusiast",
            att_nuclear_energy: "Positive",
            att_electric_vehicles: "Enthusiast",
            att_public_transit: "Enthusiast",
            att_urban_density: "Positive"
          }
        },
        {
          value: "renewables_only",
          label: { en: "Renewables/transit yes, nuclear no", zh: "支持可再生/公交，反对核电" },
          example: {
            en: "\"Solar/wind + buses — skip nuclear risk.\"",
            zh: "「太阳能/风+公交——别冒核电风险。」"
          },
          maps: {
            att_climate_action: "Positive",
            att_renewable_energy: "Enthusiast",
            att_nuclear_energy: "Opposed",
            att_electric_vehicles: "Positive",
            att_public_transit: "Positive",
            dospert_health_safety_risk_tolerance: "Low"
          }
        },
        {
          value: "skeptic",
          label: { en: "Costs too high / unconvinced", zh: "成本太高/未被说服" },
          example: {
            en: "\"Show me bills first — not sold on urgency.\"",
            zh: "「先看账单—— urgency 没说服我。」"
          },
          maps: {
            att_climate_action: "Skeptical",
            att_renewable_energy: "Neutral",
            att_nuclear_energy: "Skeptical",
            att_electric_vehicles: "Neutral",
            att_public_transit: "Neutral",
            att_urban_density: "Neutral"
          }
        },
        {
          value: "oppose",
          label: { en: "Keep car-centric status quo", zh: "维持汽车导向现状" },
          example: {
            en: "\"Don't mess with my commute or energy choice.\"",
            zh: "「别动我的通勤和能源选择。」"
          },
          maps: {
            att_climate_action: "Opposed",
            att_renewable_energy: "Skeptical",
            att_nuclear_energy: "Opposed",
            att_electric_vehicles: "Opposed",
            att_public_transit: "Opposed",
            att_urban_density: "Skeptical"
          }
        }
      ]
    },
    {
      id: "health_trust",
      text: {
        en: "A close friend skips vaccines and relies on alternative medicine. You:",
        zh: "好友不打疫苗、靠替代医学。你会："
      },
      options: [
        {
          value: "science",
          label: { en: "Push evidence-based care", zh: "强调循证医疗" },
          example: {
            en: "\"I love you, but please talk to a real clinician.\"",
            zh: "「关心你，但请找真正的临床医生。」"
          },
          maps: {
            att_vaccines: "Enthusiast",
            att_genetic_engineering: "Positive",
            att_alternative_medicine: "Opposed",
            dospert_health_safety_risk_tolerance: "Low",
            safety_sensitivity: "High-stakes (medical/legal/financial)",
            mft_care_harm: "Very high"
          }
        },
        {
          value: "mixed",
          label: { en: "Open to both worlds", zh: "两者都可接受" },
          example: {
            en: "\"Mainstream + acupuncture if it helps — their call.\"",
            zh: "「主流+针灸若有帮助——他们自选。」"
          },
          maps: {
            att_vaccines: "Positive",
            att_genetic_engineering: "Neutral",
            att_alternative_medicine: "Positive",
            dospert_health_safety_risk_tolerance: "Average",
            safety_sensitivity: "Sensitive personal"
          }
        },
        {
          value: "skeptical_mainstream",
          label: { en: "Skeptical of pharma too", zh: "对主流医药也怀疑" },
          example: {
            en: "\"Big Pharma profit motives — I get why they opt out.\"",
            zh: "「大 pharma 逐利——理解他们为何 opt out。」"
          },
          maps: {
            att_vaccines: "Skeptical",
            att_genetic_engineering: "Skeptical",
            att_alternative_medicine: "Positive",
            trust_level: "Skeptical",
            dospert_health_safety_risk_tolerance: "Average"
          }
        },
        {
          value: "live_and_let",
          label: { en: "Not my body — stay out", zh: "身体是他们的事" },
          example: {
            en: "\"Personal freedom beats my opinion on medicine.\"",
            zh: "「个人自由高于我对医学的意见。」"
          },
          maps: {
            att_vaccines: "Neutral",
            att_alternative_medicine: "Neutral",
            att_free_speech: "Positive",
            mft_liberty_oppression: "High",
            mft_authority_subversion: "Low"
          }
        }
      ]
    },
    {
      id: "faith_holiday",
      text: {
        en: "At a family gathering with strong religious traditions, you:",
        zh: "家庭聚会宗教传统很强时，你通常："
      },
      options: [
        {
          value: "devout",
          label: { en: "Participate fully", zh: "全情参与" },
          example: {
            en: "\"Tradition grounds me — I want my kids in it too.\"",
            zh: "「传统给我根基——也希望孩子参与。」"
          },
          maps: {
            att_organized_religion: "Enthusiast",
            topic_spirituality: "Passionate",
            fam_religious_studies: "Proficient",
            mft_sanctity_degradation: "High",
            mft_authority_subversion: "High",
            mft_loyalty_betrayal: "High"
          }
        },
        {
          value: "respectful",
          label: { en: "Show up, keep personal beliefs private", zh: "出席，但信念私下持有" },
          example: {
            en: "\"I'll pray at the table out of respect, not conviction.\"",
            zh: "「桌上会配合仪式，出于尊重而非信仰。」"
          },
          maps: {
            att_organized_religion: "Neutral",
            topic_spirituality: "Interested",
            fam_religious_studies: "Aware",
            mft_loyalty_betrayal: "High",
            mft_sanctity_degradation: "Average"
          }
        },
        {
          value: "spiritual_not_religious",
          label: { en: "Spiritual, not institutional", zh: "有灵性，不依附机构" },
          example: {
            en: "\"Meditation yes, organized religion not for me.\"",
            zh: "「冥想可以，组织化宗教不适合我。」"
          },
          maps: {
            att_organized_religion: "Skeptical",
            topic_spirituality: "Passionate",
            fam_religious_studies: "Familiar",
            mft_sanctity_degradation: "Average",
            mft_liberty_oppression: "High"
          }
        },
        {
          value: "secular",
          label: { en: "Secular — minimize participation", zh: "世俗——尽量不参与" },
          example: {
            en: "\"I'll visit family, skip the ritual parts.\"",
            zh: "「会探亲，仪式部分能免则免。」"
          },
          maps: {
            att_organized_religion: "Opposed",
            topic_spirituality: "Indifferent",
            fam_religious_studies: "None",
            mft_sanctity_degradation: "Low",
            mft_authority_subversion: "Low"
          }
        }
      ]
    },
    {
      id: "work_model",
      text: {
        en: "Your employer picks a permanent work model. You prefer:",
        zh: "公司定下长期工作模式，你更偏好："
      },
      options: [
        {
          value: "remote",
          label: { en: "Remote-first", zh: "远程优先" },
          example: {
            en: "\"Office is optional — optimize for focus and life.\"",
            zh: "「办公室可选——专注与生活优先。」"
          },
          maps: {
            att_remote_work: "Enthusiast",
            att_working_from_office: "Opposed",
            att_four_day_work_week: "Enthusiast",
            att_performance_reviews: "Skeptical"
          }
        },
        {
          value: "hybrid",
          label: { en: "Hybrid with flexibility", zh: "灵活混合" },
          example: {
            en: "\"2–3 days in for collaboration, rest at home.\"",
            zh: "「每周 2–3 天协作，其余在家。」"
          },
          maps: {
            att_remote_work: "Positive",
            att_working_from_office: "Positive",
            att_four_day_work_week: "Positive",
            att_performance_reviews: "Neutral"
          }
        },
        {
          value: "office",
          label: { en: "In-office culture", zh: "办公室文化" },
          example: {
            en: "\"Best work happens shoulder-to-shoulder.\"",
            zh: "「肩并肩才能做出最好工作。」"
          },
          maps: {
            att_remote_work: "Skeptical",
            att_working_from_office: "Enthusiast",
            att_four_day_work_week: "Skeptical",
            att_performance_reviews: "Positive"
          }
        },
        {
          value: "education_focus",
          label: { en: "Doesn't matter — invest in learning", zh: "无所谓——更在意学习成长" },
          example: {
            en: "\"Whatever model — fund tuition and kill pointless tests.\"",
            zh: "「模式都行——投教育、少搞无意义考试。」"
          },
          maps: {
            att_remote_work: "Neutral",
            att_higher_education: "Enthusiast",
            att_standardized_testing: "Opposed",
            acad_political_theory: "Interested",
            fam_political_science: "Familiar"
          }
        }
      ]
    },
    {
      id: "consumer_habits",
      text: {
        en: "Your shopping / media habits are closest to:",
        zh: "你的消费/媒体习惯更像："
      },
      options: [
        {
          value: "minimal",
          label: { en: "Minimal & ethical", zh: "极简且重伦理" },
          example: {
            en: "\"Few items, secondhand, skip influencers and fast fashion.\"",
            zh: "「少买、二手、不看网红/fast fashion。」"
          },
          maps: {
            att_minimalism: "Enthusiast",
            att_consumerism: "Opposed",
            att_fast_fashion: "Opposed",
            att_advertising: "Skeptical",
            att_influencers: "Opposed",
            att_veganism: "Positive",
            att_brand_loyalty: "Skeptical",
            att_subscription_services: "Skeptical"
          }
        },
        {
          value: "deal_hunter",
          label: { en: "Deal hunter — reviews & subs", zh: "薅羊毛——看评测和订阅" },
          example: {
            en: "\"Compare reviews, stack subscriptions if they're worth it.\"",
            zh: "「比评测，值得就叠订阅。」"
          },
          maps: {
            att_minimalism: "Neutral",
            att_consumerism: "Neutral",
            att_online_reviews: "Enthusiast",
            att_subscription_services: "Positive",
            att_brand_loyalty: "Neutral",
            att_advertising: "Neutral",
            att_influencers: "Neutral",
            att_tipping_culture: "Positive"
          }
        },
        {
          value: "brand_fan",
          label: { en: "Brand loyal / influencer-led", zh: "品牌粉/跟网红买" },
          example: {
            en: "\"If my favorite creator promotes it, I'll try it.\"",
            zh: "「喜欢的博主推了就会试。」"
          },
          maps: {
            att_consumerism: "Positive",
            att_brand_loyalty: "Enthusiast",
            att_influencers: "Enthusiast",
            att_advertising: "Positive",
            att_fast_fashion: "Positive",
            att_online_reviews: "Positive",
            att_minimalism: "Skeptical"
          }
        },
        {
          value: "indifferent",
          label: { en: "Buy when needed — no strong view", zh: "需要才买——无强烈偏好" },
          example: {
            en: "\"Not thinking about consumerism debates day to day.\"",
            zh: "「日常不太想消费主义辩论。」"
          },
          maps: {
            att_minimalism: "Neutral",
            att_consumerism: "Neutral",
            att_fast_fashion: "Neutral",
            att_advertising: "Neutral",
            att_influencers: "Neutral",
            att_veganism: "Neutral",
            att_tipping_culture: "Neutral"
          }
        }
      ]
    },
    {
      id: "neighborhood_change",
      text: {
        en: "Your neighborhood gets new condos, cafes, and rising rents. You feel:",
        zh: "社区新建公寓、咖啡馆、租金上涨。你的感受："
      },
      options: [
        {
          value: "pro_growth",
          label: { en: "Good — vitality & investment", zh: "好事——活力与投资" },
          example: {
            en: "\"More services, safer streets — change happens.\"",
            zh: "「更多服务、更安全——变化难免。」"
          },
          maps: {
            att_gentrification: "Positive",
            att_urban_density: "Enthusiast",
            att_homeownership: "Positive",
            att_public_transit: "Positive"
          }
        },
        {
          value: "mixed",
          label: { en: "Mixed — winners and losers", zh: "复杂——有人受益有人受损" },
          example: {
            en: "\"Nice cafes, but neighbors priced out — uneasy.\"",
            zh: "「咖啡馆不错，但老邻居被挤走——不安。」"
          },
          maps: {
            att_gentrification: "Neutral",
            att_urban_density: "Neutral",
            att_homeownership: "Neutral",
            att_public_transit: "Positive"
          }
        },
        {
          value: "anti",
          label: { en: "Harmful — protect existing residents", zh: "有害——应保护原住民" },
          example: {
            en: "\"Gentrification destroys community — resist it.\"",
            zh: "「中产阶层化破坏社区——应抵抗。」"
          },
          maps: {
            att_gentrification: "Opposed",
            att_urban_density: "Skeptical",
            att_homeownership: "Positive",
            mft_fairness_cheating: "High"
          }
        },
        {
          value: "suburban",
          label: { en: "I'd leave for more space", zh: "我会搬去空间更大的地方" },
          example: {
            en: "\"Density isn't for me — house and yard if I can.\"",
            zh: "「高密度不适合我——能买就买房带院子。」"
          },
          maps: {
            att_gentrification: "Skeptical",
            att_urban_density: "Opposed",
            att_homeownership: "Enthusiast",
            att_public_transit: "Skeptical"
          }
        }
      ]
    },
    {
      id: "rights_debate",
      text: {
        en: "A heated public debate: speech vs harm, guns, and punishment. You lean:",
        zh: "公开辩论：言论 vs 伤害、枪支、刑罚。你更倾向："
      },
      options: [
        {
          value: "liberty",
          label: { en: "Maximize individual liberty", zh: "最大化个人自由" },
          example: {
            en: "\"Even offensive speech stays legal; gun rights matter.\"",
            zh: "「冒犯性言论也合法；持枪权重要。」"
          },
          maps: {
            att_free_speech: "Enthusiast",
            att_gun_ownership: "Positive",
            att_capital_punishment: "Opposed",
            mft_liberty_oppression: "Very high",
            mft_authority_subversion: "Low"
          }
        },
        {
          value: "security",
          label: { en: "Safety & order first", zh: "安全与秩序优先" },
          example: {
            en: "\"Restrict dangerous speech/weapons; strong penalties deter crime.\"",
            zh: "「限制危险言论/武器；重刑震慑犯罪。」"
          },
          maps: {
            att_free_speech: "Skeptical",
            att_gun_ownership: "Opposed",
            att_capital_punishment: "Positive",
            mft_care_harm: "Very high",
            mft_authority_subversion: "High",
            safety_sensitivity: "Potentially harmful"
          }
        },
        {
          value: "balanced",
          label: { en: "Balance — context matters", zh: "平衡——看情境" },
          example: {
            en: "\"Protect speech in public square, limit incitement and assault weapons.\"",
            zh: "「公共广场保护言论，限制煽动和攻击性武器。」"
          },
          maps: {
            att_free_speech: "Positive",
            att_gun_ownership: "Neutral",
            att_capital_punishment: "Neutral",
            mft_fairness_cheating: "High",
            mft_care_harm: "High"
          }
        },
        {
          value: "institutions",
          label: { en: "Trust courts & experts to decide", zh: "信任法院与专家裁决" },
          example: {
            en: "\"Not my job to litigate — defer to institutions.\"",
            zh: "「不该我来断案——交给机构。」"
          },
          maps: {
            att_free_speech: "Neutral",
            att_authority: "Positive",
            trust_level: "Trusting",
            att_capital_punishment: "Neutral",
            mft_loyalty_betrayal: "Average"
          }
        }
      ]
    },
    {
      id: "money_risk",
      text: {
        en: "You get a bonus. Your instinct:",
        zh: "拿到一笔奖金，你的本能反应："
      },
      options: [
        {
          value: "invest",
          label: { en: "Invest / crypto / startup bet", zh: "投资/crypto/创业赌一把" },
          example: {
            en: "\"Higher risk for higher upside — YOLO a slice.\"",
            zh: "「高风险高回报——拿一部分 YOLO。」"
          },
          maps: {
            att_risk_taking: "Enthusiast",
            att_taking_on_debt: "Positive",
            att_cryptocurrency: "Positive",
            att_homeownership: "Neutral",
            dospert_health_safety_risk_tolerance: "High"
          }
        },
        {
          value: "save",
          label: { en: "Save & pay down debt", zh: "储蓄并还债" },
          example: {
            en: "\"Emergency fund first — debt is stress I don't need.\"",
            zh: "「先应急金——债务是多余压力。」"
          },
          maps: {
            att_risk_taking: "Skeptical",
            att_taking_on_debt: "Opposed",
            att_cryptocurrency: "Skeptical",
            att_homeownership: "Positive",
            dospert_health_safety_risk_tolerance: "Low"
          }
        },
        {
          value: "balance",
          label: { en: "Split — some fun, some safe", zh: "分配——一点享乐一点安全" },
          example: {
            en: "\"Index fund + vacation — nothing extreme.\"",
            zh: "「指数基金+旅行——不走极端。」"
          },
          maps: {
            att_risk_taking: "Neutral",
            att_taking_on_debt: "Neutral",
            att_cryptocurrency: "Neutral",
            att_homeownership: "Neutral",
            dospert_health_safety_risk_tolerance: "Average"
          }
        },
        {
          value: "spend",
          label: { en: "Spend — life is short", zh: "花了——人生苦短" },
          example: {
            en: "\"Experiences now; I'll figure out housing later.\"",
            zh: "「体验优先；房子以后再说。」"
          },
          maps: {
            att_risk_taking: "Positive",
            att_taking_on_debt: "Positive",
            att_consumerism: "Positive",
            att_homeownership: "Skeptical",
            dospert_health_safety_risk_tolerance: "Average"
          }
        }
      ]
    },
    {
      id: "loyalty_dilemma",
      text: {
        en: "Your team is accused of cheating; you know part of it is true. You:",
        zh: "团队被指控作弊，你知道有一部分属实。你会："
      },
      options: [
        {
          value: "whistleblow",
          label: { en: "Report it — fairness over loyalty", zh: "举报——公平高于忠诚" },
          example: {
            en: "\"I'll take the heat — cheating erodes everything.\"",
            zh: "「宁可得罪人——作弊腐蚀一切。」"
          },
          maps: {
            mft_fairness_cheating: "Very high",
            mft_loyalty_betrayal: "Low",
            mft_care_harm: "High",
            trust_level: "Verifying",
            att_authority: "Neutral"
          }
        },
        {
          value: "loyal",
          label: { en: "Stand with the team publicly", zh: "公开站在团队一边" },
          example: {
            en: "\"Handle it inside — outsiders don't get the full story.\"",
            zh: "「内部处理——外人不知全貌。」"
          },
          maps: {
            mft_loyalty_betrayal: "Very high",
            mft_authority_subversion: "High",
            mft_fairness_cheating: "Low",
            trust_level: "Trusting"
          }
        },
        {
          value: "fix_quietly",
          label: { en: "Fix quietly, no scandal", zh: "悄悄纠正，不闹大" },
          example: {
            en: "\"Make it right offline — minimize damage to everyone.\"",
            zh: "「线下纠正——尽量减少伤害。」"
          },
          maps: {
            mft_fairness_cheating: "High",
            mft_loyalty_betrayal: "High",
            mft_care_harm: "High",
            trust_level: "Verifying"
          }
        },
        {
          value: "hostile_outsider",
          label: { en: "Distrust the accusers entirely", zh: "完全不信指控方" },
          example: {
            en: "\"Pile-on culture — assume bad faith until proven.\"",
            zh: "「跟风文化——默认恶意除非证伪。」"
          },
          maps: {
            mft_loyalty_betrayal: "High",
            trust_level: "Hostile",
            att_authority: "Skeptical",
            att_social_media: "Skeptical"
          }
        }
      ]
    }
  ]
};

window.SKIP_GROUP_HINTS = {
  ...(window.SKIP_GROUP_HINTS || {}),
  "Worldview: Beliefs": {
    en: "Not sure about belief questions? Skip for neutral defaults, or answer the scenarios above.",
    zh: "不确定信念类问题？可跳过使用默认值，或先回答上方情境题。"
  }
};
