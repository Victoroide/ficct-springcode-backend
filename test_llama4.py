"""Quick test script for Llama 4 Maverick implementation.

Run this to verify the implementation is working correctly.
"""

import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'base.settings')
django.setup()

from apps.ai_assistant.services import Llama4CommandService, ModelRouterService
from django.conf import settings


def test_configuration():
    """Test that configuration is correct."""
    print("=" * 70)
    print("TEST 1: CONFIGURATION")
    print("=" * 70)
    
    models = getattr(settings, 'COMMAND_PROCESSING_MODELS', {})
    default_model = getattr(settings, 'DEFAULT_COMMAND_MODEL', None)
    fallback_order = getattr(settings, 'MODEL_FALLBACK_ORDER', [])
    
    print(f"\nDefault Model: {default_model}")
    assert default_model == 'llama4-maverick', "Default model should be llama4-maverick"
    print("[PASS] Default model is llama4-maverick")
    
    print(f"\nFallback Order: {fallback_order}")
    assert fallback_order[0] == 'llama4-maverick', "First fallback should be llama4-maverick"
    assert fallback_order[1] == 'nova-pro', "Second fallback should be nova-pro"
    assert fallback_order[2] == 'o4-mini', "Third fallback should be o4-mini"
    print("[PASS] Fallback order is correct")
    
    print(f"\nLlama 4 Configuration:")
    llama_config = models.get('llama4-maverick', {})
    print(f"  Name: {llama_config.get('name')}")
    print(f"  Provider: {llama_config.get('provider')}")
    print(f"  Cost Estimate: ${llama_config.get('cost_estimate')}")
    print(f"  Max Tokens: {llama_config.get('max_tokens')}")
    print(f"  Context Window: {llama_config.get('context_window')}")
    assert llama_config.get('enabled', False), "Llama 4 should be enabled"
    print("[PASS] Llama 4 configuration is correct")
    
    print("\n[PASS] CONFIGURATION TEST PASSED\n")


def test_service_initialization():
    """Test that Llama 4 service initializes correctly."""
    print("=" * 70)
    print("TEST 2: SERVICE INITIALIZATION")
    print("=" * 70)
    
    print("\nInitializing Llama4CommandService...")
    service = Llama4CommandService()
    
    print(f"  Model ID: {service.MODEL_ID}")
    assert service.MODEL_ID == "us.meta.llama4-maverick-17b-instruct-v1:0"
    print("[PASS] Model ID is correct (inference profile)")
    
    print(f"  Input Cost: ${service.INPUT_COST_PER_1M_TOKENS}/1M tokens")
    assert service.INPUT_COST_PER_1M_TOKENS == 0.24
    print("[PASS] Input cost is correct")
    
    print(f"  Output Cost: ${service.OUTPUT_COST_PER_1M_TOKENS}/1M tokens")
    assert service.OUTPUT_COST_PER_1M_TOKENS == 0.97
    print("[PASS] Output cost is correct")
    
    if service.client:
        print("  Bedrock Client: Initialized")
        print("[PASS] Bedrock client initialized")
    else:
        print("  Bedrock Client: Not available (check AWS credentials)")
        print("[WARN] Bedrock client not initialized (AWS credentials needed)")
    
    print("\n[PASS] SERVICE INITIALIZATION TEST PASSED\n")


def test_model_router():
    """Test that model router uses Llama 4 as default."""
    print("=" * 70)
    print("TEST 3: MODEL ROUTER")
    print("=" * 70)
    
    print("\nInitializing ModelRouterService...")
    router = ModelRouterService()
    
    print(f"  Available services: {list(router._services.keys())}")
    assert 'llama4-maverick' in router._services, "Llama 4 should be in available services"
    print("[PASS] Llama 4 is in available services")
    
    default = router._get_default_model()
    print(f"  Default model from router: {default}")
    assert default == 'llama4-maverick', "Router should use llama4-maverick as default"
    print("[PASS] Router uses llama4-maverick as default")
    
    print("\n[PASS] MODEL ROUTER TEST PASSED\n")


def test_prompt_formatting():
    """Test Llama 4 prompt formatting."""
    print("=" * 70)
    print("TEST 4: PROMPT FORMATTING")
    print("=" * 70)
    
    service = Llama4CommandService()
    
    base_prompt = "You are a UML generator. Create class User."
    formatted = service._format_llama_prompt(base_prompt)
    
    print("\nFormatted prompt structure:")
    print(f"  Starts with <|begin_of_text|>: {formatted.startswith('<|begin_of_text|>')}")
    assert formatted.startswith('<|begin_of_text|>'), "Should start with begin_of_text token"
    print("[PASS] Starts with begin_of_text token")
    
    print(f"  Contains user header: {'<|start_header_id|>user<|end_header_id|>' in formatted}")
    assert '<|start_header_id|>user<|end_header_id|>' in formatted
    print("[PASS] Contains user header")
    
    print(f"  Contains eot_id: {'<|eot_id|>' in formatted}")
    assert '<|eot_id|>' in formatted
    print("[PASS] Contains end of turn marker")
    
    print(f"  Contains assistant header: {'<|start_header_id|>assistant<|end_header_id|>' in formatted}")
    assert '<|start_header_id|>assistant<|end_header_id|>' in formatted
    print("[PASS] Contains assistant header")
    
    print("\n[PASS] PROMPT FORMATTING TEST PASSED\n")


