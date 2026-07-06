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
        caller = gl.message.sender_address

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

    @gl.public.write
    def study_term(self, term: str, web_data: str):
        caller = gl.message.sender_address
        term_clean = term.strip()
        term_lower = term_clean.lower()

        if term_lower == "":
            return

        if term_lower in self.all_terms_cache:
            cached = json.loads(self.all_terms_cache[term_lower])
            self._record_query(
                caller,
                term_clean,
                cached["explanation"],
                cached["graphical_data"]
            )
            return

        def build_prompt() -> str:
            prompt_str = f"""You are MYOGEN, an expert AI system specializing in muscle physiology,
anatomy, kinesiology, and sports science.

A student wants to understand this term:

"{term_clean}"

Here is frontend-provided context:

{web_data}

Return ONLY valid JSON using this exact structure:

{{
    "term": "{term_clean}",
    "definition": "A clear 2-3 sentence definition suitable for medical students",
    "category": "one of: Muscle Fiber Types | Muscle Mechanics | Anatomy & Physiology | Biochemistry | Neural Control | Pathology | Exercise Physiology",
    "detailed_explanation": "A thorough 4-6 sentence explanation covering the biological mechanism, function, and clinical relevance",
    "key_facts": [
        "Key fact 1",
        "Key fact 2",
        "Key fact 3",
        "Key fact 4",
        "Key fact 5"
    ],
    "related_terms": ["related_term_1", "related_term_2", "related_term_3"],
    "clinical_relevance": "1-2 sentences about clinical or athletic relevance",
    "muscle_groups_involved": ["muscle1", "muscle2"],
    "visualization_type": "one of: fiber_diagram | contraction_cycle | cross_section | neural_pathway | biochemical_cycle | joint_mechanics | cellular_diagram",
    "color_theme": "one of: red-orange | blue-cyan | green-teal | purple-violet | gold-amber"
}}

If the term is NOT related to muscle physiology, anatomy, kinesiology, or exercise science, return exactly this JSON:

{{
    "term": "{term_clean}",
    "definition": "this is not a muscle term",
    "category": "Out of Scope",
    "detailed_explanation": "MYOGEN specializes exclusively in muscle physiology, anatomy, kinesiology, and related sports science. Please enter a relevant anatomical or physiological term.",
    "key_facts": [],
    "related_terms": ["actin", "myosin", "sarcomere", "motor neuron", "muscle fiber"],
    "clinical_relevance": "N/A",
    "muscle_groups_involved": [],
    "visualization_type": "fiber_diagram",
    "color_theme": "red-orange"
}}"""
            return gl.nondet.exec_prompt(prompt_str)

        explanation_result = gl.eq_principle.prompt_non_comparative(
            build_prompt,
            task="Analyze the medical term and return only the requested JSON object.",
            criteria="""
            The response must be valid JSON.
            The response must match the exact requested structure.
            The explanation must be medically accurate.
            If the term is outside muscle physiology, anatomy, kinesiology, or exercise science, classify it as Out of Scope.
            """
        )

        try:
            explanation_data = json.loads(explanation_result)
        except Exception:
            explanation_data = {
                "term": term_clean,
                "definition": f"Analysis of '{term_clean}' in the context of muscle physiology.",
                "category": "General",
                "detailed_explanation": explanation_result if isinstance(explanation_result, str) else "Explanation processed by GenLayer validators.",
                "key_facts": [
                    "Analyzed by GenLayer AI validators",
                    "Consensus reached through GenLayer execution"
                ],
                "related_terms": [],
                "clinical_relevance": "Consult a qualified medical professional for clinical advice.",
                "muscle_groups_involved": [],
                "visualization_type": "fiber_diagram",
                "color_theme": "red-orange"
            }

        graphical_data = self._generate_graphical_data(explanation_data)

        self.all_terms_cache[term_lower] = json.dumps({
            "explanation": explanation_data,
            "graphical_data": graphical_data,
            "validated_at": self._safe_timestamp(),
            "validator_consensus": True
        })

        current_popular = json.loads(self.popular_terms_list)
        if term_clean not in current_popular:
            current_popular.append(term_clean)
            self.popular_terms_list = json.dumps(current_popular)

        self._record_query(
            caller,
            term_clean,
            explanation_data,
            graphical_data
        )

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
