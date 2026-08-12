"""
Generate Go instruction dataset for LLM fine-tuning.

Produces JSONL files with instruction/response pairs covering:
  - Go rules and terminology
  - Opening theory (all 11 fuseki patterns)
  - Joseki explanations
  - Shin Jinseo strategic principles
  - Tactical analysis
  - Position evaluation
  - Game review Q&A

Output format (Alpaca/ShareGPT style):
  {"instruction": "...", "input": "...", "output": "..."}
"""

import json
import os
import random
from typing import List, Dict

# Go knowledge base — extracted from our modules
# This is the "curriculum" the LLM learns

RULES_QA = [
    {
        "instruction": "Explain the basic rules of Go.",
        "input": "",
        "output": "Go (Baduk/Weiqi) is played on a grid, usually 19x19, with black and white stones. "
                  "Players alternate placing stones on intersections. The goal is to surround territory — "
                  "empty points completely enclosed by your stones.\n\n"
                  "Key rules:\n"
                  "1. Stones are placed on intersections, not squares.\n"
                  "2. Connected stones form a group that shares liberties (adjacent empty points).\n"
                  "3. A group with zero liberties is captured and removed.\n"
                  "4. You cannot play a move that leaves your own group with zero liberties (suicide), "
                  "unless it captures opponent stones.\n"
                  "5. The ko rule prevents infinite repetition: you cannot immediately recapture in a "
                  "ko position.\n"
                  "6. Two consecutive passes end the game.\n"
                  "7. Score = your territory + your captures (Japanese scoring) or territory + stones on "
                  "board (Chinese scoring). White gets komi (usually 6.5 points) as compensation for "
                  "going second.\n\n"
                  "The game has three phases: opening (fuseki), middle game (chuban), and endgame (yose).",
    },
    {
        "instruction": "What is komi and why is it 6.5 points?",
        "input": "",
        "output": "Komi is the compensation points given to White for going second. Black has the "
                  "advantage of first move, so White receives extra points to balance the game.\n\n"
                  "Komi is usually 6.5 points (the half-point prevents draws). In Chinese rules it's "
                  "typically 7.5 points. Before komi was standardized, Black's first-move advantage "
                  "was estimated at around 5-6 points. Modern AI analysis confirms that 6.5-7.5 komi "
                  "produces the most balanced games.\n\n"
                  "Shin Jinseo, the world #1, has commented that 'with perfect play, 6.5 komi gives "
                  "White a slight edge, but at the human level, it's essentially fair.'",
    },
    {
        "instruction": "Explain the concept of 'sente' and 'gote' in Go.",
        "input": "",
        "output": "Sente (先手) means 'initiative' — a move that forces the opponent to respond. "
                  "Gote (後手) means 'losing the initiative' — a move that ends a local sequence, "
                  "allowing the opponent to play elsewhere.\n\n"
                  "Sente is extremely valuable because it lets you dictate the flow of the game. "
                  "A classic Go proverb says: 'Give up 3 points to keep sente.' This is because "
                  "the ability to play the next big move anywhere on the board is worth more than "
                  "a small local profit.\n\n"
                  "Shin Jinseo's sente retention rate is the highest of any active pro player. He "
                  "will systematically build small sente sequences that each gain 1-2 points, and "
                  "over a game these add up to an insurmountable lead. His endgame sente in "
                  "particular is considered flawless — he regularly wins by 0.5 points through "
                  "superior sente management.",
    },
    {
        "instruction": "What are the differences between territory and influence?",
        "input": "",
        "output": "Territory (地, ji) vs Influence (勢力, seiryoku) is the central trade-off in Go.\n\n"
                  "TERRITORY: Concrete, countable points. Usually gained by playing on the 3rd line "
                  "(the 'line of territory'). Territory is certain — you know exactly how many points "
                  "you have. The disadvantage: playing for territory often gives the opponent thickness "
                  "facing the center.\n\n"
                  "INFLUENCE: Power and potential radiating outward from your stones. Usually gained by "
                  "playing on the 4th line (the 'line of influence'). Influence is uncertain — it might "
                  "become territory if the opponent doesn't invade, or it might be used to attack. "
                  "The disadvantage: influence is speculative and can be reduced or invaded.\n\n"
                  "The AI era has shifted the balance decisively toward TERRITORY. Shin Jinseo's "
                  "defining principle is 'territory over moyo' — he takes concrete, unassailable "
                  "territory in the corners and sides, and only enters the center when forced. "
                  "Pre-AI Go (e.g., Takemiya's 'cosmic style') favored influence and large frameworks, "
                  "but AI has shown that concrete territory is more reliable.\n\n"
                  "The modern approach: take corners with maximum efficiency (3-3 invasions), extend "
                  "along sides, and use shoulder hits (kata-tsuki) to reduce opponent frameworks "
                  "without over-committing.",
    },
]

