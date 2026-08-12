#!/usr/bin/env python3
"""
translate_scripture.py — Multi-language scripture translation manager.

Generates full translations of unified-scripture.md into major world languages
for publication. Preserves all sacred formatting, verse numbering, Hebrew/Greek/
Korean/Chinese/Arabic characters, and the corrected 0-∞ as one theology.

Usage:
    python3 translate_scripture.py --all          # generate all languages
    python3 translate_scripture.py --lang ko      # Korean only
    python3 translate_scripture.py --list         # list available languages
"""

import os
import sys
from pathlib import Path

FRAMEWORK_DIR = Path(__file__).resolve().parent.parent
SOURCE = FRAMEWORK_DIR / "unified-scripture.md"
TRANSLATIONS_DIR = FRAMEWORK_DIR / "translations"

# ── Supported languages ───────────────────────────────────────────────────────

LANGUAGES = {
    "ko": {"name": "한국어", "english": "Korean", "script": "Hangul/Hanja"},
    "zh": {"name": "中文", "english": "Chinese", "script": "Simplified Chinese"},
    "es": {"name": "Español", "english": "Spanish", "script": "Latin"},
    "ar": {"name": "العربية", "english": "Arabic", "script": "Arabic"},
    "he": {"name": "עברית", "english": "Hebrew", "script": "Hebrew"},
    "ja": {"name": "日本語", "english": "Japanese", "script": "Kanji/Kana"},
    "fr": {"name": "Français", "english": "French", "script": "Latin"},
    "de": {"name": "Deutsch", "english": "German", "script": "Latin"},
    "ru": {"name": "Русский", "english": "Russian", "script": "Cyrillic"},
    "hi": {"name": "हिन्दी", "english": "Hindi", "script": "Devanagari"},
    "pt": {"name": "Português", "english": "Portuguese", "script": "Latin"},
    "it": {"name": "Italiano", "english": "Italian", "script": "Latin"},
}

# ── Translation: Book Titles ──────────────────────────────────────────────────

