import os
import pytest
import json

# Workaround for genlayer-test Windows PermissionError on os.unlink temp file
original_unlink = os.unlink
def safe_unlink(path, *args, **kwargs):
    try:
        original_unlink(path, *args, **kwargs)
    except PermissionError:
        pass
os.unlink = safe_unlink

@pytest.mark.direct
def test_successful_peer_challenge(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy("myogen_contract.py")

    # 1. Fund treasury
    with direct_vm.prank(direct_bob):
        direct_vm.value = 10 * 10**18
        contract.fund_treasury()

    # 2. Alice proposes initial term
    initial_url = "https://medical-dictionary.com/myoglobin"
    direct_vm.mock_web(initial_url, {
        "body": "Myoglobin is an oxygen-binding protein found in muscle tissue.",
        "method": "GET",
        "status": 200
    })

    initial_json = json.dumps({
        "is_accurate": True,
        "reasoning": "Accurate initial definition.",
        "term": "Myoglobin",
        "definition": "An oxygen-binding protein in muscle tissue.",
        "category": "Biochemistry",
        "detailed_explanation": "Stores oxygen for muscle contraction.",
        "key_facts": [],
        "related_terms": [],
        "clinical_relevance": "",
        "muscle_groups_involved": []
    })

    import genlayer.gl as gl
    original_prompt = getattr(gl.eq_principle, 'prompt_non_comparative', None)
    gl.eq_principle.prompt_non_comparative = lambda prompt, task, criteria: initial_json

    try:
        with direct_vm.prank(direct_alice):
            direct_vm.value = 1 * 10**18
            contract.propose_term("Myoglobin", "An oxygen-binding protein in muscle tissue.", initial_url)

        # Verify initial entry
        cached = json.loads(contract.get_cached_term("Myoglobin"))
        assert cached.get("explanation", {}).get("definition") == "An oxygen-binding protein in muscle tissue."

        # 3. Charlie challenges the definition with superior counter-evidence
        counter_url = "https://en.wikipedia.org/wiki/Myoglobin"
        direct_vm.mock_web(counter_url, {
            "body": "Myoglobin is an iron- and oxygen-binding hemoprotein found exclusively in cardiac and skeletal muscle.",
            "method": "GET",
            "status": 200
        })

        dispute_ruling = json.dumps({
            "challenger_wins": True,
            "adjudication_reasoning": "Counter-evidence is more rigorous and provides precise molecular classification (hemoprotein).",
            "definition": "An iron- and oxygen-binding hemoprotein found exclusively in cardiac and skeletal muscle tissue.",
            "detailed_explanation": "Functions as a primary oxygen reservoir in striated muscle fibers.",
            "category": "Molecular Physiology"
        })

        gl.eq_principle.prompt_non_comparative = lambda prompt, task, criteria: dispute_ruling

        charlie_str = direct_charlie.hex().lower()
        if not charlie_str.startswith("0x"):
            charlie_str = "0x" + charlie_str

        # Charlie stakes 1 GEN to challenge
        with direct_vm.prank(direct_charlie):
            direct_vm.value = 1 * 10**18
            contract.challenge_term(
                "Myoglobin",
                "An iron- and oxygen-binding hemoprotein found exclusively in cardiac and skeletal muscle tissue.",
                counter_url,
                "Definition omitted hemoprotein classification and striated muscle exclusivity."
            )

        # 4. Verify Charlie earned 2 GEN reward
        assert int(contract.pending_rewards.get(charlie_str, "0")) == 2 * 10**18

        # 5. Verify the dictionary was updated with the challenger's definition
        updated = json.loads(contract.get_cached_term("Myoglobin"))
        assert "hemoprotein" in updated.get("explanation", {}).get("definition")
        assert updated.get("disputed") is True
        assert updated.get("dispute_count") == 1
        assert updated.get("proposer") == charlie_str

        # 6. Charlie withdraws reward
        with direct_vm.prank(direct_charlie):
            direct_vm.value = 0
            contract.withdraw_rewards()

        assert int(contract.pending_rewards.get(charlie_str, "0")) == 0
        assert any("EthSend" in str(t) for t in direct_vm._traces)

    finally:
        if original_prompt:
            gl.eq_principle.prompt_non_comparative = original_prompt


@pytest.mark.direct
def test_failed_frivolous_peer_challenge(direct_deploy, direct_vm, direct_alice, direct_bob, direct_charlie):
    contract = direct_deploy("myogen_contract.py")

    # 1. Fund treasury
    with direct_vm.prank(direct_bob):
        direct_vm.value = 5 * 10**18
        contract.fund_treasury()

    # 2. Propose valid term (Alice)
    evidence_url = "https://medical-dictionary.com/actin"
    direct_vm.mock_web(evidence_url, {
        "body": "Actin is a globular multi-functional protein that forms microfilaments in muscle.",
        "method": "GET",
        "status": 200
    })

    initial_json = json.dumps({
        "is_accurate": True,
        "reasoning": "Valid actin definition.",
        "term": "Actin",
        "definition": "A globular protein that forms microfilaments in muscle.",
        "category": "Proteins",
        "detailed_explanation": "Interacts with myosin to produce muscle contraction.",
        "key_facts": [],
        "related_terms": [],
        "clinical_relevance": "",
        "muscle_groups_involved": []
    })

    import genlayer.gl as gl
    original_prompt = getattr(gl.eq_principle, 'prompt_non_comparative', None)
    gl.eq_principle.prompt_non_comparative = lambda prompt, task, criteria: initial_json

    try:
        with direct_vm.prank(direct_alice):
            direct_vm.value = 1 * 10**18
            contract.propose_term("Actin", "A globular protein that forms microfilaments in muscle.", evidence_url)

        # 3. Charlie attempts a frivolous dispute
        bogus_url = "https://fake-science-blog.com/actin"
        direct_vm.mock_web(bogus_url, {
            "body": "Actin is actually a carbohydrate stored in liver cells.",
            "method": "GET",
            "status": 200
        })

        frivolous_ruling = json.dumps({
            "challenger_wins": False,
            "adjudication_reasoning": "The counter-evidence claiming actin is a carbohydrate is biologically false and rejected.",
            "definition": "Actin is a carbohydrate.",
            "detailed_explanation": "",
            "category": "Carbohydrates"
        })

        gl.eq_principle.prompt_non_comparative = lambda prompt, task, criteria: frivolous_ruling

        charlie_str = direct_charlie.hex().lower()
        if not charlie_str.startswith("0x"):
            charlie_str = "0x" + charlie_str

        # Charlie stakes 1 GEN on the frivolous challenge
        with direct_vm.prank(direct_charlie):
            direct_vm.value = 1 * 10**18
            contract.challenge_term(
                "Actin",
                "Actin is actually a carbohydrate stored in liver cells.",
                bogus_url,
                "The current definition is wrong."
            )

        # 4. Verify Charlie earned 0 reward (frivolous challenge rejected)
        assert int(contract.pending_rewards.get(charlie_str, "0")) == 0

        # 5. Verify the definition was NOT altered
        cached = json.loads(contract.get_cached_term("Actin"))
        assert "globular protein" in cached.get("explanation", {}).get("definition")
        assert cached.get("disputed") is False

        # 6. Verify burn trace was issued
        assert any("EthSend" in str(t) for t in direct_vm._traces)

    finally:
        if original_prompt:
            gl.eq_principle.prompt_non_comparative = original_prompt
