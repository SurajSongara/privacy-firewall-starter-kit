from pathlib import Path

import pytest
from pydantic import ValidationError

from privacy_firewall.policy import (
    BUILTIN_POLICIES,
    Policy,
    PolicyAction,
    TypePolicy,
    get_policy,
    list_policies,
)


class TestPolicyModel:
    def test_defaults(self) -> None:
        policy = Policy(name="test")
        assert policy.default_action == PolicyAction.REDACT
        assert policy.auto_redact_above == 0.9
        assert policy.ask_above == 0.5

    def test_inverted_bands_rejected(self) -> None:
        with pytest.raises(ValidationError, match="confidence bands"):
            Policy(name="bad", auto_redact_above=0.4, ask_above=0.6)

    def test_band_out_of_range_rejected(self) -> None:
        with pytest.raises(ValidationError, match="confidence bands"):
            Policy(name="bad", auto_redact_above=1.5)

    def test_type_policy_falls_back_to_default(self) -> None:
        policy = Policy(name="test", default_action=PolicyAction.ASK)
        assert policy.type_policy("PAN").action == PolicyAction.ASK

    def test_type_policy_override(self) -> None:
        policy = Policy(
            name="test",
            types={"PAN": TypePolicy(action=PolicyAction.KEEP)},
        )
        assert policy.type_policy("PAN").action == PolicyAction.KEEP
        assert policy.type_policy("EMAIL").action == PolicyAction.REDACT

    def test_immutable(self) -> None:
        policy = Policy(name="test")
        with pytest.raises(ValidationError):
            policy.name = "other"  # type: ignore[misc]


class TestPresets:
    def test_builtin_names(self) -> None:
        assert list_policies() == ["kyc", "minimal", "share-with-ai"]

    def test_share_with_ai_redacts_everything(self) -> None:
        policy = BUILTIN_POLICIES["share-with-ai"]
        for dtype in ("PAN", "AADHAAR", "EMAIL", "PHONE", "UPI", "IFSC", "ACCOUNT"):
            assert policy.type_policy(dtype).action == PolicyAction.REDACT

    def test_kyc_keeps_identity_numbers(self) -> None:
        policy = BUILTIN_POLICIES["kyc"]
        assert policy.type_policy("PAN").action == PolicyAction.KEEP
        assert policy.type_policy("AADHAAR").action == PolicyAction.KEEP
        assert policy.type_policy("ACCOUNT").action == PolicyAction.REDACT

    def test_minimal_asks_everything(self) -> None:
        policy = BUILTIN_POLICIES["minimal"]
        assert policy.type_policy("PAN").action == PolicyAction.ASK


class TestLoader:
    def test_builtin_by_name(self) -> None:
        assert get_policy("kyc").name == "kyc"

    def test_unknown_name_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown policy"):
            get_policy("does-not-exist")

    def test_load_yaml_file(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "custom.yaml"
        policy_file.write_text(
            "name: my-policy\n"
            "default_action: ask\n"
            "ask_above: 0.4\n"
            "types:\n"
            "  IFSC:\n"
            "    action: keep\n"
            "  PHONE:\n"
            "    action: redact\n"
            "    allow_values: ['1800-11-2233']\n"
        )
        policy = get_policy(str(policy_file))
        assert policy.name == "my-policy"
        assert policy.type_policy("IFSC").action == PolicyAction.KEEP
        assert policy.type_policy("PHONE").allow_values == ("1800-11-2233",)
        assert policy.type_policy("PAN").action == PolicyAction.ASK

    def test_load_json_file(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "custom.json"
        policy_file.write_text('{"name": "json-policy", "default_action": "keep"}')
        policy = get_policy(str(policy_file))
        assert policy.default_action == PolicyAction.KEEP

    def test_invalid_file_content_raises(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "bad.yaml"
        policy_file.write_text("name: bad\nask_above: 2.0\n")
        with pytest.raises(ValidationError):
            get_policy(str(policy_file))

    def test_unsupported_extension_raises(self, tmp_path: Path) -> None:
        policy_file = tmp_path / "bad.txt"
        policy_file.write_text("name: bad")
        with pytest.raises(ValueError, match="Unsupported policy file type"):
            get_policy(str(policy_file))
