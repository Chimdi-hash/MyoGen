"""Integration tests for MyoGen withdrawal logic.

Run with: gltest test_myogen_withdraw.py -v -s
"""

import pytest
import json
from gltest import get_contract_factory
from gltest.helpers import load_fixture
from gltest.assertions import tx_execution_succeeded

@pytest.mark.integration
def deploy_contract():
    factory = get_contract_factory("MyogenDictionary")
    contract = factory.deploy()
    return contract

@pytest.mark.integration
def test_collateralized_withdrawal():
    contract = load_fixture(deploy_contract)
    
    # 1. Fund the treasury to ensure fully collateralized rewards
    fund_result = contract.fund_treasury(
        args=[],
        value=5 * 10**18
    )
    assert tx_execution_succeeded(fund_result)
    
    # 2. Submit a valid proposal (stake 1 GEN)
    propose_result = contract.propose_term(
        args=[
            "Myosin",
            "A superfamily of motor proteins best known for their roles in muscle contraction and in a wide range of other motility processes in eukaryotes.",
            "https://en.wikipedia.org/wiki/Myosin"
        ],
        value=1 * 10**18
    )
    assert tx_execution_succeeded(propose_result)
    
    # 3. Check pending rewards - should be 2 GEN (stake * 2)
    caller_address = propose_result.sender
    pending_rewards = int(contract.get_pending_reward(args=[caller_address]))
    assert pending_rewards == 2 * 10**18
    
    # 4. Withdraw the rewards
    withdraw_result = contract.withdraw_rewards(
        args=[],
        from_address=caller_address
    )
    assert tx_execution_succeeded(withdraw_result)
    
    # 5. Verify pending balance is now 0
    final_pending = int(contract.get_pending_reward(args=[caller_address]))
    assert final_pending == 0