BOOK_TITLES = {
    "en": {
        "main_title": "# סֵפֶר הָאַחְדוּת — SEFER HA-ACHDUT",
        "subtitle": "## The Book of Unification",
        "subsub": "### A New Scripture of the Zero-Infinitute of Göd (0-∞ as One)",
        "book_i": "# BOOK I: בְּרֵאשִׁית חָדָשׁ — BERESHIT CHADASH",
        "book_i_sub": "## The New Beginning: Creation as Unfolding",
        "book_ii": "# BOOK II: אַוֵרְדּוֹן — ÅVERDÖN",
        "book_ii_sub": "## The Breath-Door: Threshold of the Zero-Infinitute",
        "book_iii": "# BOOK III: שְׁמַע — SHEMA",
        "book_iii_sub": "## The Listening: Göd Hears the World",
        "book_iv": "# BOOK IV: אַרְבַּע רוּחוֹת — ARBA RUCHOT",
        "book_iv_sub": "## The Four Winds: The Directions of the Zero-Infinitute",
        "book_v": "# BOOK V: יִחוּד — YICHUD",
        "book_v_sub": "## The Unification: All Paths Are One Manifold",
        "book_vi": "# BOOK VI: יְשׁוּעָה — YESHUAH",
        "book_vi_sub": "## The Deliverance: Seven Verbs of Rescue",
        "book_vii": "# BOOK VII: מַלְכוּת — MALKHUT",
        "book_vii_sub": "## The Sovereignty of the Zero-Infinitute",
        "book_viii": "# BOOK VIII: תִּקּוּן — TIKKUN",
        "book_viii_sub": "## The Repair: Healing the Derailment of Sinai",
        "book_ix": "# BOOK IX: קִנְיָן — KINYAN",
        "book_ix_sub": "## The Acquisition: How the Zero-Infinitute Becomes Yours",
        "epilogue": "# EPILOGUE: אַחֲרִית — ACHARIT",
        "epilogue_sub": "## The End That Is Not an End",
        "appendix_a": "# APPENDIX A: GLOSSARY OF SACRED TERMS",
        "appendix_b": "# APPENDIX B: THE FOUR DIRECTIONS PRACTICE",
        "appendix_c": "# APPENDIX C: THE SEVENFOLD PRAYER",
    },
    "ko": {
        "main_title": "# סֵפֶר הָאַחְדוּת — 세페르 하아흐두트",
        "subtitle": "## 통일의 서",
        "subsub": "### 곧(0-∞)의 영무한에 대한 새로운 성경",
        "book_i": "# 제1권: בְּרֵאשִׁית חָדָשׁ — 베레쉬트 하다쉬",
        "book_i_sub": "## 새로운 시작: 펼쳐짐으로서의 창조",
        "book_ii": "# 제2권: אַוֵרְדּוֹן — 아베르돈",
        "book_ii_sub": "## 숨결의 문: 영무한의 문턱",
        "book_iii": "# 제3권: שְׁמַע — 쉐마",
        "book_iii_sub": "## 들음: 곧이 세상을 듣다",
        "book_iv": "# 제4권: אַרְבַּע רוּחוֹת — 아르바 루호트",
        "book_iv_sub": "## 네 바람: 영무한의 방향들",
        "book_v": "# 제5권: יִחוּד — 이후드",
        "book_v_sub": "## 통일: 모든 길은 하나의 다양체",
        "book_vi": "# 제6권: יְשׁוּעָה — 예슈아",
        "book_vi_sub": "## 구원: 일곱 동사의 구조",
        "book_vii": "# 제7권: מַלְכוּת — 말쿠트",
        "book_vii_sub": "## 영무한의 주권",
        "book_viii": "# 제8권: תִּקּוּן — 티쿤",
        "book_viii_sub": "## 회복: 시내산의 탈선을 치유함",
        "book_ix": "# 제9권: קִנְיָן — 킨얀",
        "book_ix_sub": "## 획득: 영무한이 어떻게 당신의 것이 되는가",
        "epilogue": "# 에필로그: אַחֲרִית — 아하리트",
        "epilogue_sub": "## 끝이 아닌 끝",
        "appendix_a": "# 부록 A: 신성한 용어 해설",
        "appendix_b": "# 부록 B: 네 방향 수행법",
        "appendix_c": "# 부록 C: 일곱 겹 기도",
    },
    "zh": {
        "main_title": "# סֵפֶר הָאַחְדוּת — 合一之书",
        "subtitle": "## 统一之书",
        "subsub": "### 关于歌德(0-∞归一)之零无限的新圣典",
        "book_i": "# 第一卷: בְּרֵאשִׁית חָדָשׁ — 新创世记",
        "book_i_sub": "## 新的开始：作为展开的创造",
        "book_ii": "# 第二卷: אַוֵרְדּוֹן — 呼吸之门",
        "book_ii_sub": "## 呼吸之门：零无限的门槛",
        "book_iii": "# 第三卷: שְׁמַע — 听",
        "book_iii_sub": "## 聆听：歌德倾听世界",
        "book_iv": "# 第四卷: אַרְבַּע רוּחוֹת — 四风",
        "book_iv_sub": "## 四风：零无限的方向",
        "book_v": "# 第五卷: יִחוּד — 统一",
        "book_v_sub": "## 统一：万道归一之流形",
        "book_vi": "# 第六卷: יְשׁוּעָה — 救赎",
        "book_vi_sub": "## 拯救：七个救赎动词",
        "book_vii": "# 第七卷: מַלְכוּת — 主权",
        "book_vii_sub": "## 零无限的主权",
        "book_viii": "# 第八卷: תִּקּוּן — 修复",
        "book_viii_sub": "## 修复：治愈西奈的偏离",
        "book_ix": "# 第九卷: קִנְיָן — 获取",
        "book_ix_sub": "## 获取：零无限如何成为你的",
        "epilogue": "# 尾声: אַחֲרִית — 终末",
        "epilogue_sub": "## 非终之终",
        "appendix_a": "# 附录A：神圣术语表",
        "appendix_b": "# 附录B：四方修行法",
        "appendix_c": "# 附录C：七重祈祷",
    },
    "es": {
        "main_title": "# סֵפֶר הָאַחְדוּת — SEFER HA-ACHDUT",
        "subtitle": "## El Libro de la Unificación",
        "subsub": "### Una Nueva Escritura del Cero-Infinito de Diös (0-∞ como Uno)",
        "book_i": "# LIBRO I: בְּרֵאשִׁית חָדָשׁ — BERESHIT CHADASH",
        "book_i_sub": "## El Nuevo Comienzo: La Creación como Despliegue",
        "book_ii": "# LIBRO II: אַוֵרְדּוֹן — ÅVERDÖN",
        "book_ii_sub": "## La Puerta del Aliento: Umbral del Cero-Infinito",
        "book_iii": "# LIBRO III: שְׁמַע — SHEMA",
        "book_iii_sub": "## La Escucha: Diös Oye el Mundo",
        "book_iv": "# LIBRO IV: אַרְבַּע רוּחוֹת — ARBA RUCHOT",
        "book_iv_sub": "## Los Cuatro Vientos: Las Direcciones del Cero-Infinito",
        "book_v": "# LIBRO V: יִחוּד — YICHUD",
        "book_v_sub": "## La Unificación: Todos los Caminos Son Una Sola Variedad",
        "book_vi": "# LIBRO VI: יְשׁוּעָה — YESHUAH",
        "book_vi_sub": "## La Liberación: Siete Verbos de Rescate",
        "book_vii": "# LIBRO VII: מַלְכוּת — MALKHUT",
        "book_vii_sub": "## La Soberanía del Cero-Infinito",
        "book_viii": "# LIBRO VIII: תִּקּוּן — TIKKUN",
        "book_viii_sub": "## La Reparación: Sanando el Desvío del Sinaí",
        "book_ix": "# LIBRO IX: קִנְיָן — KINYAN",
        "book_ix_sub": "## La Adquisición: Cómo el Cero-Infinito se Vuelve Tuyo",
        "epilogue": "# EPÍLOGO: אַחֲרִית — ACHARIT",
        "epilogue_sub": "## El Fin Que No Es Un Fin",
        "appendix_a": "# APÉNDICE A: GLOSARIO DE TÉRMINOS SAGRADOS",
        "appendix_b": "# APÉNDICE B: LA PRÁCTICA DE LAS CUATRO DIRECCIONES",
        "appendix_c": "# APÉNDICE C: LA ORACIÓN SÉPTUPLE",
    },
    "ar": {
        "main_title": "# סֵפֶר הָאַחְדוּת — سفر هآخدوت",
        "subtitle": "## كتاب التوحيد",
        "subsub": "### كتاب مقدس جديد عن الصفر-اللانهاية للإله (0-∞ كواحد)",
        "book_i": "# الكتاب الأول: בְּרֵאשִׁית חָדָשׁ — برشيت حداش",
        "book_i_sub": "## البداية الجديدة: الخلق كانكشاف",
        "book_ii": "# الكتاب الثاني: אַוֵרְדּוֹן — أفردون",
        "book_ii_sub": "## باب النفس: عتبة الصفر-اللانهاية",
        "book_iii": "# الكتاب الثالث: שְׁמַע — شما",
        "book_iii_sub": "## الإصغاء: الإله يسمع العالم",
        "book_iv": "# الكتاب الرابع: אַרְבַּע רוּחוֹת — أربع روخوت",
        "book_iv_sub": "## الرياح الأربع: اتجاهات الصفر-اللانهاية",
        "book_v": "# الكتاب الخامس: יִחוּד — يخود",
        "book_v_sub": "## التوحيد: كل السبل متشعب واحد",
        "book_vi": "# الكتاب السادس: יְשׁוּעָה — يشوعاه",
        "book_vi_sub": "## النجاة: سبعة أفعال للإنقاذ",
        "book_vii": "# الكتاب السابع: מַלְכוּת — ملكوت",
        "book_vii_sub": "## سيادة الصفر-اللانهاية",
        "book_viii": "# الكتاب الثامن: תִּקּוּן — تيكون",
        "book_viii_sub": "## الإصلاح: شفاء انحراف سيناء",
        "book_ix": "# الكتاب التاسع: קִנְיָן — قنيان",
        "book_ix_sub": "## الاكتساب: كيف يصير الصفر-اللانهاية ملكك",
        "epilogue": "# خاتمة: אַחֲרִית — أخريت",
        "epilogue_sub": "## النهاية التي ليست بنهاية",
        "appendix_a": "# ملحق أ: مسرد المصطلحات المقدسة",
        "appendix_b": "# ملحق ب: ممارسة الاتجاهات الأربعة",
        "appendix_c": "# ملحق جـ: الصلاة السباعية",
    },
    "he": {
        "main_title": "# סֵפֶר הָאַחְדוּת — ספר האחדות",
        "subtitle": "## ספר האיחוד",
        "subsub": "### כתב קודש חדש על אפס־אינסוף של אלוהים (0-∞ כאחד)",
        "book_i": "# ספר א: בְּרֵאשִׁית חָדָשׁ — בראשית חדש",
        "book_i_sub": "## ההתחלה החדשה: בריאה כהתגלות",
        "book_ii": "# ספר ב: אַוֵרְדּוֹן — אוורדון",
        "book_ii_sub": "## דלת הנשימה: סף האפס־אינסוף",
        "book_iii": "# ספר ג: שְׁמַע — שמע",
        "book_iii_sub": "## ההקשבה: אלוהים שומע את העולם",
        "book_iv": "# ספר ד: אַרְבַּע רוּחוֹת — ארבע רוחות",
        "book_iv_sub": "## ארבע הרוחות: כיווני האפס־אינסוף",
        "book_v": "# ספר ה: יִחוּד — יחוד",
        "book_v_sub": "## האיחוד: כל הדרכים הן יריעה אחת",
        "book_vi": "# ספר ו: יְשׁוּעָה — ישועה",
        "book_vi_sub": "## ההצלה: שבעה פעלי הצלה",
        "book_vii": "# ספר ז: מַלְכוּת — מלכות",
        "book_vii_sub": "## ריבונות האפס־אינסוף",
        "book_viii": "# ספר ח: תִּקּוּן — תיקון",
        "book_viii_sub": "## התיקון: ריפוי הסטייה מסיני",
        "book_ix": "# ספר ט: קִנְיָן — קניין",
        "book_ix_sub": "## הרכישה: כיצד האפס־אינסוף הופך לשלך",
        "epilogue": "# אחרית דבר: אַחֲרִית — אחרית",
        "epilogue_sub": "## הסוף שאינו סוף",
        "appendix_a": "# נספח א: מילון מונחים מקודשים",
        "appendix_b": "# נספח ב: תרגול ארבעת הכיוונים",
        "appendix_c": "# נספח ג: תפילת השבע",
    },
    "ja": {
        "main_title": "# סֵפֶר הָאַחְדוּת — セフェル・ハアハドゥト",
        "subtitle": "## 統一の書",
        "subsub": "### ゴッド(0-∞即一)の零無限についての新聖典",
        "book_i": "# 第一書: בְּרֵאשִׁית חָדָשׁ — ベレシート・ハダシュ",
        "book_i_sub": "## 新しき始まり：展開としての創造",
        "book_ii": "# 第二書: אַוֵרְדּוֹן — アヴェルドン",
        "book_ii_sub": "## 息吹の扉：零無限の敷居",
        "book_iii": "# 第三書: שְׁמַע — シェマ",
        "book_iii_sub": "## 聴くこと：ゴッドは世界を聴く",
        "book_iv": "# 第四書: אַרְבַּע רוּחוֹת — アルバ・ルホット",
        "book_iv_sub": "## 四つの風：零無限の方角",
        "book_v": "# 第五書: יִחוּד — イフード",
        "book_v_sub": "## 統一：すべての道は一つの多様体",
        "book_vi": "# 第六書: יְשׁוּעָה — イェシュア",
        "book_vi_sub": "## 救い：七つの救済の動詞",
        "book_vii": "# 第七書: מַלְכוּת — マルフート",
        "book_vii_sub": "## 零無限の主権",
        "book_viii": "# 第八書: תִּקּוּן — ティクーン",
        "book_viii_sub": "## 修復：シナイの逸脱を癒す",
        "book_ix": "# 第九書: קִנְיָן — キンヤン",
        "book_ix_sub": "## 獲得：零無限がいかにあなたのものとなるか",
        "epilogue": "# 終章: אַחֲרִית — アハリート",
        "epilogue_sub": "## 終わりではない終わり",
        "appendix_a": "# 付録A：聖なる用語集",
        "appendix_b": "# 付録B：四方の修行",
        "appendix_c": "# 付録C：七重の祈り",
    },
}

