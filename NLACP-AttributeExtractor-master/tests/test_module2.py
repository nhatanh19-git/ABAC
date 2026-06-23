import unittest
import uuid
import sys
import os

# ensure project root is on sys.path for imports when running tests directly
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from nlacp import module2


class TestModule2(unittest.TestCase):
    def test_dispatcher_routing_and_assembly(self):
        module1_output = {
            "subjects": [{"entity_type": "user", "ref_tokens": ["students"], "role": "student", "qualifiers": {"type": "civilian"}}],
            "actions": [{"verb": "view", "operation": "READ", "negated": False}],
            "resource": {"label": "score", "subject_filter": "civilian_student"},
            "environments": [{"id": "env_1", "trigger_phrase": "the academic information system"}],
            "context": [{"formal_expression": "resource.course_id IN subject.enrolled_courses"}],
            "relation_pairs": [{"entity": "subject", "rel_type": "attribute", "attribute": "type", "value": "civilian"}]
        }
        policy = module2.run_module2(module1_output)
        self.assertIn("policy_id", policy)
        self.assertTrue(policy.get("valid"))
        self.assertIn("principal_cluster", policy)
        self.assertIn("action_cluster", policy)
        self.assertIn("resource_cluster", policy)
        self.assertIn("context_cluster", policy)

    def test_validator_missing_SAR(self):
        # Build merged clusters missing action and resource
        merged = {
            "principal_cluster": {"subjects": [{"role": "student"}], "roles": ["student"], "qualifiers": []},
            "action_cluster": {"actions": [], "ops": [], "negation": False},
            "resource_cluster": {"resource": "", "scope": "", "attributes": []},
            "context_cluster": {"conditions": [], "env": [], "relations": []}
        }
        validator = module2.ConstraintValidator()
        res = validator.validate(merged)
        self.assertFalse(res["valid"])
        self.assertIn("Missing action(s)", res["warnings"])
        self.assertIn("Missing resource", res["warnings"])

    def test_assembler_schema_and_uuid(self):
        merged = {
            "principal_cluster": {"subjects": [{"role": "student"}], "roles": ["student"], "qualifiers": []},
            "action_cluster": {"actions": [{"verb": "read"}], "ops": ["read-ops"], "negation": False},
            "resource_cluster": {"resource": "score", "scope": "own", "attributes": []},
            "context_cluster": {"conditions": ["resource.course_id IN subject.enrolled_courses"], "env": ["the academic information system"], "relations": []}
        }
        assembler = module2.PolicyContextAssembler()
        policy = assembler.assemble(merged, [])
        # Validate policy_id is a uuid4
        pid = policy.get("policy_id")
        self.assertIsNotNone(pid)
        # check uuid format
        u = uuid.UUID(pid)
        self.assertEqual(u.version, 4)
        self.assertIn("abac_policy", policy)


if __name__ == "__main__":
    unittest.main()
