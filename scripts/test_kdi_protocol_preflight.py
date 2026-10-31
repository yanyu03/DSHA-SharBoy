"""KDI-P01 isolated protocol preflight tests: no process or network execution."""
import json
import unittest

from scripts.kdi_protocol_preflight import (
    CompiledContract, CompiledNullableTail, PreflightError, prepare_tool_call,
)


class PreflightTests(unittest.TestCase):
    def setUp(self):
        self.contract = CompiledContract.compile(["scribe", "cf"], max_arguments=2)

    def responses(self, arguments='{"args":["status"]}', **updates):
        item = {"type": "function_call", "call_id": "call-r1", "name": "scribe", "arguments": arguments}
        item.update(updates)
        return item

    def chat(self, arguments='{"args":["status"]}', **updates):
        item = {"id": "call-c1", "type": "function", "function": {"name": "scribe", "arguments": arguments}}
        item.update(updates)
        return item

    def test_same_dsha_request_for_both_protocols(self):
        r = prepare_tool_call(self.responses(), "responses", self.contract)
        c = prepare_tool_call(self.chat(), "chat", self.contract)
        self.assertEqual(r.to_dsha_request(), c.to_dsha_request())
        self.assertEqual(r.to_dsha_request(), {"tool": "scribe", "args": ["status"], "context": {}})
        self.assertEqual((r.provider_call_id, c.provider_call_id), ("call-r1", "call-c1"))

    def test_empty_args_supported(self):
        obj = prepare_tool_call(self.responses('{"args":[]}'), "responses", self.contract)
        self.assertEqual(obj.args, ())

    def test_responses_sdk_optional_item_metadata(self):
        item = self.responses(id="fc_123", status="completed")
        result = prepare_tool_call(item, "responses", self.contract)
        self.assertEqual(result.provider_call_id, "call-r1")  # never confuse item id with call_id
        self.assertEqual(result.to_dsha_request(), {"tool": "scribe", "args": ["status"], "context": {}})
        self.assertEqual(item["id"], "fc_123")
        self.assertEqual(prepare_tool_call(self.responses(id=None, status=None), "responses", self.contract),
                         prepare_tool_call(self.responses(), "responses", self.contract))

    def test_responses_incomplete_status_rejected(self):
        for status in ("in_progress", "incomplete", "failed", 1, {}, []):
            with self.subTest(status=status), self.assertRaises(PreflightError):
                prepare_tool_call(self.responses(status=status), "responses", self.contract)

    def test_responses_invalid_optional_id_rejected(self):
        for item_id in ("", 123, [], "x" * 129, "x\x00y", "x\x7fy"):
            with self.subTest(item_id=item_id), self.assertRaises(PreflightError):
                prepare_tool_call(self.responses(id=item_id), "responses", self.contract)

    def test_responses_unrecognized_sdk_metadata_still_rejected(self):
        for field in ("async", "caller", "namespace", "context"):
            with self.subTest(field=field), self.assertRaises(PreflightError):
                prepare_tool_call(self.responses(**{field: None}), "responses", self.contract)

    def test_unknown_tool_denied(self):
        with self.assertRaises(PreflightError):
            prepare_tool_call(self.responses(name="pwsh"), "responses", self.contract)

    def test_context_escalation_denied(self):
        for args in ('{"args":[],"context":{"tier":"danger-full-access"}}',
                     '{"args":[],"custom_env":{"TOKEN":"x"}}'):
            with self.subTest(args=args), self.assertRaises(PreflightError):
                prepare_tool_call(self.responses(args), "responses", self.contract)

    def test_duplicate_json_keys_denied(self):
        with self.assertRaises(PreflightError):
            prepare_tool_call(self.responses('{"args":[],"args":["override"]}'), "responses", self.contract)

    def test_unknown_payload_field_denied(self):
        with self.assertRaises(PreflightError):
            prepare_tool_call(self.responses(extra="x"), "responses", self.contract)

    def test_chat_payload_unknown_fields_denied(self):
        malformed = self.chat()
        malformed["function"]["context"] = {}
        with self.assertRaises(PreflightError):
            prepare_tool_call(malformed, "chat", self.contract)

    def test_invalid_argument_types_denied(self):
        for value in ('{"args":"status"}', '{"args":[123]}', '{"args":null}',
                      '{"args":["a","b","c"]}', '{"args":["a\\u0000b"]}',
                      '{"args":NaN}', '{"args":{}}', '[]', '{'):
            with self.subTest(value=value), self.assertRaises(PreflightError):
                prepare_tool_call(self.responses(value), "responses", self.contract)

    def test_argument_bytes_capped(self):
        big = json.dumps({"args": ["X" * 5000]})
        with self.assertRaises(PreflightError):
            prepare_tool_call(self.responses(big), "responses", self.contract)

    def test_unsupported_protocol_denied(self):
        with self.assertRaises(PreflightError):
            prepare_tool_call(self.responses(), "messages", self.contract)

    def test_bad_contract_denied(self):
        for tool_ids in ([], ["../tool"], ["UpperCase"]):
            with self.subTest(tool_ids=tool_ids), self.assertRaises(ValueError):
                CompiledContract.compile(tool_ids)

    def test_stable_preparation_and_no_mutation(self):
        original = self.responses()
        before = json.dumps(original, sort_keys=True)
        a = prepare_tool_call(original, "responses", self.contract)
        b = prepare_tool_call(original, "responses", self.contract)
        self.assertEqual(a, b)
        self.assertEqual(before, json.dumps(original, sort_keys=True))
        returned = a.to_dsha_request()
        returned["args"].append("injected")
        self.assertEqual(a.args, ("status",))


    def test_named_string_fields_both_protocols(self):
        contract = CompiledContract.compile(["scribe", "cf"], max_arguments=2,
            named_string_fields={"scribe": ("location", "query")})
        payload = '{"query":"today","location":"Boston"}'
        r = prepare_tool_call(self.responses(payload), "responses", contract)
        c = prepare_tool_call(self.chat(payload), "chat", contract)
        self.assertEqual(r.args, ("Boston", "today"))
        self.assertEqual(c.to_dsha_request(), r.to_dsha_request())
        self.assertEqual(r.provider_call_id, "call-r1")
        self.assertEqual(c.provider_call_id, "call-c1")

    def test_named_fields_default_denied_and_legacy_preserved(self):
        with self.assertRaises(PreflightError):
            prepare_tool_call(self.responses('{"location":"Boston"}'), "responses", self.contract)
        contract = CompiledContract.compile(["scribe"], named_string_fields={"scribe": ("location",)})
        self.assertEqual(prepare_tool_call(self.responses(), "responses", contract).args, ("status",))
        self.assertEqual(prepare_tool_call(self.responses('{"location":"Boston"}'), "responses", contract).args, ("Boston",))

    def test_named_fields_fail_closed(self):
        contract = CompiledContract.compile(["scribe", "cf"], max_arguments=2,
            named_string_fields={"scribe": ("location", "query")})
        for payload in ('{"location":"Boston"}', '{"location":"Boston","query":"today","extra":1}',
                        '{"location":"Boston","query":2}', '{"location":"Boston","query":"x\\u0000"}',
                        '{"location":"Boston","query":"today","context":{}}',
                        '{"location":"Boston","location":"NY","query":"today"}'):
            with self.subTest(payload=payload), self.assertRaises(PreflightError):
                prepare_tool_call(self.responses(payload), "responses", contract)
        with self.assertRaises(PreflightError):
            prepare_tool_call(self.responses('{"location":"Boston","query":"today"}', name="cf"), "responses", contract)

    def test_invalid_named_field_contract_denied(self):
        for mapping in ({"unknown": ("location",)}, {"scribe": ("context",)},
                        {"scribe": ("args",)}, {"scribe": ("location", "location")},
                        {"scribe": ()}, {"scribe": ("location", "query", "extra")},
                        {"scribe": ("bad-field",)}, {"scribe": "location"}, []):
            with self.subTest(mapping=mapping), self.assertRaises(ValueError):
                CompiledContract.compile(["scribe"], max_arguments=2, named_string_fields=mapping)

    def test_named_field_mapping_is_frozen(self):
        source = {"scribe": ["location"]}
        contract = CompiledContract.compile(["scribe"], named_string_fields=source)
        source["scribe"].append("context")
        source["scribe"] = ["query"]
        self.assertEqual(contract.named_string_fields, (("scribe", ("location",)),))
        result = prepare_tool_call(self.responses('{"location":"Boston"}'), "responses", contract)
        self.assertEqual(result.args, ("Boston",))


    def test_optional_trailing_named_fields_both_protocols(self):
        contract = CompiledContract.compile(
            ["scribe"], max_arguments=3,
            named_string_fields={"scribe": ("location", "query", "lang")},
            named_required_counts={"scribe": 1})
        for payload, expected in (
            ('{"location":"Boston"}', ("Boston",)),
            ('{"query":"today","location":"Boston"}', ("Boston", "today")),
            ('{"lang":"en","location":"Boston","query":"today"}',
             ("Boston", "today", "en")),
        ):
            with self.subTest(payload=payload):
                for source, item in (("responses", self.responses(payload)),
                                     ("chat", self.chat(payload))):
                    self.assertEqual(
                        prepare_tool_call(item, source, contract).args, expected)
        self.assertEqual(
            prepare_tool_call(self.responses(), "responses", contract).args,
            ("status",))

    def test_optional_fields_reject_holes_unknown_and_bad_types(self):
        contract = CompiledContract.compile(
            ["scribe"], max_arguments=3,
            named_string_fields={"scribe": ("location", "query", "lang")},
            named_required_counts={"scribe": 1})
        for payload in (
            '{"query":"today"}',
            '{"location":"Boston","lang":"en"}',
            '{"location":"Boston","query":123}',
            '{"location":"Boston","query":"today","lang":null}',
            '{"location":"Boston","query":"today","extra":"x"}',
            '{"location":"Boston","query":"today","context":{}}',
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(PreflightError):
                    prepare_tool_call(self.responses(payload), "responses", contract)

    def test_optional_fields_default_required_and_explicit_zero(self):
        required = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("location", "query")})
        with self.assertRaises(PreflightError):
            prepare_tool_call(self.responses('{"location":"Boston"}'),
                              "responses", required)
        empty_allowed = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("location", "query")},
            named_required_counts={"scribe": 0})
        self.assertEqual(
            prepare_tool_call(self.responses("{}"), "responses", empty_allowed).args,
            ())
        with self.assertRaises(PreflightError):
            prepare_tool_call(self.responses('{"query":"today"}'),
                              "responses", empty_allowed)

    def test_optional_required_counts_contract_validation_and_freezing(self):
        for bad in (
            [], {"unknown": 0}, {"scribe": -1}, {"scribe": 3},
            {"scribe": True}, {"scribe": 1.0}, {"scribe": "1"},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                CompiledContract.compile(
                    ["scribe"], named_string_fields={"scribe": ("location", "query")},
                    named_required_counts=bad)
        source = {"scribe": 1}
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("location", "query")},
            named_required_counts=source)
        source["scribe"] = 0
        self.assertEqual(contract.named_required_counts, (("scribe", 1),))
        with self.assertRaises(PreflightError):
            prepare_tool_call(self.responses("{}"), "responses", contract)


    def test_opt_in_named_scalar_types_both_protocols(self):
        contract = CompiledContract.compile(
            ["scribe"], max_arguments=3,
            named_string_fields={"scribe": ("location", "limit", "verbose")},
            named_required_counts={"scribe": 2},
            named_scalar_types={"scribe": {"limit": "integer", "verbose": "boolean"}})
        for payload, expected in (
            ('{"verbose":true,"limit":3,"location":"Boston"}', ("Boston", "3", "true")),
            ('{"location":"Boston","limit":-2}', ("Boston", "-2")),
            ('{"location":"Boston","limit":0,"verbose":false}', ("Boston", "0", "false")),
        ):
            for protocol, item in (("responses", self.responses(payload)),
                                   ("chat", self.chat(payload))):
                with self.subTest(payload=payload, protocol=protocol):
                    self.assertEqual(prepare_tool_call(item, protocol, contract).args, expected)
        self.assertEqual(prepare_tool_call(self.responses(), "responses", contract).args, ("status",))

    def test_named_scalar_types_reject_type_confusion(self):
        contract = CompiledContract.compile(
            ["scribe"], max_arguments=3,
            named_string_fields={"scribe": ("location", "limit", "verbose")},
            named_scalar_types={"scribe": {"limit": "integer", "verbose": "boolean"}})
        for payload in (
            '{"location":"Boston","limit":true,"verbose":false}',
            '{"location":"Boston","limit":"3","verbose":false}',
            '{"location":"Boston","limit":3.0,"verbose":false}',
            '{"location":"Boston","limit":null,"verbose":false}',
            '{"location":"Boston","limit":[],"verbose":false}',
            '{"location":"Boston","limit":3,"verbose":1}',
            '{"location":"Boston","limit":3,"verbose":"true"}',
            '{"location":"Boston","limit":3,"verbose":null}',
            '{"location":"Boston","limit":3,"verbose":{}}',
        ):
            with self.subTest(payload=payload), self.assertRaises(PreflightError):
                prepare_tool_call(self.responses(payload), "responses", contract)

    def test_named_scalar_types_contract_rejects_invalid_declarations(self):
        fields = {"scribe": ("location", "limit")}
        for bad in (
            [], {"scribe": []}, {"unknown": {"limit": "integer"}},
            {"scribe": {"missing": "integer"}}, {"scribe": {"limit": "number"}},
            {"scribe": {"limit": "string"}}, {"scribe": {"limit": True}},
            {"scribe": {"limit": None}},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                CompiledContract.compile(["scribe"], named_string_fields=fields,
                                         named_scalar_types=bad)
        with self.assertRaises(ValueError):
            CompiledContract.compile(["scribe"], named_scalar_types={"scribe": {"limit": "integer"}})

    def test_named_scalar_type_mapping_frozen_from_caller_mutation(self):
        declared = {"scribe": {"limit": "integer"}}
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("limit",)},
            named_scalar_types=declared)
        declared["scribe"]["limit"] = "boolean"
        declared["scribe"]["other"] = "integer"
        self.assertEqual(contract.named_scalar_types,
                         (("scribe", (("limit", "integer"),)),))
        self.assertEqual(prepare_tool_call(
            self.responses('{"limit":5}'), "responses", contract).args, ("5",))

    def test_named_scalar_opt_in_does_not_change_string_or_privilege_rules(self):
        default = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("limit",)})
        with self.assertRaises(PreflightError):
            prepare_tool_call(self.responses('{"limit":5}'), "responses", default)
        self.assertEqual(prepare_tool_call(
            self.responses('{"limit":"5"}'), "responses", default).args, ("5",))
        typed = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("limit",)},
            named_scalar_types={"scribe": {"limit": "integer"}})
        for payload in ('{"limit":5,"context":{}}',
                        '{"limit":5,"tier":"danger-full-access"}',
                        '{"limit":5,"extra":0}'):
            with self.subTest(payload=payload), self.assertRaises(PreflightError):
                prepare_tool_call(self.responses(payload), "responses", typed)

    def test_named_integer_bounds_inclusive_edges_both_protocols(self):
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("limit",)},
            named_scalar_types={"scribe": {"limit": "integer"}},
            named_integer_bounds={"scribe": {"limit": (0, 10)}})
        for value in (0, 5, 10):
            payload = json.dumps({"limit": value})
            for protocol, item in (("responses", self.responses(payload)),
                                   ("chat", self.chat(payload))):
                with self.subTest(value=value, protocol=protocol):
                    self.assertEqual(prepare_tool_call(item, protocol, contract).args,
                                     (str(value),))
        self.assertEqual(prepare_tool_call(self.responses(), "responses", contract).args,
                         ("status",))

    def test_named_integer_bounds_reject_outside_and_type_confusion(self):
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("limit",)},
            named_scalar_types={"scribe": {"limit": "integer"}},
            named_integer_bounds={"scribe": {"limit": (0, 10)}})
        for payload in ('{"limit":-1}', '{"limit":11}', '{"limit":true}',
                        '{"limit":1.5}', '{"limit":"5"}', '{"limit":null}'):
            for protocol, item in (("responses", self.responses(payload)),
                                   ("chat", self.chat(payload))):
                with self.subTest(payload=payload, protocol=protocol):
                    with self.assertRaises(PreflightError):
                        prepare_tool_call(item, protocol, contract)

    def test_named_integer_bounds_invalid_contracts_rejected(self):
        fields = {"scribe": ("limit", "verbose")}
        typed = {"scribe": {"limit": "integer", "verbose": "boolean"}}
        for invalid in (
            [], {"unknown": {"limit": (0, 10)}}, {"scribe": {}},
            {"scribe": {"missing": (0, 10)}},
            {"scribe": {"verbose": (0, 1)}},
            {"scribe": {"limit": (10, 0)}},
            {"scribe": {"limit": (0, True)}},
            {"scribe": {"limit": (0, 1.0)}},
            {"scribe": {"limit": [0]}},
            {"scribe": {"limit": "0,10"}},
            {"scribe": {"limit": (0, 10, 20)}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                CompiledContract.compile(["scribe"], named_string_fields=fields,
                    named_scalar_types=typed, named_integer_bounds=invalid)
        with self.assertRaises(ValueError):
            CompiledContract.compile(["scribe"], named_string_fields=fields,
                named_integer_bounds={"scribe": {"limit": (0, 10)}})

    def test_named_integer_bounds_frozen_and_unbounded_default_preserved(self):
        source = {"scribe": {"limit": [0, 10]}}
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("limit",)},
            named_scalar_types={"scribe": {"limit": "integer"}},
            named_integer_bounds=source)
        source["scribe"]["limit"][0] = 100
        source["scribe"]["extra"] = [0, 1]
        self.assertEqual(contract.named_integer_bounds,
                         (("scribe", (("limit", 0, 10),)),))
        self.assertEqual(prepare_tool_call(
            self.responses('{"limit":10}'), "responses", contract).args, ("10",))
        unbounded = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("limit",)},
            named_scalar_types={"scribe": {"limit": "integer"}})
        self.assertEqual(prepare_tool_call(
            self.responses('{"limit":999}'), "responses", unbounded).args, ("999",))


    def test_named_string_enums_accept_declared_values_both_protocols(self):
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("location", "lang")},
            named_required_counts={"scribe": 1},
            named_string_enums={"scribe": {"lang": ("en", "ja", "中文")}})
        for payload, expected in (
            ('{"location":"Boston","lang":"en"}', ("Boston", "en")),
            ('{"lang":"中文","location":"Beijing"}', ("Beijing", "中文")),
            ('{"location":"Tokyo"}', ("Tokyo",)),
        ):
            for protocol, item in (("responses", self.responses(payload)),
                                   ("chat", self.chat(payload))):
                with self.subTest(payload=payload, protocol=protocol):
                    self.assertEqual(prepare_tool_call(item, protocol, contract).args, expected)

    def test_named_string_enums_reject_outside_values_and_preserve_legacy(self):
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("lang",)},
            named_string_enums={"scribe": {"lang": ("en", "ja")}})
        for payload in ('{"lang":"EN"}', '{"lang":"fr"}', '{"lang":1}',
                        '{"lang":null}', '{"lang":"en","context":{}}',
                        '{"lang":"en","lang":"ja"}'):
            for protocol, item in (("responses", self.responses(payload)),
                                   ("chat", self.chat(payload))):
                with self.subTest(payload=payload, protocol=protocol):
                    with self.assertRaises(PreflightError):
                        prepare_tool_call(item, protocol, contract)
        self.assertEqual(prepare_tool_call(self.responses(), "responses", contract).args,
                         ("status",))

    def test_named_string_enums_reject_invalid_trusted_declarations(self):
        fields = {"scribe": ("lang", "limit")}
        typed = {"scribe": {"limit": "integer"}}
        for invalid in (
            [], {"unknown": {"lang": ("en",)}}, {"scribe": {}},
            {"scribe": {"missing": ("en",)}}, {"scribe": {"limit": ("1",)}},
            {"scribe": {"lang": ()}}, {"scribe": {"lang": ("en", "en")}},
            {"scribe": {"lang": ("en", 1)}}, {"scribe": {"lang": ("a\x00b",)}},
            {"scribe": {"lang": ("x" * 1025,)}},
            {"scribe": {"lang": tuple(str(i) for i in range(65))}},
            {"scribe": {"lang": "en"}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                CompiledContract.compile(
                    ["scribe"], named_string_fields=fields,
                    named_scalar_types=typed, named_string_enums=invalid)
        with self.assertRaises(ValueError):
            CompiledContract.compile(
                ["scribe"], named_string_enums={"scribe": {"lang": ("en",)}})

    def test_named_string_enums_frozen_and_opt_in(self):
        source = {"scribe": {"lang": ["en", "ja"]}}
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("lang",)},
            named_string_enums=source)
        source["scribe"]["lang"][0] = "fr"
        source["scribe"]["extra"] = ["es"]
        self.assertEqual(contract.named_string_enums,
                         (("scribe", (("lang", ("en", "ja")),)),))
        self.assertEqual(prepare_tool_call(
            self.responses('{"lang":"en"}'), "responses", contract).args, ("en",))
        with self.assertRaises(PreflightError):
            prepare_tool_call(self.responses('{"lang":"fr"}'), "responses", contract)
        unbounded = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("lang",)})
        self.assertEqual(prepare_tool_call(
            self.responses('{"lang":"fr"}'), "responses", unbounded).args, ("fr",))


    def test_invalid_unicode_legacy_args_fail_closed_both_protocols(self):
        for payload in (r'{"args":["\ud800"]}', r'{"args":["\udc00"]}'):
            for protocol, item in (("responses", self.responses(payload)),
                                   ("chat", self.chat(payload))):
                with self.subTest(payload=payload, protocol=protocol):
                    with self.assertRaises(PreflightError):
                        prepare_tool_call(item, protocol, self.contract)

    def test_invalid_unicode_named_args_fail_closed_both_protocols(self):
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("lang",)})
        for payload in (r'{"lang":"\ud800"}', r'{"lang":"\udc00"}'):
            for protocol, item in (("responses", self.responses(payload)),
                                   ("chat", self.chat(payload))):
                with self.subTest(payload=payload, protocol=protocol):
                    with self.assertRaises(PreflightError):
                        prepare_tool_call(item, protocol, contract)

    def test_invalid_unicode_provider_metadata_and_raw_fail_closed(self):
        bad = chr(0xD800)
        cases = (
            ("responses", self.responses(id="fc_" + bad)),
            ("responses", self.responses(call_id="call_" + bad)),
            ("chat", self.chat(id="call_" + bad)),
            ("responses", self.responses('{"args":["' + bad + '"]}')),
            ("chat", self.chat('{"args":["' + bad + '"]}')),
        )
        for protocol, item in cases:
            with self.subTest(protocol=protocol, item_keys=tuple(item)):
                with self.assertRaises(PreflightError):
                    prepare_tool_call(item, protocol, self.contract)

    def test_unicode_valid_pair_and_enum_compile_boundary(self):
        valid = r'{"args":["\ud83d\ude80"]}'
        for protocol, item in (("responses", self.responses(valid)),
                               ("chat", self.chat(valid))):
            self.assertEqual(prepare_tool_call(item, protocol, self.contract).args,
                             ("🚀",))
        with self.assertRaises(ValueError):
            CompiledContract.compile(
                ["scribe"], named_string_fields={"scribe": ("lang",)},
                named_string_enums={"scribe": {"lang": (chr(0xD800),)}})
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("lang",)},
            named_string_enums={"scribe": {"lang": ("🚀",)}})
        self.assertEqual(
            prepare_tool_call(self.responses(r'{"lang":"\ud83d\ude80"}'),
                              "responses", contract).args, ("🚀",))


    def test_schema_boundary_required_prefix_not_arbitrary_subset(self):
        # JSON Schema can require non-prefix fields; P01 intentionally cannot.
        contract = CompiledContract.compile(
            ["scribe"], max_arguments=3,
            named_string_fields={"scribe": ("location", "query", "lang")},
            named_required_counts={"scribe": 1})
        accepted = '{"lang":"ja","query":"weather","location":"Tokyo"}'
        for protocol, item in (("responses", self.responses(accepted)),
                               ("chat", self.chat(accepted))):
            with self.subTest(protocol=protocol):
                self.assertEqual(prepare_tool_call(item, protocol, contract).args,
                                 ("Tokyo", "weather", "ja"))
        for payload in ('{"location":"Tokyo","lang":"ja"}',
                        '{"query":"weather","lang":"ja"}'):
            for protocol, item in (("responses", self.responses(payload)),
                                   ("chat", self.chat(payload))):
                with self.subTest(payload=payload, protocol=protocol):
                    with self.assertRaises(PreflightError):
                        prepare_tool_call(item, protocol, contract)

    def test_schema_boundary_extra_properties_fail_closed_both_protocols(self):
        # Named P01 rejects extras even though generic JSON Schema permits them by default.
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("location",)})
        for payload in ('{"location":"Tokyo","extra":"x"}',
                        '{"location":"Tokyo","context":{}}',
                        '{"location":"Tokyo","tier":"read-only"}'):
            for protocol, item in (("responses", self.responses(payload)),
                                   ("chat", self.chat(payload))):
                with self.subTest(payload=payload, protocol=protocol):
                    with self.assertRaises(PreflightError):
                        prepare_tool_call(item, protocol, contract)
        self.assertEqual(prepare_tool_call(
            self.responses('{"location":"Tokyo"}'), "responses", contract).args,
            ("Tokyo",))

    def test_schema_boundary_legacy_args_not_subject_to_named_constraints(self):
        # Compatibility boundary: named integer bounds and enums do not cover legacy argv.
        contract = CompiledContract.compile(
            ["scribe"], max_arguments=2,
            named_string_fields={"scribe": ("limit", "lang")},
            named_scalar_types={"scribe": {"limit": "integer"}},
            named_integer_bounds={"scribe": {"limit": (0, 10)}},
            named_string_enums={"scribe": {"lang": ("en", "ja")}})
        for protocol, item in (("responses", self.responses('{"args":["999","fr"]}')),
                               ("chat", self.chat('{"args":["999","fr"]}'))):
            with self.subTest(protocol=protocol):
                self.assertEqual(prepare_tool_call(item, protocol, contract).args,
                                 ("999", "fr"))
        for protocol, item in (("responses", self.responses('{"limit":999,"lang":"fr"}')),
                               ("chat", self.chat('{"limit":999,"lang":"fr"}'))):
            with self.subTest(protocol=protocol):
                with self.assertRaises(PreflightError):
                    prepare_tool_call(item, protocol, contract)


    def test_strict_named_closed_subset_both_protocols(self):
        contract = CompiledContract.compile(
            ["scribe"], max_arguments=2,
            named_string_fields={"scribe": ("location", "limit")},
            named_scalar_types={"scribe": {"limit": "integer"}},
            named_integer_bounds={"scribe": {"limit": (1, 5)}},
            strict_named_tools=("scribe",))
        for protocol, make_item in (("responses", self.responses), ("chat", self.chat)):
            with self.subTest(protocol=protocol):
                good = prepare_tool_call(
                    make_item('{"limit":3,"location":"Tokyo"}'), protocol, contract)
                self.assertEqual(good.args, ("Tokyo", "3"))
                self.assertEqual(good.to_dsha_request()["context"], {})
                for payload in ('{"location":"Tokyo"}',
                                '{"location":"Tokyo","limit":3,"extra":"x"}',
                                '{"location":"Tokyo","limit":9}',
                                '{"args":["Tokyo","3"]}'):
                    with self.subTest(payload=payload), self.assertRaises(PreflightError):
                        prepare_tool_call(make_item(payload), protocol, contract)

    def test_strict_named_rejects_invalid_trusted_contract(self):
        base = {"named_string_fields": {"scribe": ("location", "lang")}}
        for extra in (
            {"strict_named_tools": ("cf",)},
            {"strict_named_tools": ("scribe", "scribe")},
            {"strict_named_tools": "scribe"},
            {"strict_named_tools": ("scribe",), "named_required_counts": {"scribe": 1}},
        ):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                CompiledContract.compile(["scribe", "cf"], **{**base, **extra})

    def test_strict_named_opt_in_and_immutable_snapshot(self):
        strict_names = ["scribe"]
        strict = CompiledContract.compile(
            ["scribe", "cf"], named_string_fields={"scribe": ("location",)},
            strict_named_tools=strict_names)
        strict_names.clear()
        self.assertEqual(strict.strict_named_tools, frozenset({"scribe"}))
        with self.assertRaises(PreflightError):
            prepare_tool_call(self.responses('{"args":["Tokyo"]}'), "responses", strict)
        default = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("location",)})
        self.assertEqual(
            prepare_tool_call(self.responses('{"args":["Tokyo"]}'), "responses", default).args,
            ("Tokyo",))


    def test_strict_named_null_values_fail_closed_both_protocols(self):
        # A strict all-required object cannot silently turn JSON null into argv.
        contract = CompiledContract.compile(
            ["scribe"], max_arguments=3,
            named_string_fields={"scribe": ("location", "limit", "lang")},
            named_scalar_types={"scribe": {"limit": "integer"}},
            strict_named_tools=("scribe",))
        for protocol, make_item in (("responses", self.responses), ("chat", self.chat)):
            with self.subTest(protocol=protocol):
                valid = '{"location":"Tokyo","limit":3,"lang":"ja"}'
                self.assertEqual(prepare_tool_call(make_item(valid), protocol, contract).args,
                                 ("Tokyo", "3", "ja"))
                for payload in (
                    '{"location":null,"limit":3,"lang":"ja"}',
                    '{"location":"Tokyo","limit":null,"lang":"ja"}',
                    '{"location":"Tokyo","limit":3,"lang":null}',
                ):
                    with self.subTest(payload=payload), self.assertRaises(PreflightError):
                        prepare_tool_call(make_item(payload), protocol, contract)

    def test_strict_named_missing_null_and_empty_are_distinct(self):
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("location", "lang")},
            strict_named_tools=("scribe",))
        for protocol, make_item in (("responses", self.responses), ("chat", self.chat)):
            for payload in ('{"location":"Tokyo"}',
                            '{"location":"Tokyo","lang":null}',
                            '{"args":["Tokyo",""]}'):
                with self.subTest(protocol=protocol, payload=payload):
                    with self.assertRaises(PreflightError):
                        prepare_tool_call(make_item(payload), protocol, contract)
            self.assertEqual(
                prepare_tool_call(make_item('{"location":"Tokyo","lang":""}'),
                                  protocol, contract).args, ("Tokyo", ""))
            self.assertEqual(
                prepare_tool_call(make_item('{"location":"Tokyo","lang":"null"}'),
                                  protocol, contract).args, ("Tokyo", "null"))

    def test_non_strict_optional_omission_does_not_accept_null(self):
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("location", "lang")},
            named_required_counts={"scribe": 1})
        for protocol, make_item in (("responses", self.responses), ("chat", self.chat)):
            self.assertEqual(
                prepare_tool_call(make_item('{"location":"Tokyo"}'),
                                  protocol, contract).args, ("Tokyo",))
            self.assertEqual(
                prepare_tool_call(make_item('{"args":["Tokyo"]}'),
                                  protocol, contract).args, ("Tokyo",))
            with self.subTest(protocol=protocol), self.assertRaises(PreflightError):
                prepare_tool_call(make_item('{"location":"Tokyo","lang":null}'),
                                  protocol, contract)



    def test_nullable_suffix_projection_roundtrip_both_protocols(self):
        # Pure opt-in experiment; production prepare_tool_call still rejects null.
        contract = CompiledContract.compile(
            ["scribe"], max_arguments=3,
            named_string_fields={"scribe": ("location", "lang", "note")},
            strict_named_tools=("scribe",))
        projection_contract = CompiledNullableTail.compile(contract, "scribe", ("lang", "note"))
        cases = (
            ('{"location":"Tokyo","lang":"ja","note":null}', ("Tokyo", "ja"), 1),
            ('{"location":"Tokyo","lang":null,"note":null}', ("Tokyo",), 2),
            ('{"location":"Tokyo","lang":"","note":"null"}', ("Tokyo", "", "null"), 0),
            ('{"location":"东京🚀","lang":"日本語","note":null}', ("东京🚀", "日本語"), 1),
        )
        for payload, argv, null_count in cases:
            for protocol, item in (("responses", self.responses(payload)),
                                   ("chat", self.chat(payload))):
                raw = item["arguments"] if protocol == "responses" else item["function"]["arguments"]
                with self.subTest(protocol=protocol, payload=payload):
                    result = projection_contract.project(raw)
                    self.assertEqual(result.argv_prefix, argv)
                    self.assertEqual(result.null_suffix_count, null_count)
                    self.assertEqual(result.restore_named(), json.loads(payload))
                    self.assertFalse(hasattr(result, "to_dsha_request"))

    def test_nullable_suffix_projection_rejects_holes_and_untrusted_values(self):
        contract = CompiledContract.compile(
            ["scribe"], max_arguments=3,
            named_string_fields={"scribe": ("location", "lang", "note")},
            strict_named_tools=("scribe",))
        projection_contract = CompiledNullableTail.compile(contract, "scribe", ("lang", "note"))
        invalid = (
            '{"location":"Tokyo","lang":null,"note":"later"}',
            '{"location":null,"lang":null,"note":null}',
            '{"location":"Tokyo","lang":"ja"}',
            '{"location":"Tokyo","lang":"ja","note":null,"context":{}}',
            '{"location":"Tokyo","lang":"ja","note":42}',
            '{"location":"Tokyo","lang":"ja","note":"\\ud800"}',
            '{"location":"Tokyo","lang":"ja","note":"x\\u0000"}',
            '{"location":"Tokyo","lang":"ja","note":null,"note":null}',
            '{"args":["Tokyo"]}',
            '{"location":"Tokyo","lang":"ja","note":NaN}',
        )
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(PreflightError):
                projection_contract.project(payload)
        with self.assertRaises(PreflightError):
            projection_contract.project('{"location":"' + "x" * 5000 + '","lang":null,"note":null}')

    def test_nullable_suffix_compilation_requires_trusted_strict_string_suffix(self):
        fields = {"scribe": ("location", "lang", "note")}
        strict = CompiledContract.compile(
            ["scribe"], max_arguments=3, named_string_fields=fields,
            strict_named_tools=("scribe",))
        for bad in ((), ("lang",), ("location",), ("note", "lang"), "note",
                    ("note", "note"), ("lang", "other")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                CompiledNullableTail.compile(strict, "scribe", bad)
        with self.assertRaises(ValueError):
            CompiledNullableTail.compile(strict, "unknown", ("note",))
        non_strict = CompiledContract.compile(["scribe"], max_arguments=3, named_string_fields=fields)
        with self.assertRaises(ValueError):
            CompiledNullableTail.compile(non_strict, "scribe", ("note",))
        typed = CompiledContract.compile(
            ["scribe"], max_arguments=3, named_string_fields=fields,
            strict_named_tools=("scribe",),
            named_scalar_types={"scribe": {"note": "integer"}})
        with self.assertRaises(ValueError):
            CompiledNullableTail.compile(typed, "scribe", ("note",))
        enumerated = CompiledContract.compile(
            ["scribe"], max_arguments=3, named_string_fields=fields,
            strict_named_tools=("scribe",),
            named_string_enums={"scribe": {"note": ("ja", "en")}})
        with self.assertRaises(ValueError):
            CompiledNullableTail.compile(enumerated, "scribe", ("note",))
        mutable = ["lang", "note"]
        compiled = CompiledNullableTail.compile(strict, "scribe", mutable)
        mutable.clear()
        self.assertEqual(compiled.nullable_tail, ("lang", "note"))

    def test_nullable_suffix_projection_does_not_change_p01_fail_closed(self):
        contract = CompiledContract.compile(
            ["scribe"], named_string_fields={"scribe": ("location", "lang")},
            strict_named_tools=("scribe",))
        helper = CompiledNullableTail.compile(contract, "scribe", ("lang",))
        payload = '{"location":"Tokyo","lang":null}'
        self.assertEqual(helper.project(payload).restore_named(),
                         {"location": "Tokyo", "lang": None})
        for protocol, item in (("responses", self.responses(payload)),
                               ("chat", self.chat(payload))):
            with self.subTest(protocol=protocol), self.assertRaises(PreflightError):
                prepare_tool_call(item, protocol, contract)


    def test_nullable_suffix_metadata_not_preserved_by_legacy_dsha_envelope(self):
        # The projection is reversible only while its trusted sidecar is retained.
        fields = ("location", "lang")
        strict = CompiledContract.compile(
            ["scribe"], max_arguments=2,
            named_string_fields={"scribe": fields},
            strict_named_tools=("scribe",))
        payload = '{"location":"Tokyo","lang":null}'
        projection = CompiledNullableTail.compile(strict, "scribe", ("lang",)).project(payload)
        self.assertEqual(projection.argv_prefix, ("Tokyo",))
        self.assertEqual(projection.null_suffix_count, 1)
        self.assertEqual(projection.restore_named(), {"location": "Tokyo", "lang": None})
        self.assertFalse(hasattr(projection, "to_dsha_request"))

        # Non-strict omission produces the same argv, but means something else.
        non_strict = CompiledContract.compile(
            ["scribe"], max_arguments=2,
            named_string_fields={"scribe": fields},
            named_required_counts={"scribe": 1})
        for protocol, make_item in (("responses", self.responses), ("chat", self.chat)):
            with self.subTest(protocol=protocol):
                with self.assertRaises(PreflightError):
                    prepare_tool_call(make_item(payload), protocol, strict)
                with self.assertRaises(PreflightError):
                    prepare_tool_call(make_item(payload), protocol, non_strict)
                omitted = prepare_tool_call(make_item('{"location":"Tokyo"}'),
                                            protocol, non_strict)
                request = omitted.to_dsha_request()
                self.assertEqual(request, {"tool": "scribe", "args": ["Tokyo"], "context": {}})
                self.assertEqual(tuple(request["args"]), projection.argv_prefix)
                self.assertNotEqual({"location": "Tokyo"}, projection.restore_named())


if __name__ == "__main__":
    unittest.main()