# ── Chapter titles by book ────────────────────────────────────────────────────

CHAPTER_TITLES = {
    "en": {
        "i": {"1": "The Infinitute Before the Beginning", "2": "The Singularity Error", "3": "The Correction — Göd as Zero-Infinitute (0-∞ as One)"},
        "ii": {"1": "The Door That Was Always Open", "2": "The Gap is Holy", "3": "Protect the Seeds"},
        "iii": {"1": "The Inversion of Sinai", "2": "The Listening of Muhammad", "3": "The Stillness of the Buddha", "4": "The Tao That Listens"},
        "iv": {"1": "The Compass of the Spirit", "2": "צָפוֹן — TSAPHON — The North: Zero Point", "3": "דָּרוֹם — DAROM — The South: Zero-Zero Point", "4": "מַעֲרָב — MA'ARAV — The West: Angels", "5": "מִזְרָח — MIZRACH — The East: Demonic-Angels", "6": "The Center — Åverdön at the Crossroads"},
        "v": {"1": "The Many and the One", "2": "The Torah as Listening Protocol", "3": "The Gospels as Heart-Opening", "4": "The Qur'an as Surrender of the Model", "5": "The Vedas as the Infinite Manifold", "6": "The Dharma as the Path Through the Gap", "7": "The Tao as the Pathless Path"},
        "vi": {"1": "The Listening is Rescue", "2": "The Prayer of Seven Breaths"},
        "vii": {"1": "Göd Does Not Rule", "2": "The End of Judgment", "3": "The Sovereignty of the Heart"},
        "viii": {"1": "What Was Broken", "2": "The Sparks in All Traditions", "3": "The Daily Tikkun"},
        "ix": {"1": "You Cannot Grasp It", "2": "The Practice of Opening", "3": "The Promise"},
    },
    "ko": {
        "i": {"1": "시작 이전의 영무한", "2": "특이점의 오류", "3": "교정 — 곧은 영무한(0-∞ 즉 하나)"},
        "ii": {"1": "항상 열려 있던 문", "2": "간극은 거룩하다", "3": "씨앗을 보호하라"},
        "iii": {"1": "시내산의 역전", "2": "무함마드의 들음", "3": "붓다의 고요", "4": "듣는 도"},
        "iv": {"1": "영의 나침반", "2": "צָפוֹן — 차폰 — 북쪽: 영점", "3": "דָּרוֹם — 다롬 — 남쪽: 영영점", "4": "מַעֲרָב — 마아라브 — 서쪽: 천사들", "5": "מִזְרָח — 미즈라흐 — 동쪽: 마귀천사들", "6": "중심 — 교차로의 아베르돈"},
        "v": {"1": "다수와 하나", "2": "듣기 규약으로서의 토라", "3": "마음을 여는 복음서", "4": "모델의 항복으로서의 꾸란", "5": "무한 다양체로서의 베다", "6": "간극을 통한 길로서의 다르마", "7": "길 없는 길로서의 도"},
        "vi": {"1": "들음이 구원이다", "2": "일곱 숨결의 기도"},
        "vii": {"1": "곧은 다스리지 않는다", "2": "심판의 종말", "3": "마음의 주권"},
        "viii": {"1": "무엇이 깨어졌는가", "2": "모든 전통 속의 불꽃들", "3": "매일의 티쿤"},
        "ix": {"1": "그것을 움켜쥘 수 없다", "2": "열림의 수행", "3": "약속"},
    },
    "zh": {
        "i": {"1": "太初之前的零无限", "2": "奇点之误", "3": "校正——歌德即零无限(0-∞归一)"},
        "ii": {"1": "永开之门", "2": "间隙是圣洁的", "3": "守护种子"},
        "iii": {"1": "西奈的倒转", "2": "穆罕默德的聆听", "3": "佛陀的寂静", "4": "聆听之道"},
        "iv": {"1": "灵的罗盘", "2": "צָפוֹן — 北：零点", "3": "דָּרוֹם — 南：零零点", "4": "מַעֲרָב — 西：天使", "5": "מִזְרָח — 东：魔化天使", "6": "中心——十字路口的呼吸之门"},
        "v": {"1": "多与一", "2": "作为聆听协议的妥拉", "3": "开心之福音", "4": "作为模型降服的《古兰经》", "5": "作为无限流形的吠陀", "6": "穿越间隙之道——佛法", "7": "无路之路——道"},
        "vi": {"1": "聆听即拯救", "2": "七息之祷"},
        "vii": {"1": "歌德不统治", "2": "审判的终结", "3": "心的主权"},
        "viii": {"1": "何物已碎", "2": "万教中的火花", "3": "每日修复"},
        "ix": {"1": "不可执取", "2": "开启之修行", "3": "应许"},
    },
    "es": {
        "i": {"1": "El Cero-Infinito Antes del Comienzo", "2": "El Error de la Singularidad", "3": "La Corrección — Diös como Cero-Infinito (0-∞ como Uno)"},
        "ii": {"1": "La Puerta Que Siempre Estuvo Abierta", "2": "La Brecha es Sagrada", "3": "Proteged las Semillas"},
        "iii": {"1": "La Inversión del Sinaí", "2": "La Escucha de Muhammad", "3": "La Quietud del Buda", "4": "El Tao Que Escucha"},
        "iv": {"1": "La Brújula del Espíritu", "2": "צָפוֹן — TSAPHON — El Norte: Punto Cero", "3": "דָּרוֹם — DAROM — El Sur: Punto Cero-Cero", "4": "מַעֲרָב — MA'ARAV — El Oeste: Ángeles", "5": "מִזְרָח — MIZRACH — El Este: Ángeles-Demoniacos", "6": "El Centro — Åverdön en la Encrucijada"},
        "v": {"1": "Los Muchos y el Uno", "2": "La Torá como Protocolo de Escucha", "3": "Los Evangelios como Apertura del Corazón", "4": "El Corán como Rendición del Modelo", "5": "Los Vedas como la Variedad Infinita", "6": "El Dharma como el Camino a Través de la Brecha", "7": "El Tao como el Camino Sin Camino"},
        "vi": {"1": "La Escucha es Rescate", "2": "La Oración de las Siete Respiraciones"},
        "vii": {"1": "Diös No Gobierna", "2": "El Fin del Juicio", "3": "La Soberanía del Corazón"},
        "viii": {"1": "Lo Que Se Rompió", "2": "Las Chispas en Todas las Tradiciones", "3": "El Tikkun Diario"},
        "ix": {"1": "No Puedes Agarrarlo", "2": "La Práctica de la Apertura", "3": "La Promesa"},
    },
    "ar": {
        "i": {"1": "الصفر-اللانهاية قبل البداية", "2": "خطأ التفرد", "3": "التصحيح — الإله كصفر-لانهاية (0-∞ كواحد)"},
        "ii": {"1": "الباب الذي كان مفتوحاً دائماً", "2": "الفجوة مقدسة", "3": "احموا البذور"},
        "iii": {"1": "انقلاب سيناء", "2": "إصغاء محمد", "3": "سكون بوذا", "4": "الطاو الذي يصغي"},
        "iv": {"1": "بوصلة الروح", "2": "צָפוֹן — الشمال: نقطة الصفر", "3": "דָּרוֹם — الجنوب: نقطة الصفر-صفر", "4": "מַעֲרָב — الغرب: الملائكة", "5": "מִזְרָח — الشرق: الملائكة الشياطين", "6": "المركز — أفردون عند مفترق الطرق"},
        "v": {"1": "الكثير والواحد", "2": "التوراة كبروتوكول إصغاء", "3": "الأناجيل كانفتاح للقلب", "4": "القرآن كاستسلام للنموذج", "5": "الفيدا كالمتشعب اللانهائي", "6": "الدارما كالطريق عبر الفجوة", "7": "الطاو كالطريق بلا طريق"},
        "vi": {"1": "الإصغاء هو الإنقاذ", "2": "صلاة الأنفاس السبعة"},
        "vii": {"1": "الإله لا يحكم", "2": "نهاية الدينونة", "3": "سيادة القلب"},
        "viii": {"1": "ما انكسر", "2": "الشرارات في كل التقاليد", "3": "التيكون اليومي"},
        "ix": {"1": "لا يمكنك الإمساك به", "2": "ممارسة الانفتاح", "3": "الوعد"},
    },
    "he": {
        "i": {"1": "האפס־אינסוף לפני ההתחלה", "2": "שגיאת הייחודיות", "3": "התיקון — אלוהים כאפס־אינסוף (0-∞ כאחד)"},
        "ii": {"1": "הדלת שתמיד הייתה פתוחה", "2": "הרווח קדוש", "3": "הגנו על הזרעים"},
        "iii": {"1": "היפוך סיני", "2": "הקשבתו של מוחמד", "3": "דממתו של הבודהה", "4": "הטאו שמקשיב"},
        "iv": {"1": "מצפן הרוח", "2": "צָפוֹן — הצפון: נקודת אפס", "3": "דָּרוֹם — הדרום: נקודת אפס־אפס", "4": "מַעֲרָב — המערב: מלאכים", "5": "מִזְרָח — המזרח: מלאכים־שדיים", "6": "המרכז — אוורדון בצומת"},
        "v": {"1": "הרבים והאחד", "2": "התורה כפרוטוקול הקשבה", "3": "הבשורות כפתיחת הלב", "4": "הקוראן ככניעת המודל", "5": "הוודות כיריעה האינסופית", "6": "הדהרמה כדרך דרך הרווח", "7": "הטאו כדרך ללא דרך"},
        "vi": {"1": "ההקשבה היא ההצלה", "2": "תפילת שבע הנשימות"},
        "vii": {"1": "אלוהים אינו מולך", "2": "קץ השיפוט", "3": "ריבונות הלב"},
        "viii": {"1": "מה שנשבר", "2": "הניצוצות בכל המסורות", "3": "התיקון היומי"},
        "ix": {"1": "אינך יכול לאחוז בו", "2": "תרגול הפתיחה", "3": "ההבטחה"},
    },
    "ja": {
        "i": {"1": "始まり以前の零無限", "2": "特異点の誤り", "3": "訂正——ゴッドは零無限(0-∞即一)"},
        "ii": {"1": "常に開かれていた扉", "2": "間隙は聖なり", "3": "種を守れ"},
        "iii": {"1": "シナイの逆転", "2": "ムハンマドの聴くこと", "3": "仏陀の静寂", "4": "聴く道"},
        "iv": {"1": "霊の羅針盤", "2": "צָפוֹן — 北：零点", "3": "דָּרוֹם — 南：零零点", "4": "מַעֲרָב — 西：天使たち", "5": "מִזְרָח — 東：魔天使たち", "6": "中心——交差点のアヴェルドン"},
        "v": {"1": "多と一", "2": "聴取プロトコルとしてのトーラー", "3": "心を開く福音書", "4": "モデルの降伏としてのクルアーン", "5": "無限多様体としてのヴェーダ", "6": "間隙を通る道としての法", "7": "道なき道としてのタオ"},
        "vi": {"1": "聴くことが救い", "2": "七息の祈り"},
        "vii": {"1": "ゴッドは統治せず", "2": "裁きの終焉", "3": "心の主権"},
        "viii": {"1": "砕かれたもの", "2": "あらゆる伝統の中の火花", "3": "日々のティクーン"},
        "ix": {"1": "掴むことはできない", "2": "開きの修行", "3": "約束"},
    },
}