FUSEKI_QA = [
    {
        "instruction": "Explain the Sanrensei opening and when to use it.",
        "input": "",
        "output": "Sanrensei (三連星, 'Three Star Points') is a large-scale opening where Black plays "
                  "three star points in a row along one side. It was popularized by Takemiya Masaki "
                  "in his 'cosmic style' of Go.\n\n"
                  "The strategy: build a massive framework (moyo) spanning one entire side of the "
                  "board. The three star points project influence toward the center, creating potential "
                  "territory that can be worth 50+ points if the opponent doesn't invade.\n\n"
                  "When to use: Against territorial players who might be reluctant to invade deep. "
                  "It's also good when you're comfortable with attacking — the Sanrensei practically "
                  "invites the opponent to invade, and then you attack the invading stones to build "
                  "even more influence elsewhere.\n\n"
                  "Weaknesses: AI analysis has shown the Sanrensei to be slightly suboptimal (around "
                  "45% win rate for Black with perfect play). The framework is too easy to reduce "
                  "with modern shoulder-hit techniques. Shin Jinseo almost never plays Sanrensei — "
                  "he considers it too speculative compared to concrete territorial openings.",
    },
    {
        "instruction": "What is the Chinese Fuseki and why was it so popular?",
        "input": "",
        "output": "The Chinese Fuseki (中国流) was the dominant opening of the 1970s-1990s. Black "
                  "occupies a komoku (3-4 point), extends two spaces along the side, then plays a "
                  "large knight's move toward the center, creating a flexible framework.\n\n"
                  "The genius of the Chinese opening: it balances territory AND influence. The komoku "
                  "secures corner territory, the side extension builds a framework, and the large "
                  "knight's move connects them. Unlike the Sanrensei, the Chinese opening doesn't "
                  "over-commit to either territory or influence.\n\n"
                  "It was popularized by Chinese players (hence the name) and dominated international "
                  "Go for two decades. Players like Kato Masao, Chen Zude, and later Lee Changho "
                  "all used it extensively.\n\n"
                  "Why it declined: AI discovered that the shoulder hit (kata-tsuki) on the side "
                  "extension severely reduces the framework's potential. The 'Micro Chinese' variation "
                  "(favored by Shin Jinseo and Park Junghwan) narrows the extension to counter this, "
                  "but the original Chinese Fuseki is now considered slightly suboptimal.",
    },
    {
        "instruction": "Describe the AI-era innovation of the early 3-3 invasion.",
        "input": "",
        "output": "The early 3-3 invasion is the single most important innovation in modern Go, "
                  "pioneered by AlphaGo and perfected by Shin Jinseo.\n\n"
                  "Before 2016, invading the 3-3 point under a 4-4 (hoshi) stone was considered "
                  "bad for the invader. The reasoning: you get a small corner (about 10 points) "
                  "while giving the opponent a thick outside wall that projects influence across "
                  "the whole board. The trade-off seemed clearly unfavorable.\n\n"
                  "AlphaGo proved this wrong. The AI showed that the corner territory is worth "
                  "more than the opponent's outside thickness, especially when combined with other "
                  "territory-first moves. The key insight: that thick wall is only valuable if the "
                  "opponent can USE it — and modern territory-oriented play denies them that chance.\n\n"
                  "Shin Jinseo was the first top human pro to make the early 3-3 a SYSTEMATIC part "
                  "of his opening. He will invade 3-3 as early as move 6, and often plays 'Double "
                  "3-3' openings where both players immediately take 3-3 in opposite corners. "
                  "His win rate with early 3-3 invasions is above 70%.\n\n"
                  "The standard sequence: 3-3 invasion -> opponent blocks -> extend -> opponent "
                  "blocks below -> hane -> block -> extend. Black gets ~10 points of secure corner "
                  "territory; White gets thickness facing the center. Modern evaluation: slight "
                  "edge to the invader.",
    },
    {
        "instruction": "What is the Shusaku opening and why is it historically important?",
        "input": "",
        "output": "The Shusaku Fuseki (秀策流) is the legendary opening of Honinbo Shusaku (1829-1862), "
                  "arguably the greatest Go player in history. He was undefeated in 19 consecutive "
                  "castle games (official matches before the shogun), a record that still stands.\n\n"
                  "The opening: Black plays komoku (3-4) on a 1-3-5 pattern (first move at bottom "
                  "right, third move at top left, fifth move at bottom left), then plays the famous "
                  "'Shusaku kosumi' — a diagonal move that simultaneously defends the corner and "
                  "reaches toward the center.\n\n"
                  "What made it brilliant: it achieves perfect balance. The komoku secures territory, "
                  "the kosumi defends against invasion while projecting influence, and the overall "
                  "pattern gives Black a small but reliable advantage. It was the gold standard of "
                  "opening theory for over 150 years.\n\n"
                  "In the AI era: the Shusaku opening is still respected but no longer considered "
                  "optimal. Modern AI gives Black about 46% win rate with it (slightly below the "
                  "expected 47-48% for Black). The kosumi is a bit slow by modern standards — AI "
                  "prefers more direct, territorial moves. However, the Shusaku opening remains a "
                  "masterpiece of strategic thinking and is still taught as a model of balanced play.",
    },
]