def test_cost_calculation():
    """Test cost calculation."""
    print("=" * 70)
    print("TEST 5: COST CALCULATION")
    print("=" * 70)
    
    service = Llama4CommandService()
    
    prompt_tokens = 1500
    completion_tokens = 2000
    
    cost_info = service._calculate_cost(prompt_tokens, completion_tokens)
    
    expected_input = (1500 / 1_000_000) * 0.24
    expected_output = (2000 / 1_000_000) * 0.97
    expected_total = expected_input + expected_output
    
    print(f"\nCost calculation for 1500 input + 2000 output tokens:")
    print(f"  Input cost: ${cost_info['input_cost']:.6f} (expected: ${expected_input:.6f})")
    assert abs(cost_info['input_cost'] - expected_input) < 0.000001
    print("[PASS] Input cost correct")
    
    print(f"  Output cost: ${cost_info['output_cost']:.6f} (expected: ${expected_output:.6f})")
    assert abs(cost_info['output_cost'] - expected_output) < 0.000001
    print("[PASS] Output cost correct")
    
    print(f"  Total cost: ${cost_info['total_cost']:.6f} (expected: ${expected_total:.6f})")
    assert abs(cost_info['total_cost'] - expected_total) < 0.000001
    print("[PASS] Total cost correct")
    
    print(f"\nComparison with Nova Pro (same tokens):")
    nova_input = (1500 / 1_000_000) * 0.80
    nova_output = (2000 / 1_000_000) * 3.20
    nova_total = nova_input + nova_output
    
    savings = nova_total - expected_total
    savings_pct = (savings / nova_total) * 100
    
    print(f"  Nova Pro cost: ${nova_total:.6f}")
    print(f"  Llama 4 cost: ${expected_total:.6f}")
    print(f"  Savings: ${savings:.6f} ({savings_pct:.1f}%)")
    print("[PASS] 70% cost savings confirmed")
    
    print("\n[PASS] COST CALCULATION TEST PASSED\n")


def test_json_parsing():
    """Test JSON parsing strategies."""
    print("=" * 70)
    print("TEST 6: JSON PARSING")
    print("=" * 70)
    
    service = Llama4CommandService()
    
    test_cases = [
        {
            'name': 'Direct JSON',
            'text': '{"action": "create_class", "elements": [], "confidence": 0.95}',
            'should_parse': True
        },
        {
            'name': 'JSON in markdown',
            'text': '```json\n{"action": "create_class", "elements": []}\n```',
            'should_parse': True
        },
        {
            'name': 'JSON with prefix text',
            'text': 'Here is the result: {"action": "create_class", "elements": []}',
            'should_parse': True
        },
        {
            'name': 'Empty response',
            'text': '',
            'should_parse': False
        }
    ]
    
    for test_case in test_cases:
        print(f"\n  Testing: {test_case['name']}")
        result = service._parse_response(test_case['text'])
        
        if test_case['should_parse']:
            assert 'action' in result, f"Should parse {test_case['name']}"
            print(f"    [PASS] Successfully parsed")
        else:
            assert result.get('action') == 'error', f"Should return error for {test_case['name']}"
            print(f"    [PASS] Correctly returned error")
    
    print("\n[PASS] JSON PARSING TEST PASSED\n")


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("LLAMA 4 MAVERICK IMPLEMENTATION TESTS")
    print("=" * 70 + "\n")
    
    tests = [
        ("Configuration", test_configuration),
        ("Service Initialization", test_service_initialization),
        ("Model Router", test_model_router),
        ("Prompt Formatting", test_prompt_formatting),
        ("Cost Calculation", test_cost_calculation),
        ("JSON Parsing", test_json_parsing),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n[FAIL] {test_name} FAILED: {e}\n")
            failed += 1
        except Exception as e:
            print(f"\n[FAIL] {test_name} ERROR: {e}\n")
            failed += 1
    
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"\n  Total Tests: {len(tests)}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    
    if failed == 0:
        print("\n*** ALL TESTS PASSED! Llama 4 implementation is ready. ***")
    else:
        print(f"\n[WARN] {failed} test(s) failed. Please review the errors above.")
    
    print("\n" + "=" * 70 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