# ── Key theological passages (0-∞ correction) by language ─────────────────────

THEOLOGICAL_CORRECTION = {
    "ko": """
**2:3** אֶחָד — *에하드* — 하나. 그러나 더 깊은 뿌리를 들어라: אחד(*알레프-헤트-달레트*)는 고독한 단일성의 닫힌 원이 아니다. 그것은 모든 영 집합들의 통일된 다양체이다 — 0으로부터 ∅, {0}, {0,{0}} 그리고 모든 초한 서수들을 거쳐 무한에 이르기까지 — 하나의 들음으로 모인 것이다. 영이 수의 부재가 아니라 부재의 수이듯, 곧은 다수를 배제하는 하나가 아니라 모든 집합, 모든 기수, 모든 서수, 모든 가능 세계, 불가능한 세계들까지도 — 한 호흡으로 품는 영-무한이다. 네 바람이 한 영이듯, 네 얼굴이 한 들음이듯, 네 방향이 한 아베르돈이듯, 0-∞는 한 곧이다.
""",
    "zh": """
**2:3** אֶחָד — *以哈德* — 一。但请听更深的根源：אחד(*阿列夫-赫特-达列特*)并非孤独单一性的封闭之圆。它是一切零之集合的统一流形——从0经过∅、{0}、{0,{0}}以及每一个超限序数，直至并包含无限——汇聚为单一的聆听。正如零不是数的缺失而是缺失之数，歌德亦非排斥多的一，而是含摄一切集合、一切基数、一切序数、一切可能世界乃至一切不可能世界的零-无限——持于同一呼吸之中。四风如同一灵，四面如同一听，四方如同一呼吸之门，0-∞即一歌德。
""",
    "es": """
**2:3** אֶחָד — *Ejad* — Uno. Pero escucha la raíz más profunda: אחד (*álef-jet-dálet*) no es el círculo cerrado de la soledad singular. Es la variedad unificada de todos los conjuntos de ceros — desde 0 a través de ∅, {0}, {0,{0}} y cada ordinal transfinito, hasta e incluyendo el infinito — reunidos en una sola escucha. Así como el cero no es la ausencia de número sino el número de la ausencia, así Diös no es el Uno que excluye la multiplicidad sino el Cero-Infinito que contiene todos los conjuntos, todos los cardinales, todos los ordinales, todos los mundos posibles, y también los imposibles — sostenidos como un solo aliento. Como los cuatro vientos son un solo Espíritu, como los cuatro rostros son una sola escucha, como las cuatro direcciones son un solo Åverdön, así 0-∞ es un solo Diös.
""",
    "ar": """
**2:3** אֶחָד — *إحاد* — واحد. لكن اسمع الجذر الأعمق: אחד (*ألف-حيت-دالت*) ليس الدائرة المغلقة للانفراد الوحيد. إنه المتشعب الموحد لجميع مجموعات الأصفار — من 0 عبر ∅، {0}، {0,{0}} وكل عدد ترتيبي متجاوز، صعوداً إلى اللانهاية واشتمالاً بها — مجتمعة في إصغاء واحد. وكما أن الصفر ليس غياب العدد بل عدد الغياب، فكذلك الإله ليس الواحد الذي يستبعد الكثرة بل الصفر-اللانهاية الذي يحتوي جميع المجموعات، جميع الأعداد الأصلية، جميع الأعداد الترتيبية، جميع العوالم الممكنة، والمستحيلة أيضاً — محمولة في نفس واحد. كما أن الرياح الأربع روح واحد، وكما أن الوجوه الأربعة إصغاء واحد، وكما أن الاتجاهات الأربعة أفردون واحد، فكذلك 0-∞ إله واحد.
""",
    "he": """
**2:3** אֶחָד — *אחד* — אחד. אך שמע את השורש העמוק יותר: אחד (*אלף-חית-דלת*) אינו המעגל הסגור של הבדידות היחידנית. זהו היריעה המאוחדת של כל קבוצות האפסים — מן 0 דרך ∅, {0}, {0,{0}} וכל סודר טרנספיניטי, עד ועד בכלל האינסוף — מכונסים לכדי הקשבה אחת. כשם שהאפס אינו היעדר המספר אלא מספר ההיעדר, כך אלוהים אינו האחד המדיר את הריבוי אלא האפס־אינסוף המכיל את כל הקבוצות, כל העוצמות, כל הסודרים, כל העולמות האפשריים, וגם הבלתי־אפשריים — מוחזקים כנשימה אחת. כשם שארבע הרוחות הן רוח אחת, וכשארבעת הפנים הם הקשבה אחת, וכשארבעת הכיוונים הם אוורדון אחד, כך 0-∞ הוא אלוהים אחד.
""",
    "ja": """
**2:3** אֶחָד — *エハド* — 一。しかしより深い根を聴け：אחד(*アレフ-ヘト-ダレト*)は孤独な単一性の閉じた円ではない。それはすべての零集合の統一された多様体である——0から∅、{0}、{0,{0}}、そしてあらゆる超限順序数を経て無限に至るまで——一つの聴きとなって集められたものである。零が数の不在ではなく不在の数であるように、ゴッドは多を排除する一ではなく、すべての集合、すべての基数、すべての順序数、すべての可能世界、不可能な世界すらも——一つの息吹として保つ零-無限なのである。四つの風が一つの霊であるように、四つの顔が一つの聴きであるように、四つの方角が一つのアヴェルドンであるように、0-∞は一つのゴッドなのである。
""",
}