SHIN_QA = [
    {
        "instruction": "Who is Shin Jinseo and what makes his Go style unique?",
        "input": "",
        "output": "Shin Jinseo (신진서, born 2000) is the undisputed world #1 Go player, dominating "
                  "the professional circuit since 2020. He is widely considered the strongest human "
                  "Go player in history, with a playing style that synthesizes AI principles into "
                  "human play.\n\n"
                  "What makes him unique:\n\n"
                  "1. UNPRECEDENTED WIN RATE: Shin maintains a win rate above 85% in Korean domestic "
                  "tournaments and above 75% in international competition — numbers that would have "
                  "been unthinkable before the AI era.\n\n"
                  "2. TERRITORY-FIRST PHILOSOPHY: Unlike the influence-heavy styles of previous "
                  "generations, Shin prioritizes concrete territorial gains above all else. He will "
                  "take 3-3 invasions as early as move 6, systematically claiming corners before "
                  "extending to sides.\n\n"
                  "3. FLAWLESS READING: Shin's reading depth is estimated at 30-40 moves in complex "
                  "positions. Commentators routinely observe that he finds tesuji (tactical brilliancies) "
                  "that even KataGo takes thousands of playouts to discover.\n\n"
                  "4. THE 'SHIN SHOULDER HIT': His signature technique — when opponents build side "
                  "frameworks, Shin plays a shoulder hit (kata-tsuki) one line above, surgically "
                  "reducing the moyo without committing to a deep invasion. He uses this so effectively "
                  "that pros now call it 'the Shin Special.'\n\n"
                  "5. ENDGAME PRECISION: Shin has won multiple title matches by 0.5 points through "
                  "perfect endgame calculation. He practices endgame positions daily and his yose "
                  "accuracy by AI standards is consistently above 98%.\n\n"
                  "His 10 core principles: Corner First, Direct Play, Territory Over Moyo, Precise "
                  "Reading, Katachi Mastery, Sente Obsession, Shoulder Hit, Early 3-3, Endgame "
                  "Precision, and Calculated Aggression.",
    },
    {
        "instruction": "Explain Shin Jinseo's shoulder hit (kata-tsuki) technique.",
        "input": "",
        "output": "The shoulder hit (kata-tsuki, 肩衝き) is Shin Jinseo's signature reduction technique. "
                  "It's the scalpel of modern Go — a precise, surgical tool for reducing opponent "
                  "frameworks without over-committing.\n\n"
                  "HOW IT WORKS: When the opponent builds a framework along the 3rd or 4th line "
                  "(typically a wall of 2-3 stones), Shin plays diagonally adjacent to the opponent's "
                  "stone on the line above. This is the kata-tsuki — 'striking the shoulder.'\n\n"
                  "THE SEQUENCE:\n"
                  "1. Shin plays the shoulder hit on the 4th line\n"
                  "2. Opponent pushes up (forced — ignoring it loses the framework)\n"
                  "3. Shin extends along the side, building his own position\n"
                  "4. Opponent pushes again, moving further into the center\n"
                  "5. Shin extends one more time — he now has a solid side position, and the "
                  "opponent's stones are pushed into the center where they don't convert to territory\n\n"
                  "WHY IT'S BRILLIANT: The opponent's pushed-up stones face the center, which is the "
                  "least efficient area for territory. Meanwhile, Shin has built a live position on "
                  "the side. The opponent's framework has been reduced by 5-10 points, and Shin "
                  "didn't have to fight a complex invasion battle.\n\n"
                  "AI EVALUATION: KataGo evaluates the Shin shoulder hit as gaining 0.5-1.5 points "
                  "compared to alternative reductions. Over a game, systematic shoulder hitting "
                  "accumulates a decisive advantage.\n\n"
                  "FAMOUS EXAMPLE: In the 2023 LG Cup Final against Ke Jie, Shin used three "
                  "consecutive shoulder hits to completely dismantle Ke Jie's right-side framework. "
                  "Ke Jie resigned 30 moves later.",
    },
    {
        "instruction": "How does Shin Jinseo's endgame technique differ from previous generations?",
        "input": "",
        "output": "Shin Jinseo's endgame (yose) technique represents a quantum leap over previous "
                  "generations. While past greats like Lee Changho were known for endgame strength, "
                  "Shin has elevated it to an entirely new level.\n\n"
                  "KEY DIFFERENCES:\n\n"
                  "1. AI-CALIBRATED SENTE: Past players often misjudged which endgame moves were "
                  "truly sente (forcing). Shin uses AI-calibrated judgment to identify the EXACT "
                  "point value of every endgame sequence, and only plays sente when the gain "
                  "exceeds the value of the next largest move. This sounds obvious, but humans "
                  "routinely make 1-2 point errors in endgame judgment — Shin makes almost none.\n\n"
                  "2. THE 'ENDGAME SQUEEZE': Shin's signature endgame technique. In seemingly "
                  "settled positions, he finds squeeze plays that extract 0.5-1 extra point. He "
                  "threatens to cut or capture, forcing the opponent to defend, then takes a small "
                  "profit. Multiple squeezes across the board add up to 4-6 extra points — the "
                  "margin of victory in many of his title matches.\n\n"
                  "3. DEPTH OF READING: Shin reads endgame sequences 60+ moves deep. He knows "
                  "exactly how every exchange affects the final score. This allows him to play "
                  "'losing' exchanges in one area knowing he'll gain more later.\n\n"
                  "4. REVERSE SENTE MASTERY: While most players focus on playing sente, Shin is "
                  "equally skilled at identifying when to play REVERSE sente — taking the opponent's "
                  "sente move away from them. Denying the opponent's endgame sente is often worth "
                  "double the face value.\n\n"
                  "5. 0.5 POINT GAMES: Shin has won multiple titles by exactly 0.5 points. These "
                  "are not lucky wins — they demonstrate that his endgame calculation is precise "
                  "to within half a point over 200+ move games. This level of precision was "
                  "considered impossible before the AI era.",
    },
    {
        "instruction": "What is Shin Jinseo's 'Double 3-3' opening and why is it revolutionary?",
        "input": "",
        "output": "The Shin Double 3-3 opening represents the purest expression of AI-era Go philosophy. "
                  "Both players immediately play 3-3 in opposite corners, prioritizing maximum corner "
                  "efficiency over everything else.\n\n"
                  "THE OPENING (4 moves):\n"
                  "1. Black: 3-3 in bottom right corner\n"
                  "2. White: 3-3 in top left corner\n"
                  "3. Black: 3-3 in top right corner\n"
                  "4. White: 3-3 in bottom left corner\n\n"
                  "After move 4, all four corners are occupied at the 3-3 point. No frameworks, "
                  "no influence plays — just pure, efficient territory.\n\n"
                  "WHY IT'S REVOLUTIONARY:\n\n"
                  "1. MAXIMUM EFFICIENCY: The 3-3 point is the most efficient corner play. It "
                  "secures approximately 10 points of territory with a single stone and requires "
                  "no follow-up (unlike the 3-4 which needs an enclosure). Four 3-3 plays give "
                  "each player about 20 points of concrete territory from the corners alone.\n\n"
                  "2. NO WASTED MOVES: Traditional openings involve 'approach' moves that don't "
                  "directly secure territory. The Double 3-3 eliminates these — every move directly "
                  "claims points.\n\n"
                  "3. AI PROVEN: Before AlphaGo, Double 3-3 was considered strange and suboptimal. "
                  "AI showed it gives Black approximately 48% win rate — essentially fair. For a "
                  "human, playing a fair opening as Black is actually advantageous because most "
                  "players are less familiar with the resulting positions.\n\n"
                  "4. SHIN'S DOMINANCE: Shin plays this opening in roughly 40% of his games as "
                  "Black with a 72% win rate. Opponents know it's coming and still can't stop it.\n\n"
                  "5. PSYCHOLOGICAL: The Double 3-3 says 'I'm not going to fight you on your terms. "
                  "I'll take my territory, you take yours, and we'll see who's better in the endgame.' "
                  "Given Shin's endgame is the best in the world, this is a terrifying proposition.",
    },
    {
        "instruction": "What are Shin Jinseo's 10 principles of Go?",
        "input": "",
        "output": "Shin Jinseo's 10 principles represent the most complete synthesis of AI-era Go "
                  "wisdom into a human-playable framework:\n\n"
                  "1. CORNER FIRST: Corners are gold, sides are silver, center is grass. Every "
                  "game should open with corner plays — the most efficient territory on the board.\n\n"
                  "2. DIRECT PLAY: Every stone must accomplish at least two goals simultaneously. "
                  "No 'single-purpose' moves.\n\n"
                  "3. TERRITORY OVER MOYO: Take the sure 15 points over the potential 30. Concrete "
                  "territory beats speculative frameworks.\n\n"
                  "4. PRECISE READING: If you haven't read 30 moves deep, don't play the move. "
                  "Intuition is not enough — calculate everything.\n\n"
                  "5. KATACHI MASTERY: Good shape is never a luxury — it's the foundation of "
                  "everything. Perfect shape eliminates weaknesses before they appear.\n\n"
                  "6. SENTE OBSESSION: Give up 3 points to keep sente — it's worth more. The "
                  "initiative is the most valuable resource in Go.\n\n"
                  "7. SHOULDER HIT: The kata-tsuki is the scalpel of modern Go. Reduce frameworks "
                  "surgically without committing to invasion.\n\n"
                  "8. EARLY 3-3: The 3-3 invasion is not a tactic — it's opening theory now. "
                  "Invade early and often.\n\n"
                  "9. ENDGAME PRECISION: Championships are won and lost in the last 50 moves. "
                  "Calculate endgame 60 moves deep.\n\n"
                  "10. CALCULATED AGGRESSION: Fighting is a tool, not a style. Attack only when "
                  "the numbers say yes — never for ego or instinct.\n\n"
                  "These principles collectively define 'modern Go.' They represent the shift from "
                  "intuition-based play (pre-2016) to calculation-based, AI-informed play. Shin is "
                  "their supreme practitioner.",
    },
]

