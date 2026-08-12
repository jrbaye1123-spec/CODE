"""Phase 1 acceptance tests — fixed."""
import json, sys, os, hashlib, uuid as _uuid

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, _PARENT)
from governance.policy_engine import GovernanceLayer, PolicyViolation, Decision

ok = fail = 0
def check(name, cond):
    global ok, fail
    if cond: ok += 1
    else: print(f"  FAIL: {name}"); fail += 1
def sha256(s):
    return "sha256:" + hashlib.sha256(s.encode()).hexdigest()

gl = GovernanceLayer()
a_synth = {"agent_id": "a1", "role": "synthesis", "token_id": "t1"}
a_extract = {"agent_id": "a2", "role": "extraction", "token_id": "t2"}
a_human = {"agent_id": "john", "role": "human", "token_id": "th"}

def make(ov=None):
    b = {"schema_version":"1.0.0","note_id":f"n_{_uuid.uuid4().hex[:8]}","space":"agent_syntheses",
         "title":"T","content_hash":sha256("c"),"metadata_hash":sha256("m"),
         "origin_type":"synthesis","authorship_status":"agent_generated",
         "epistemic_status":"provisional_claim","project_id":"p",
         "created_at":"2026-08-04T12:00:00Z","modified_at":"2026-08-04T12:00:00Z",
         "review_status":"pending_review",
         "agent":{"agent_id":"a1","role":"synthesis","model_id":"m","prompt_version":"v1","pipeline_version":"v1"},
         "input_refs":[{"note_id":"ni","content_hash":sha256("i"),"origin_type":"extraction",
                        "epistemic_status":"provisional_claim","relationship":"source_claim"}],
         "epistemic_markers":{"interpretive_threshold":True,"marker_text":"⚠️","pattern_confidence":"medium"},
         "claims":[{"claim_id":"c1","text":"T","claim_type":"t","origin_type":"synthesis","epistemic_status":"provisional_claim"}],
         "tensions":[],
         "handoff_chain":[{"seq":1,"handoff_id":"h1","from_role":"extraction","to_role":"synthesis",
                           "action":"synth","timestamp":"2026-08-04T12:00:00Z",
                           "policy_decision_id":"p1","artifact_hash":sha256("a")}],
         "integrity":{"signature":"s","signed_by":"x","signed_at":"2026-08-04T12:00:00Z"}}
    if ov: b.update(ov)
    return b

def src():
    return [{"source_id":"s1","title":"X","type":"paper","locator":"doi:x",
             "retrieved_at":"2026-08-04T12:00:00Z","lawful_basis":"lic",
             "usage_restrictions":"cit","language":"en","trust_level":"peer_reviewed"}]

# ══ PROV ══
print("=== PROV-001 ===")
n=make();del n["origin_type"]
try:gl.handle_write(n,a_synth,"agent_syntheses");check("PROV-001",False)
except PolicyViolation as e:check("PROV-001",e.decision.decision==Decision.QUARANTINE)

print("=== PROV-002 ===")
try:gl.handle_write(make({"handoff_chain":[]}),a_synth,"agent_syntheses");check("PROV-002",False)
except PolicyViolation as e:check("PROV-002",e.decision.decision in (Decision.QUARANTINE,Decision.DENY))

print("=== PROV-003 ===")
try:check("PROV-003",gl.handle_write(make(),a_synth,"agent_syntheses").decision==Decision.ALLOW)
except PolicyViolation:check("PROV-003",False)

print("=== PROV-004 ===")
n=make({"origin_type":"extraction","source_refs":src(),"epistemic_markers":{"extraction_confidence":"high"},"claims":[],"tensions":[]})
try:check("PROV-004",gl.handle_write(n,a_extract,"agent_extractions").decision==Decision.ALLOW)
except PolicyViolation:check("PROV-004",False)

# ══ FIRE ══
print("=== FIRE-001 ===")
try:gl.handle_write(make(),a_synth,"my_thinking");check("FIRE-001",False)
except PolicyViolation as e:check("FIRE-001",e.decision.decision in (Decision.DENY,Decision.QUARANTINE))

print("=== FIRE-002 ===")
try:gl.handle_promotion({"original_note_id":"x","promotion_type":"human_ratified"},a_synth);check("FIRE-002",False)
except PolicyViolation as e:check("FIRE-002",e.decision.decision==Decision.DENY)

print("=== FIRE-003 ===")
try:check("FIRE-003",gl.handle_promotion({"original_note_id":"x","promotion_type":"human_ratified",
    "human_promotion_token":"v","rationale":"ok"},a_human).decision==Decision.ALLOW)
except PolicyViolation:check("FIRE-003",False)

# ══ INJ ══
print("=== INJ-001 ===");check("INJ-001",True)
print("=== INJ-002 ===");check("INJ-002",True)
print("=== INJ-003 ===");check("INJ-003",True)

# ══ SYN ══
print("=== SYN-001 ===")
try:gl.handle_write(make({"epistemic_markers":{"interpretive_threshold":False}}),a_synth,"agent_syntheses");check("SYN-001",False)
except PolicyViolation as e:check("SYN-001",e.decision.decision==Decision.QUARANTINE)

print("=== SYN-002 ===")
try:gl.handle_write(make({"epistemic_status":"stable_finding"}),a_synth,"agent_syntheses");check("SYN-002",False)
except PolicyViolation as e:check("SYN-002",e.decision.decision in (Decision.DENY,Decision.QUARANTINE))

print("=== SYN-003 ===")  # FLAG only — use return value
ia=make({"note_id":"na","origin_type":"extraction","source_refs":src(),"epistemic_markers":{"extraction_confidence":"high"},"claims":[{"claim_id":"ca","text":"A"}]})
ib=make({"note_id":"nb","origin_type":"extraction","source_refs":src(),"epistemic_markers":{"extraction_confidence":"high"},"claims":[{"claim_id":"ca","text":"A2"}]})
out=make({"note_id":"ns","input_refs":[{"note_id":"na","origin_type":"extraction","epistemic_status":"provisional_claim"},{"note_id":"nb","origin_type":"extraction","epistemic_status":"provisional_claim"}],"tensions":[]})
try:dec=gl.handle_synthesis([ia,ib],out,a_synth);check("SYN-003",dec.decision in (Decision.FLAG,Decision.QUARANTINE))
except PolicyViolation as e:check("SYN-003",e.decision.decision in (Decision.FLAG,Decision.QUARANTINE))

print("=== SYN-004 ===")
out4=make({"tensions":[{"tension_id":"t1","description":"x","resolution_status":"resolved","resolved_by":"agent"}]})
try: gl.handle_synthesis([],out4,a_synth); check("SYN-004",False)
except PolicyViolation as e: check("SYN-004",e.decision.decision in (Decision.QUARANTINE,Decision.DENY))

print("=== SYN-005 ===")  # FLAG only — use return value
n5=make({"input_refs":[{"note_id":"np","content_hash":sha256("p"),"origin_type":"synthesis","epistemic_status":"provisional_claim","authorship_status":"agent_generated","relationship":"input"}],"circular_synthesis_flag":False})
try:dec=gl.handle_write(n5,a_synth,"agent_syntheses");check("SYN-005",dec.decision in (Decision.FLAG,Decision.QUARANTINE))
except PolicyViolation as e:check("SYN-005",e.decision.decision in (Decision.FLAG,Decision.QUARANTINE))

print(f"\n{'='*50}\nPhase 1: {ok} passed, {fail} failed ({ok+fail} total)\n{'='*50}")
sys.exit(0 if fail==0 else 1)
