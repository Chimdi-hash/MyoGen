# v0.3.1 — Stable reward tracking (no gl.transfer dependency)
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json


class MyogenDictionary(gl.Contract):
    """
    MYOGEN: Decentralized AI-powered muscle physiology dictionary.

    ECONOMIC MODEL:
    - Stake 1 GEN per proposal.
    - ACCEPTED  → earn 2 GEN (tracked in pending_rewards, withdrawn via claim_reward).
    - REJECTED  → 1 GEN slashed to contract treasury.
    All address keys are normalised to lower-case to avoid checksum mismatches.
    """

    # ── Storage ───────────────────────────────────────────────────
    query_history:   TreeMap[str, str]   # lower(address) → JSON history list
    all_terms_cache: TreeMap[str, str]   # lower(term)    → JSON term data
    pending_rewards: TreeMap[str, str]   # lower(address) → wei amount string
    treasury:        u256                # accumulated slashed GEN (wei)
    total_queries:   u256
    popular_terms_list: str

    def __init__(self):
        self.treasury        = 0
        self.total_queries   = 0
        self.popular_terms_list = "[]"

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _addr(a) -> str:
        """Return a normalised (lower-case) string for any address-like value."""
        return str(a).lower()

    # ── Core Staking + AI Validation ─────────────────────────────

    @gl.public.write.payable
    def propose_term(self, term: str, proposed_definition: str, evidence_url: str):
        caller    = gl.message.sender_address
        stake     = gl.message.value
        ONE_GEN   = 1000000000000000000      # 1e18 wei

        if stake < ONE_GEN:
            raise Exception("Must stake at least 1 GEN.")

        term_clean = term.strip()
        term_lower = term_clean.lower()

        if not term_lower:
            raise Exception("Term cannot be empty.")

        if term_lower in self.all_terms_cache:
            raise Exception(
                f"'{term_clean}' is already in the MYOGEN dictionary. "
                "Use a different term to earn a reward."
            )

        # ── AI validation ──
        def build_prompt() -> str:
            return gl.nondet.exec_prompt(
                f"""You are a STRICT scientific fact-checker for the MYOGEN muscle physiology dictionary.
Your job is to REJECT incorrect definitions. Be extremely critical.

Term proposed: "{term_clean}"
Proposed definition: "{proposed_definition}"
Evidence URL: "{evidence_url}"

STEP 1 — Fetch the evidence URL and read it carefully.
STEP 2 — Find what the source says about "{term_clean}".
STEP 3 — Compare the proposed definition against the source facts.
STEP 4 — Apply REJECTION CRITERIA below.

MANDATORY REJECTION RULES (set is_accurate=false if ANY apply):
- The definition describes the WRONG biological function (e.g. calls a structural protein a "digestive enzyme")
- The definition places the term in the WRONG organ system (e.g. digestive/pancreas when it should be muscular)
- The definition mentions WRONG molecule types (e.g. enzyme vs protein, actin vs myosin)
- The definition is factually about a COMPLETELY DIFFERENT thing than what the evidence URL describes
- The definition contains made-up or hallucinated information not supported by the source
- The term has nothing to do with muscle physiology or anatomy

EXAMPLE OF REQUIRED REJECTION:
- Term: "Titin", Proposed: "a digestive enzyme produced in the pancreas" → is_accurate: false
  Because: Titin is the largest structural protein in muscle sarcomeres, NOT a digestive enzyme.

Only set is_accurate=true if the proposed definition correctly describes the term as shown in the evidence URL.

Return ONLY a valid JSON object (no markdown, no extra text):
{{
    "is_accurate": false,
    "reasoning": "The evidence URL states that '{term_clean}' is [quote exact description from source]. The proposed definition incorrectly states [specific wrong claim]. This is factually incorrect and does not match the source.",
    "term": "{term_clean}",
    "definition": "Correct definition based on the evidence URL (only fill if is_accurate=true, otherwise leave as empty string).",
    "category": "Anatomy & Physiology",
    "detailed_explanation": "Fill only if is_accurate=true, otherwise empty string.",
    "key_facts": [],
    "related_terms": [],
    "clinical_relevance": "",
    "muscle_groups_involved": []
}}"""
            )

        result_str = gl.eq_principle.prompt_non_comparative(
            build_prompt,
            task="Verify the proposed muscle physiology definition using the evidence URL.",
            criteria=(
                "The leader's response is a valid JSON object "
                "(starts with '{' and ends with '}') "
                "containing at least the keys 'is_accurate' and 'reasoning'."
            ),
        )

        # ── Parse AI output ──
        try:
            cleaned = result_str.strip()
            if "```" in cleaned:
                s = cleaned.find("{"); e = cleaned.rfind("}") + 1
                if s >= 0 and e > s:
                    cleaned = cleaned[s:e]
            data = json.loads(cleaned)
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}

        is_accurate = bool(data.get("is_accurate", False))

        safe_exp = {
            "term":                  data.get("term",                 term_clean),
            "definition":            data.get("definition",           proposed_definition),
            "category":              data.get("category",             "General"),
            "detailed_explanation":  data.get("detailed_explanation", ""),
            "clinical_relevance":    data.get("clinical_relevance",   ""),
            "reasoning":             data.get("reasoning",            ""),
            "key_facts":             data.get("key_facts",            []) if isinstance(data.get("key_facts"),    list) else [],
            "related_terms":         data.get("related_terms",        []) if isinstance(data.get("related_terms"), list) else [],
            "muscle_groups_involved":data.get("muscle_groups_involved",[]) if isinstance(data.get("muscle_groups_involved"), list) else [],
            "visualization_type":    "fiber_diagram",
            "color_theme":           "red-orange",
        }

        caller_str = self._addr(caller)
        stake_int  = int(stake)

        if is_accurate:
            # ── Credit 2x stake to pending_rewards ──
            prev = int(self.pending_rewards[caller_str]) if caller_str in self.pending_rewards else 0
            self.pending_rewards[caller_str] = str(prev + stake_int * 2)

            self.all_terms_cache[term_lower] = json.dumps({
                "explanation":        safe_exp,
                "validator_consensus": True,
                "proposer":           caller_str,
            })

            try:
                pop = json.loads(self.popular_terms_list)
                if not isinstance(pop, list): pop = []
            except Exception:
                pop = []
            if term_clean not in pop:
                pop.append(term_clean)
                self.popular_terms_list = json.dumps(pop)

            self._record(caller_str, term_lower, term_clean,
                         safe_exp.get("definition", ""),
                         safe_exp.get("reasoning", ""), True)
        else:
            self.treasury += stake
            self._record(caller_str, term_lower, term_clean,
                         proposed_definition,
                         data.get("reasoning", "Definition did not match evidence."), False)

        self.total_queries += 1

    # ── View: pending reward balance ─────────────────────────────

    @gl.public.view
    def get_pending_reward(self, user_address: str) -> str:
        key = user_address.strip().lower()
        return self.pending_rewards[key] if key in self.pending_rewards else "0"

    # ── Internal ──────────────────────────────────────────────────

    def _record(self, caller_str: str, term_lower: str, term_display: str,
                definition: str, reasoning: str, accepted: bool):
        try:
            hist = json.loads(self.query_history[caller_str]) if caller_str in self.query_history else []
            if not isinstance(hist, list): hist = []
        except Exception:
            hist = []
        hist.append({"term": term_display, "term_lower": term_lower,
                     "definition": definition, "reasoning": reasoning,
                     "accepted": accepted})
        if len(hist) > 50: hist = hist[-50:]
        self.query_history[caller_str] = json.dumps(hist)

    # ── Views ─────────────────────────────────────────────────────

    @gl.public.view
    def get_cached_term(self, term: str) -> str:
        k = term.strip().lower()
        return self.all_terms_cache[k] if k in self.all_terms_cache else json.dumps({"found": False})

    @gl.public.view
    def get_user_history(self, user_address: str) -> str:
        k = user_address.strip().lower()
        return self.query_history[k] if k in self.query_history else "[]"

    @gl.public.view
    def get_proposal_status(self, user_address: str, term: str) -> str:
        k = user_address.strip().lower()
        tl = term.strip().lower()
        if k in self.query_history:
            try:
                hist = json.loads(self.query_history[k])
                for e in reversed(hist):
                    if e.get("term_lower") == tl:
                        if e.get("accepted"):
                            return json.dumps({"status": "ACCEPTED",
                                               "reasoning": e.get("reasoning", ""),
                                               "reward": 2})
                        return json.dumps({"status": "REJECTED",
                                           "reasoning": e.get("reasoning", ""),
                                           "reward": 0})
            except Exception:
                pass
        return json.dumps({"status": "PENDING", "reasoning": "Not yet processed.", "reward": 0})

    @gl.public.view
    def get_treasury_balance(self) -> str:
        return str(int(self.treasury))

    @gl.public.view
    def get_stats(self) -> str:
        return json.dumps({"total_queries": int(self.total_queries),
                           "platform": "MYOGEN", "network": "GenLayer Studio",
                           "treasury_wei": int(self.treasury)})

    @gl.public.view
    def get_popular_terms(self) -> str:
        return self.popular_terms_list
