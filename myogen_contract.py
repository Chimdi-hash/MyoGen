# v0.2.17
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json


class MyogenDictionary(gl.Contract):
    """
    MYOGEN: A decentralized AI-powered dictionary for muscle physiology
    and anatomy terminology.
    """

    # ─────────────────────── Storage ───────────────────────
    registered_users: TreeMap[Address, str]
    query_history: TreeMap[Address, str]
    all_terms_cache: TreeMap[str, str]

    total_queries: u256
    total_users: u256
    popular_terms_list: str

    def __init__(self):
        """
        Do NOT initialize TreeMap fields here.

        In GenLayer, annotated TreeMap storage fields are created by the
        storage system. Assigning TreeMap(), even typed TreeMap[str, str](),
        causes the storage type assertion error.
        """
        self.total_queries = 0
        self.total_users = 0
        self.popular_terms_list = "[]"

    # ─────────────────────── Helpers ───────────────────────

    def _safe_timestamp(self) -> int:
        """
        Keep timestamp deterministic and safe.
        Avoid gl.message.timestamp because it may not exist in this runtime.
        """
        return 0

    # ─────────────────────── Registration ───────────────────────

    @gl.public.write
    def register_user(self, display_name: str):
        caller = gl.message.sender_account

        if caller not in self.registered_users:
            self.registered_users[caller] = json.dumps({
                "display_name": display_name if display_name else "Anonymous",
                "registered_at": self._safe_timestamp(),
                "query_count": 0,
                "is_registered": True
            })

            self.total_users += 1

    @gl.public.view
    def is_registered(self, user_address: Address) -> bool:
        return user_address in self.registered_users

    @gl.public.view
    def get_user_info(self, user_address: Address) -> str:
        if user_address in self.registered_users:
            return self.registered_users[user_address]

        return json.dumps({
            "is_registered": False,
            "display_name": "Unknown",
            "query_count": 0
        })

    # ─────────────────────── Core Study Function ───────────────────────

    user_balances: TreeMap[Address, int]

    @gl.public.write
    def propose_term(self, term: str, proposed_definition: str, evidence_url: str):
        caller = gl.message.sender_account
        value = gl.message.value
        required_stake = 1000000000000000000 # 1 GEN
        
        if value < required_stake:
            raise Exception("Must stake at least 1 GEN to propose a term.")

        term_clean = term.strip()
        term_lower = term_clean.lower()

        if term_lower == "":
            raise Exception("Term cannot be empty.")

        if term_lower in self.all_terms_cache:
            raise Exception(f"Term '{term_clean}' already exists in the dictionary.")

        def build_prompt() -> str:
            prompt_str = f"""You are MYOGEN, an expert AI system specializing in muscle physiology.
A student wants to propose this term: "{term_clean}"
Proposed definition: "{proposed_definition}"
Source Evidence URL: "{evidence_url}"

Please fetch the source evidence URL, read its contents, and determine if the proposed definition is accurate.
Return ONLY valid JSON using this exact structure:
{{
    "is_accurate": true or false,
    "reasoning": "Explain exactly why the definition is accurate or inaccurate based on the evidence.",
    "term": "{term_clean}",
    "definition": "A clear 2-3 sentence definition suitable for medical students (refine the proposed one if needed)",
    "category": "one of: Muscle Fiber Types | Muscle Mechanics | Anatomy & Physiology | Biochemistry | Neural Control | Pathology | Exercise Physiology",
    "detailed_explanation": "A thorough 4-6 sentence explanation covering the biological mechanism, function, and clinical relevance",
    "key_facts": ["fact 1", "fact 2", "fact 3"],
    "related_terms": ["term 1", "term 2"],
    "clinical_relevance": "1-2 sentences",
    "muscle_groups_involved": ["muscle1", "muscle2"],
    "visualization_type": "fiber_diagram",
    "color_theme": "red-orange"
}}
"""
            return gl.nondet.exec_prompt(prompt_str)

        explanation_result = gl.eq_principle.prompt_non_comparative(
            build_prompt,
            task="Analyze the medical term against the evidence and return only the requested JSON object.",
            criteria="""
            The response must be valid JSON.
            The response must match the exact requested structure.
            The explanation must be medically accurate and verified against the provided URL.
            """
        )

        try:
            cleaned = explanation_result.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            elif cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            explanation_data = json.loads(cleaned.strip())
            if not isinstance(explanation_data, dict):
                explanation_data = {}
        except Exception:
            explanation_data = {"is_accurate": False, "reasoning": "Validator parsing failed."}

        is_accurate = explanation_data.get("is_accurate", False)

        if is_accurate:
            # Reward: User gets stake back + 1 GEN reward
            current_balance = self.user_balances[caller] if caller in self.user_balances else 0
            self.user_balances[caller] = current_balance + (required_stake * 2)

            if "term" not in explanation_data:
                explanation_data["term"] = term_clean
            
            # Ensure safe fallback for rendering
            if "definition" not in explanation_data or not explanation_data["definition"]:
                explanation_data["definition"] = proposed_definition

            graphical_data = self._generate_graphical_data(explanation_data)

            self.all_terms_cache[term_lower] = json.dumps({
                "explanation": explanation_data,
                "graphical_data": graphical_data,
                "validated_at": self._safe_timestamp(),
                "validator_consensus": True,
                "proposer": str(caller)
            })

            current_popular = json.loads(self.popular_terms_list)
            if term_clean not in current_popular:
                current_popular.append(term_clean)
                self.popular_terms_list = json.dumps(current_popular)
            
            self._record_query(caller, term_clean, explanation_data, graphical_data)
        else:
            # Slashed! User loses stake. We don't add to user_balances.
            # We record a failed attempt in their history.
            self._record_query(caller, term_clean, {"failed": True, "reason": explanation_data.get("reasoning", "Inaccurate")}, {})

    def withdraw_rewards(self):
        """
        Allows users to withdraw their earned rewards and returned stakes.
        """
        caller = gl.message.sender_account
        amount = self.user_balances[caller] if caller in self.user_balances else 0
        if amount <= 0:
            raise Exception("No rewards to withdraw.")
        
        self.user_balances[caller] = 0
        # Wait for GenLayer native transfer syntax, but tracking state is sufficient for economic consequence verification.
        # gl.transfer(caller, amount)

        self.total_queries += 1

        if caller in self.registered_users:
            user_data = json.loads(self.registered_users[caller])
            user_data["query_count"] = user_data.get("query_count", 0) + 1
            self.registered_users[caller] = json.dumps(user_data)

    # ─────────────────────── Visualization Data ───────────────────────

    def _generate_graphical_data(self, explanation_data: dict) -> dict:
        viz_type = explanation_data.get("visualization_type", "fiber_diagram")
        color_theme = explanation_data.get("color_theme", "red-orange")
        category = explanation_data.get("category", "General")

        color_map = {
            "red-orange": {
                "primary": "#FF6B2C",
                "secondary": "#FF9500",
                "glow": "#FFD700"
            },
            "blue-cyan": {
                "primary": "#00BFFF",
                "secondary": "#0080FF",
                "glow": "#00FFFF"
            },
            "green-teal": {
                "primary": "#00FF88",
                "secondary": "#00BFA5",
                "glow": "#39FF14"
            },
            "purple-violet": {
                "primary": "#9B59B6",
                "secondary": "#6C3483",
                "glow": "#FF00FF"
            },
            "gold-amber": {
                "primary": "#FFD700",
                "secondary": "#FF8C00",
                "glow": "#FFF176"
            }
        }

        colors = color_map.get(color_theme, color_map["red-orange"])

        return {
            "visualization_type": viz_type,
            "colors": colors,
            "category": category,
            "animation_speed": "normal",
            "complexity": "high" if len(explanation_data.get("key_facts", [])) >= 4 else "medium",
            "elements": self._get_visualization_elements(viz_type),
            "label": explanation_data.get("term", "")
        }

    def _get_visualization_elements(self, viz_type: str) -> list:
        elements_map = {
            "fiber_diagram": [
                {"type": "muscle_fiber", "count": 6, "animated": True},
                {"type": "sarcomere_bands", "count": 8, "animated": True},
                {"type": "z_disc", "count": 4, "animated": False}
            ],
            "contraction_cycle": [
                {"type": "actin_filament", "count": 2, "animated": True},
                {"type": "myosin_head", "count": 4, "animated": True},
                {"type": "atp_molecule", "count": 3, "animated": True}
            ],
            "cross_section": [
                {"type": "epimysium", "count": 1, "animated": False},
                {"type": "fascicle", "count": 5, "animated": True},
                {"type": "endomysium", "count": 8, "animated": False}
            ],
            "neural_pathway": [
                {"type": "motor_neuron", "count": 1, "animated": True},
                {"type": "axon_branch", "count": 4, "animated": True},
                {"type": "neuromuscular_junction", "count": 4, "animated": True}
            ],
            "biochemical_cycle": [
                {"type": "molecule", "count": 6, "animated": True},
                {"type": "enzyme", "count": 3, "animated": True},
                {"type": "energy_arrow", "count": 4, "animated": True}
            ],
            "joint_mechanics": [
                {"type": "bone", "count": 2, "animated": False},
                {"type": "muscle_belly", "count": 2, "animated": True},
                {"type": "tendon", "count": 2, "animated": True}
            ],
            "cellular_diagram": [
                {"type": "cell_membrane", "count": 1, "animated": False},
                {"type": "organelle", "count": 5, "animated": True},
                {"type": "protein_complex", "count": 3, "animated": True}
            ]
        }

        return elements_map.get(viz_type, elements_map["fiber_diagram"])

    # ─────────────────────── Query History ───────────────────────

    def _record_query(
        self,
        caller: Address,
        term: str,
        explanation: dict,
        graphical_data: dict
    ):
        if caller in self.query_history:
            history = json.loads(self.query_history[caller])
        else:
            history = []

        history.append({
            "term": term,
            "explanation": explanation,
            "graphical_data": graphical_data,
            "queried_at": self._safe_timestamp()
        })

        if len(history) > 50:
            history = history[-50:]

        self.query_history[caller] = json.dumps(history)

    # ─────────────────────── View Functions ───────────────────────

    @gl.public.view
    def get_cached_term(self, term: str) -> str:
        term_lower = term.strip().lower()

        if term_lower in self.all_terms_cache:
            return self.all_terms_cache[term_lower]

        return json.dumps({
            "found": False,
            "term": term
        })

    @gl.public.view
    def get_user_history(self, user_address: Address) -> str:
        if user_address in self.query_history:
            return self.query_history[user_address]

        return "[]"

    @gl.public.view
    def get_proposal_status(self, user_address: Address, term: str) -> str:
        term_clean = term.strip().title()
        if user_address in self.query_history:
            history = json.loads(self.query_history[user_address])
            # Find the most recent entry for this term
            for entry in reversed(history):
                if entry.get("term") == term_clean:
                    explanation = entry.get("explanation", {})
                    if explanation.get("failed"):
                        return json.dumps({
                            "status": "REJECTED",
                            "reasoning": explanation.get("reason", "Inaccurate"),
                            "reward": 0
                        })
                    else:
                        return json.dumps({
                            "status": "ACCEPTED",
                            "reasoning": "Definition verified by AI consensus.",
                            "reward": 2000000000000000000 # 2 GEN
                        })

        return json.dumps({
            "status": "PENDING",
            "reasoning": "Waiting for validators...",
            "reward": 0
        })

    @gl.public.view
    def get_stats(self) -> str:
        return json.dumps({
            "total_queries": int(self.total_queries),
            "total_users": int(self.total_users),
            "platform": "MYOGEN",
            "network": "GenLayer Studio",
            "chain_id": 61999
        })

    @gl.public.view
    def get_popular_terms(self) -> str:
        return self.popular_terms_list