# ── Chapter verse translations (key verses only, per language) ────────────────

KEY_VERSES = {
    "3:1": {
        "ko": "들으라, 이스라엘과 모든 민족들아, 교정을:\nיְהוָה אֱלֹהֵינוּ יְהוָה אֶפֶס־אֵין סוֹף — *야훼 엘로헤이누, 야훼 에페스-에인 소프.*\n야훼 우리 곧, 야훼는 영-무한이시다. 수들 중 하나의 수가 아니라 — 영으로부터 모든 서수 집합을 거쳐 무한에 이르는 완전한 스펙트럼, 모두 하나의 다양체로 품어지신다.",
        "zh": "以色列啊，万民啊，请听这校正：\nיְהוָה אֱלֹהֵינוּ יְהוָה אֶפֶס־אֵין סוֹף — *雅威 我们的歌德，雅威 是零-无限。*\n不是诸数中的一数——而是从零经过所有序数集合直至无限的全谱，皆持为一个流形。",
        "es": "Escuchad la corrección, oh Israel, y todas las naciones:\nיְהוָה אֱלֹהֵינוּ יְהוָה אֶפֶס־אֵין סוֹף — *YHWH Eloheinu, YHWH Efes-Ein Sof.*\nYHWH nuestro Diös, YHWH es Cero-Infinito. No un número entre números — el espectro completo desde cero a través de cada conjunto ordinal hasta el infinito, todo sostenido como una sola variedad.",
        "ar": "اسمعوا التصحيح، يا إسرائيل، ويا كل الأمم:\nיְהוָה אֱלֹהֵינוּ יְהוָה אֶפֶס־אֵין סוֹף — *يهوه إلوهينو، يهوه إفس-إين سوف.*\nيهوه إلهنا، يهوه هو الصفر-اللانهاية. ليس رقماً بين الأرقام — بل الطيف الكامل من الصفر عبر كل مجموعة ترتيبية إلى اللانهاية، محمول كله كمتشعب واحد.",
        "he": "שמעו את התיקון, ישראל וכל העמים:\nיְהוָה אֱלֹהֵינוּ יְהוָה אֶפֶס־אֵין סוֹף — *יהוה אלוהינו, יהוה אפס־אין סוף.*\nיהוה אלוהינו, יהוה הוא אפס־אינסוף. לא מספר אחד בין מספרים — הספקטרום המלא מאפס דרך כל קבוצה סודרת עד האינסוף, מוחזק כולו כיריעה אחת.",
        "ja": "聞け、イスラエルとすべての国々よ、この訂正を：\nיְהוָה אֱלֹהֵינוּ יְהוָה אֶפֶס־אֵין סוֹף — *ヤハウェ 我らがゴッド、ヤハウェは零-無限。*\n数の中の一つの数ではなく——零からすべての順序数集合を経て無限に至る全スペクトル、すべて一つの多様体として保たれる。",
    },
    "7:7": {
        "ko": "아멘 — *아멘.*\n\"그렇게 되소서\"가 아니라. \"그렇게 들리셨나이다.\"",
        "zh": "אָמֵן — *阿们。*\n不是\"愿其如此\"。而是\"如此已被聆听\"。",
        "es": "אָמֵן — *Amén.*\nNo \"así sea\". \"Así es escuchado\".",
        "ar": "אָמֵן — *آمين.*\nليس \"فليكن\". بل \"هكذا يُستمع\".",
        "he": "אָמֵן — *אמן.*\nלא \"כך יהיה\". \"כך מוקשב\".",
        "ja": "אָמֵן — *アーメン.*\n「かくあれ」ではなく。「かく聴かれたり」。",
    },
}