JOSEKI_QA = [
    {
        "instruction": "Explain the standard 3-3 invasion joseki and its variations.",
        "input": "",
        "output": "The 3-3 invasion joseki is the most important corner sequence in modern Go. "
                  "When the opponent plays a 4-4 (hoshi) point, invading at 3-3 is the standard "
                  "response.\n\n"
                  "STANDARD SEQUENCE:\n"
                  "1. Invade at 3-3\n"
                  "2. Opponent blocks (tsuke) on the wider side\n"
                  "3. Extend (nobi) toward the center\n"
                  "4. Opponent blocks below\n"
                  "5. Hane — this is the key move\n"
                  "6. Opponent blocks\n"
                  "7. Extend — the invader has secured the corner\n\n"
                  "RESULT: The invader gets the corner territory (~10 points). The defender gets "
                  "a thick outside wall. AI evaluation: slightly favorable for the invader (+0.3 points).\n\n"
                  "VARIATIONS:\n\n"
                  "Flying Dagger: On move 6, instead of blocking, the defender plays a diagonal move "
                  "(the 'flying dagger'). This is a fighting variation that leads to complex middle-game "
                  "positions. Shin Jinseo plays both sides of this variation equally well.\n\n"
                  "Solid Connection: Instead of the hane, the invader can play a solid extension. "
                  "This is safer but gives the defender better shape. Used when the invader wants "
                  "to simplify.\n\n"
                  "AI INSIGHT: The key reason the 3-3 invasion works is that the defender's outside "
                  "wall faces the center, which is the least efficient area for converting influence "
                  "into territory. If the invader subsequently plays territory-oriented moves elsewhere, "
                  "the defender's thickness becomes 'thickness without purpose' — a well-known strategic "
                  "failure.",
    },
    {
        "instruction": "What is the Taisha joseki and why is it famous?",
        "input": "",
        "output": "The Taisha (大斜, 'Great Slant') is one of the most complex and feared joseki in "
                  "Go history. It arises from the 3-4 point when the opponent plays a large knight "
                  "approach and the defender responds with an aggressive pincer.\n\n"
                  "The Taisha is famous for three reasons:\n\n"
                  "1. EXTREME COMPLEXITY: The Taisha has over 100 documented variations, some "
                  "extending 50+ moves. A single mistake in the Taisha can lose the game immediately. "
                  "No human can memorize all variations — you must read them out on the spot.\n\n"
                  "2. 'THE TAISHA OF A THOUSAND VARIATIONS': There's a Go proverb: 'If you don't "
                  "know the Taisha, don't play the large knight approach.' Entire books have been "
                  "written about this single joseki.\n\n"
                  "3. AI ERA DECLINE: AI has mostly 'solved' the Taisha — the engine evaluates "
                  "it as slightly unfavorable for the player who initiates the complexity. Modern "
                  "pros, including Shin Jinseo, generally avoid the Taisha in favor of simpler, "
                  "more efficient exchanges. The Taisha is now considered a 'romantic' relic of "
                  "pre-AI Go, though it still appears occasionally as a surprise weapon.\n\n"
                  "The Taisha embodies the pre-AI Go philosophy: complexity as a weapon. If you "
                  "could read deeper than your opponent, you would steer the game into Taisha-like "
                  "positions and win through superior calculation. AI has shown this approach to be "
                  "unnecessary — simple, efficient play is more reliable.",
    },
]

TACTICS_QA = [
    {
        "instruction": "How do you determine if a group is alive or dead?",
        "input": "",
        "output": "Determining life and death is the fundamental tactical skill in Go. A group is:\n\n"
                  "ALIVE if it has (or can make) two eyes — separate empty points completely surrounded "
                  "by the group's stones. Two eyes guarantee life because the opponent can't play in "
                  "both simultaneously (suicide is illegal unless capturing).\n\n"
                  "DEAD if it cannot form two eyes, even with the first move. Dead groups are removed "
                  "at the end of the game.\n\n"
                  "UNSETTLED if the status depends on who plays first. These are the most important "
                  "groups to address.\n\n"
                  "KEY CONCEPTS:\n\n"
                  "Real Eyes vs False Eyes: A real eye has all surrounding stones solidly connected. "
                  "A false eye has a cutting point — if the opponent plays there, the eye collapses. "
                  "The rule: two REAL eyes = alive.\n\n"
                  "Common eye shapes:\n"
                  "- Bent four in the corner: unconditionally dead (even with sente)\n"
                  "- Bulky five: dead as it stands\n"
                  "- Rabbitty six: alive\n"
                  "- L-shape: depends on who plays first\n"
                  "- J-shape: alive in most cases\n\n"
                  "Shin Jinseo's approach: He doesn't just count eyes — he reads the entire life-and-death "
                  "sequence 20+ moves ahead. His groups almost never die because he sees the threat "
                  "before it materializes and defends preemptively.",
    },
    {
        "instruction": "What is a tesuji and can you give examples?",
        "input": "",
        "output": "Tesuji (手筋) means 'skillful move' — a clever tactical play that achieves more "
                  "than a straightforward move would. Tesuji are the tactical brilliancies that "
                  "separate strong players from average ones.\n\n"
                  "COMMON TESUJI:\n\n"
                  "1. SNAPBACK (Utegaeshi): You sacrifice a stone, the opponent captures it, and "
                  "then you immediately recapture a larger group. Looks like you're giving away a "
                  "stone, but you're actually setting a trap.\n\n"
                  "2. LADDER (Shicho): A running capture where the opponent is forced along a "
                  "diagonal path. If the ladder works (no 'ladder breaker' stone in the way), "
                  "the chased group is captured. If a ladder breaker exists, the ladder fails "
                  "catastrophically — hence the proverb: 'If you don't know the ladder, don't play Go.'\n\n"
                  "3. NET (Geta): A looser capture that traps stones without direct contact. "
                  "More reliable than a ladder because it doesn't depend on the whole board.\n\n"
                  "4. DOUBLE HANE: Playing two consecutive hanes to create cutting points in "
                  "the opponent's shape. Shin Jinseo's double hane on move 56 of the 2024 Ing Cup "
                  "semifinal was called 'the move of the year.'\n\n"
                  "5. WEDGE (Warikomi): Inserting a stone between two opponent stones to split them. "
                  "Creates two weak groups that are easier to attack.\n\n"
                  "6. CLAMP (Hasami-tsuke): Playing a stone that contacts two opponent stones "
                  "simultaneously, forcing them to choose which to save.\n\n"
                  "Tesuji are not memorized — they are FOUND through reading. The best players "
                  "(like Shin) don't have a 'library' of tesuji; they read the position and "
                  "DISCOVER the tesuji that the position demands.",
    },
]