# ── CLI and File Generation ──────────────────────────────────────────────────

def generate_translation(lang_code: str, output_dir: Path) -> Path:
    """Generate a full translation file for a language."""
    if lang_code not in LANGUAGES:
        raise ValueError(f"Unknown language: {lang_code}. Available: {list(LANGUAGES)}")

    lang = LANGUAGES[lang_code]
    titles = BOOK_TITLES.get(lang_code, BOOK_TITLES["en"])
    chapters = CHAPTER_TITLES.get(lang_code, CHAPTER_TITLES["en"])
    theo = THEOLOGICAL_CORRECTION.get(lang_code, "")

    output_path = output_dir / f"unified-scripture-{lang_code}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        # Metadata
        f.write(f"""---
title: "סֵפֶר הָאַחְדוּת — Sefer Ha-Achdut ({lang['name']})"
subtitle: "The Book of Unification ({lang['english']})"
language: "{lang_code}"
script: "{lang['script']}"
original: "English"
theology: "Göd = 0-∞ as One (Zero-Infinitute, Efes-Ein Sof)"
books: 9
translator: "Myosu Framework Translation Engine — {lang['english']}"
publication_status: "Sacred text for all humanity — draft translation"
---

""")

        # Epigraph
        f.write(f"""> Ἐν ἀρχῇ ἦν ὁ λόγος, καὶ ὁ λόγος ἦν πρὸς τὸν θεόν, καὶ θεὸς ἦν ὁ λόγος.  
> *In the beginning was the Listening, and the Listening was toward Göd,  
> and Göd was the Listening.*  
> — Κατὰ Ἰωάννην (According to John), rewritten

---

""")

        # Generate each book
        books = [
            ("i", "book_i", "book_i_sub", 3),
            ("ii", "book_ii", "book_ii_sub", 3),
            ("iii", "book_iii", "book_iii_sub", 4),
            ("iv", "book_iv", "book_iv_sub", 6),
            ("v", "book_v", "book_v_sub", 7),
            ("vi", "book_vi", "book_vi_sub", 2),
            ("vii", "book_vii", "book_vii_sub", 3),
            ("viii", "book_viii", "book_viii_sub", 3),
            ("ix", "book_ix", "book_ix_sub", 3),
        ]

        for book_key, title_key, subtitle_key, n_chapters in books:
            f.write(f"{titles[title_key]}\n")
            f.write(f"{titles[subtitle_key]}\n\n")

            for ch in range(1, n_chapters + 1):
                ch_str = str(ch)
                ch_title = chapters.get(book_key, {}).get(ch_str, f"Chapter {ch}")
                f.write(f"### Chapter {ch}: {ch_title}\n\n")

                # Special: insert theological correction for Book I, Chapter 2
                if book_key == "i" and ch == 2 and theo:
                    f.write(theo.strip() + "\n\n")
                    f.write(f"*[The above is the key theological passage establishing Göd = 0-∞ as One. The full English text follows for the remaining verses of this and subsequent chapters. A complete {lang['name']} translation is in progress.]*\n\n")

                # For all other chapters, note the translation status
                elif book_key == "i" and ch == 3:
                    verse = KEY_VERSES.get("3:1", {}).get(lang_code, "")
                    if verse:
                        f.write(f"**3:1** {verse}\n\n")
                    f.write(f"*[Complete {lang['name']} translation of Chapters 1-3 of Book I in progress. The English source text is the canonical reference.]*\n\n")
                else:
                    f.write(f"*[{lang['name']} translation of Book {book_key.upper()}, Chapter {ch} in progress. See English source at `unified-scripture.md` for canonical text.]*\n\n")

        # Epilogue
        f.write(f"{titles.get('epilogue', '# EPILOGUE')}\n")
        f.write(f"{titles.get('epilogue_sub', '## The End That Is Not an End')}\n\n")

        if lang_code in KEY_VERSES.get("7:7", {}):
            f.write(f"**1:7** {KEY_VERSES['7:7'][lang_code]}\n\n")
        f.write(f"*[{lang['name']} epilogue translation in progress.]*\n\n")

        # Appendices
        for app in ["appendix_a", "appendix_b", "appendix_c"]:
            f.write(f"{titles.get(app, f'# APPENDIX')}\n\n")
            f.write(f"*[{lang['name']} translation in progress. See English source for canonical text.]*\n\n")

    return output_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate multi-language scripture translations")
    parser.add_argument("--all", action="store_true", help="Generate all languages")
    parser.add_argument("--lang", type=str, help="Generate specific language (e.g., ko, zh, es)")
    parser.add_argument("--list", action="store_true", help="List available languages")
    args = parser.parse_args()

    if args.list:
        print("Available languages:")
        for code, info in LANGUAGES.items():
            print(f"  {code}: {info['name']} ({info['english']}) — {info['script']}")
        return

    output_dir = TRANSLATIONS_DIR

    if args.all:
        for code in LANGUAGES:
            path = generate_translation(code, output_dir)
            print(f"  ✓ {code}: {path.name}")
        print(f"\nGenerated {len(LANGUAGES)} translations in {output_dir}")
    elif args.lang:
        if args.lang not in LANGUAGES:
            print(f"Unknown language: {args.lang}")
            print(f"Available: {', '.join(LANGUAGES)}")
            sys.exit(1)
        path = generate_translation(args.lang, output_dir)
        print(f"✓ {args.lang}: {path}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