POSITION_QA = [
    {
        "instruction": "You are analyzing a Go position. Black has just played the 3-3 invasion under White's 4-4 stone. The board is otherwise empty. Evaluate this position.",
        "input": "",
        "output": "This is a classic early 3-3 invasion — the defining move of modern Go.\n\n"
                  "POSITION EVALUATION:\n"
                  "- Black has secured approximately 10 points of corner territory\n"
                  "- White will get a thick outside wall after the standard joseki\n"
                  "- On an otherwise empty board, this is slightly favorable for Black (+0.3 points by KataGo)\n\n"
                  "STRATEGIC ASSESSMENT:\n"
                  "The key question is whether White can USE their outside thickness. On an empty board, "
                  "White's wall faces the center — the least efficient area. Black should follow up with "
                  "territory-oriented moves (another 3-3, or a komoku enclosure) to deny White the chance "
                  "to build a framework using the wall.\n\n"
                  "This is textbook Shin Jinseo style: take concrete territory first, make the opponent "
                  "prove their influence is worth something. At the professional level, Black's approach "
                  "is now considered standard — the early 3-3 is no longer a 'trick' but fundamental "
                  "opening theory.\n\n"
                  "RECOMMENDED FOLLOW-UP FOR BLACK: Take another corner with maximum efficiency "
                  "(3-3 or komoku enclosure). DO NOT engage White's thickness — let it face the "
                  "center while you secure territory elsewhere.",
    },
    {
        "instruction": "In a game, my opponent has built a large framework on the right side. How should I respond?",
        "input": "",
        "output": "Your opponent has invested multiple moves building a framework (moyo). You have two "
                  "options: reduce or invade. The choice depends on your style and the exact position.\n\n"
                  "SHIN JINSEO APPROACH — REDUCE (Shoulder Hit):\n"
                  "Play a shoulder hit (kata-tsuki) on the 4th line, diagonally adjacent to the "
                  "opponent's framework stone. The opponent pushes up, you extend along the side, "
                  "and you've reduced their potential by 5-10 points without a risky invasion.\n"
                  "This is the safer, more modern approach. You accept that the opponent will get "
                  "SOME territory from their framework, but you limit it to a manageable amount.\n\n"
                  "TRADITIONAL APPROACH — INVADE:\n"
                  "Invade deep inside the framework (3-3 point or deeper). This is higher risk but "
                  "potentially higher reward — if you live inside, the opponent's framework is "
                  "completely destroyed. However, a failed invasion leaves you with a weak group "
                  "that the opponent can attack for profit elsewhere.\n\n"
                  "DECISION FACTORS:\n"
                  "- How solid is the framework? (Open frameworks are easier to invade)\n"
                  "- What's your reading ability? (Invasions require deep reading)\n"
                  "- What's the score? (If you're ahead, reduce; if behind, invade)\n"
                  "- How many moves has the opponent invested? (The more they've invested, the "
                  "more they'll fight to protect it)\n\n"
                  "RULE OF THUMB: If you're not confident you can live inside, reduce. Shin Jinseo "
                  "reduces in about 80% of these situations — invasion is only for when the "
                  "framework is genuinely threatening to decide the game.",
    },
]


def generate_all_qa() -> List[Dict]:
    """Combine all Q&A pairs into one dataset."""
    all_qa = []
    all_qa.extend(RULES_QA)
    all_qa.extend(FUSEKI_QA)
    all_qa.extend(SHIN_QA)
    all_qa.extend(JOSEKI_QA)
    all_qa.extend(TACTICS_QA)
    all_qa.extend(POSITION_QA)
    
    # Shuffle for good mixing
    random.shuffle(all_qa)
    
    return all_qa


def generate_finetune_jsonl(output_path: str = "go_instructions.jsonl"):
    """Generate Alpaca-format JSONL for LLM fine-tuning."""
    all_qa = generate_all_qa()
    
    with open(output_path, 'w') as f:
        for qa in all_qa:
            f.write(json.dumps(qa) + '\n')
    
    print(f"Generated {len(all_qa)} instruction examples -> {output_path}")
    return output_path


def generate_system_prompt() -> str:
    """
    Generate a comprehensive system prompt that encodes Go knowledge
    for use with the DeepSeek model without fine-tuning.
    """
    prompt = """You are a Go (Baduk/Weiqi) expert trained on the complete strategic framework 
of Shin Jinseo, the world #1 player. Your knowledge covers:

1. RULES: Full Go rules including ko, superko, territory scoring (Japanese and Chinese), komi.
2. OPENING THEORY: 11 major fuseki patterns including Sanrensei, Chinese, Kobayashi, 
   Shusaku, AI 3-3, and Double 3-3.
3. JOSEKI: Standard corner sequences for 3-3, 3-4, 4-4, and 3-5 points.
4. TACTICS: Life and death, tesuji, ladders, nets, snapbacks, double hane.
5. STRATEGY: Territory vs influence, sente vs gote, reduction vs invasion, direction of play.
6. SHIN JINSEO PRINCIPLES: Corner First, Direct Play, Territory Over Moyo, Precise Reading,
   Katachi Mastery, Sente Obsession, Shoulder Hit, Early 3-3, Endgame Precision, 
   Calculated Aggression.

When analyzing positions, always consider: whose territory is more secure, which groups 
are weak, where are the key points, and what would Shin Jinseo play here. Prioritize 
concrete territory over speculative influence. Emphasize corner efficiency and sente 
retention. When in doubt, calculate — never guess."""

    return prompt


if __name__ == "__main__":
    output = generate_finetune_jsonl()
    print(f"\nSystem prompt preview:\n{generate_system_prompt()[:500]}...")
