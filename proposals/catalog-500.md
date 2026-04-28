# Brick Proposals Catalog — 500 bricks across 5 AI data-accuracy subjects

**Status:** Draft catalog (pre-proposal backlog). Not yet individual brick-proposal files.
**Compiled:** 2026-04-21
**Source:** RA exploration pass, grounded in April 2026 discourse on LLM data accuracy (hallucination, guardrails, RAG faithfulness, uncertainty, citation, data quality).

## How to use this catalog

Each row is a *candidate* brick — a name, a proposed signature, and a one-line purpose. Nothing here has been implemented, unit-tested, or written up as a full `proposals/brick-<category>-<name>.md`.

Workflow for promoting a row to a real proposal:

1. RA picks a row while working a case, validates the name isn't already in `src/bricks/stdlib/`, and confirms the signature against a concrete case YAML.
2. RA copies the row into a new `proposals/brick-<category>-<name>.md` using the template in `proposals/README.md` — fills in motivation, spec, 3–5 test cases, and notes.
3. RA flags Hemi in chat. Hemi reviews, tells Ops to open a GitHub Issue referencing the proposal.
4. Coder implements on a feature branch, PR merges, RA stamps `**Status:** Shipped in #<PR>` at the top of the proposal.

Signatures use the Bricks stdlib convention: every brick returns `dict[str, ...]` so it composes cleanly with `save_as` in a blueprint. Types in table cells use `or` instead of `|` to keep markdown tables legible.

## Existing stdlib (do not re-propose)

Before writing a real proposal, grep `src/bricks/stdlib/` for the name. Current stdlib (April 2026) already covers: `validate_json_schema`, `redact_pii_patterns` (basic regex), `mask_sensitive_data` (field-name based), `deduplicate_dict_list` (exact-key), `is_email_valid`, `is_url_valid`, `is_iso_date`, `has_required_keys`, `matches_pattern`, `levenshtein_distance`, `extract_json_from_str`, `parse_xml_to_dict`. Everything in this catalog is intentionally distinct from those.

## Distribution

| Subject | Count |
|---|---|
| A — Output Structure & Schema Enforcement | 120 |
| B — Hallucination & Faithfulness Scoring | 130 |
| C — Citation & Provenance Tracking | 70 |
| D — Confidence & Uncertainty Signals | 80 |
| E — Data Quality, Dedup & Canonicalization | 100 |
| **Total** | **500** |

---

## A — Output Structure & Schema Enforcement (120)

The guardrails layer: making LLM output *always parseable and shape-correct* before it reaches any downstream system. Covers JSON/YAML/XML/TOML parsing and repair, schema conformance, constraint validators per field type, type coercion with explicit fallbacks, code-fence extraction, and repair strategies for the typical malformed-output patterns that models produce under temperature.

### A.1 JSON parsing + repair (20)

| Name | Signature | Description |
|---|---|---|
| parse_json_strict | `(text: str) -> {data: Any, error: str or None}` | Strict JSON parse; returns data or a structured error message, never raises. |
| parse_json_lenient | `(text: str) -> {data: Any, repairs_applied: list[str]}` | Lenient parse that records which repair heuristics ran. |
| repair_json_trailing_comma | `(text: str) -> {text: str, changed: bool}` | Strip trailing commas before `}` or `]`. |
| repair_json_unquoted_keys | `(text: str) -> {text: str, changed: bool}` | Wrap unquoted object keys in double quotes. |
| repair_json_single_quotes | `(text: str) -> {text: str, changed: bool}` | Convert Python-style single-quoted strings to JSON double quotes. |
| repair_json_smart_quotes | `(text: str) -> {text: str, changed: bool}` | Replace Unicode curly quotes with straight ASCII quotes. |
| repair_json_truncated | `(text: str) -> {text: str, closed_brackets: int}` | Close truncated JSON by balancing outstanding brackets/braces. |
| repair_json_missing_comma | `(text: str) -> {text: str, changed: bool}` | Insert missing commas between adjacent object members. |
| repair_json_escape_newlines | `(text: str) -> {text: str, changed: bool}` | Escape raw newlines inside string values. |
| extract_first_json_object | `(text: str) -> {data: dict or None}` | Return the first balanced `{...}` region parsed as JSON. |
| extract_last_json_object | `(text: str) -> {data: dict or None}` | Return the last balanced `{...}` region parsed as JSON. |
| extract_all_json_objects | `(text: str) -> {objects: list[dict]}` | Return every balanced JSON object found in the text. |
| extract_json_from_codefence | `(text: str, lang: str = "json") -> {data: Any or None}` | Pull JSON out of a fenced code block. |
| strip_json_comments | `(text: str) -> {text: str, stripped: int}` | Remove `//` and `/* */` comments that some models emit. |
| strip_json_bom | `(text: str) -> {text: str, had_bom: bool}` | Remove a UTF-8 BOM prefix before parsing. |
| detect_json_indent_style | `(text: str) -> {indent: int or str}` | Detect indent used (2 spaces, 4 spaces, tab, or inline). |
| canonicalize_json_keys_sorted | `(data: dict) -> {data: dict}` | Return the same object with keys sorted recursively for stable hashing. |
| minify_json | `(data: Any) -> {text: str}` | Produce the smallest valid JSON serialization. |
| prettify_json | `(data: Any, indent: int = 2) -> {text: str}` | Produce a human-readable JSON serialization. |
| diff_json_structurally | `(a: Any, b: Any) -> {added: list, removed: list, changed: list}` | Structural diff producing JSON-pointer-style paths. |

### A.2 YAML / XML / TOML parsing + repair (15)

| Name | Signature | Description |
|---|---|---|
| parse_yaml_strict | `(text: str) -> {data: Any, error: str or None}` | Strict YAML 1.2 parse; never raises. |
| parse_yaml_lenient | `(text: str) -> {data: Any, repairs_applied: list[str]}` | Lenient YAML parse with indentation-repair heuristics. |
| parse_xml_to_dict_namespaced | `(xml_text: str) -> {data: dict, namespaces: dict}` | XML → dict preserving namespace prefixes. |
| parse_toml_strict | `(text: str) -> {data: dict, error: str or None}` | Strict TOML parse; never raises. |
| convert_yaml_to_json | `(yaml_text: str) -> {json: str}` | Round-trip YAML into canonical JSON. |
| convert_json_to_yaml | `(data: Any) -> {yaml: str}` | Serialize a Python object into flow-friendly YAML. |
| convert_xml_to_json | `(xml_text: str) -> {json: str}` | XML → JSON using attribute prefix convention. |
| convert_json_to_xml | `(data: dict, root: str = "root") -> {xml: str}` | JSON → XML with a named root element. |
| convert_toml_to_json | `(toml_text: str) -> {json: str}` | Serialize TOML into canonical JSON. |
| extract_yaml_frontmatter | `(text: str) -> {frontmatter: dict, body: str}` | Pull `---` YAML frontmatter from a markdown document. |
| strip_yaml_anchors | `(yaml_text: str) -> {yaml: str}` | Inline all `&anchor`/`*alias` references and remove anchors. |
| flatten_xml_attributes | `(xml_text: str) -> {data: dict}` | Flatten element attributes into sibling keys under each node. |
| detect_yaml_indent_errors | `(yaml_text: str) -> {errors: list[str]}` | Surface mixed-tab-and-space or misaligned-indent locations. |
| repair_yaml_tab_chars | `(yaml_text: str, spaces: int = 2) -> {yaml: str, replacements: int}` | Replace leading tabs with spaces. |
| validate_xml_well_formed | `(xml_text: str) -> {well_formed: bool, error: str or None}` | Check XML parses without DTD/schema. |

### A.3 Schema conformance (20)

| Name | Signature | Description |
|---|---|---|
| validate_pydantic_model | `(data: dict, model_dotted: str) -> {valid: bool, errors: list}` | Validate against a registered Pydantic model referenced by dotted path. |
| validate_openapi_schema | `(data: Any, schema: dict) -> {valid: bool, errors: list}` | Validate against an OpenAPI 3.1 schema object. |
| validate_avro_schema | `(data: Any, schema: dict) -> {valid: bool, errors: list}` | Validate a record against an Avro schema. |
| validate_protobuf_schema | `(data: dict, proto_dotted: str) -> {valid: bool, errors: list}` | Validate against a registered protobuf message type. |
| validate_jsonschema_draft7 | `(data: Any, schema: dict) -> {valid: bool, errors: list}` | Draft-07 JSON Schema validator. |
| validate_jsonschema_draft2020 | `(data: Any, schema: dict) -> {valid: bool, errors: list}` | Draft 2020-12 JSON Schema validator. |
| check_required_fields_present | `(data: dict, required: list[str]) -> {missing: list[str]}` | Return the list of required fields not present. |
| check_no_extra_fields | `(data: dict, allowed: list[str]) -> {extra: list[str]}` | Return fields present but not in the allowlist. |
| check_field_types | `(data: dict, type_map: dict[str, str]) -> {mismatches: list}` | Check that each field's runtime type matches the declared type. |
| check_nested_depth_limit | `(data: Any, max_depth: int) -> {ok: bool, depth: int}` | Reject payloads that nest deeper than allowed. |
| check_array_length_bounds | `(data: list, min_len: int, max_len: int) -> {ok: bool}` | Enforce a length window on an array. |
| check_string_length_bounds | `(text: str, min_len: int, max_len: int) -> {ok: bool}` | Enforce a length window on a string. |
| check_numeric_bounds | `(value: float, min_val: float, max_val: float) -> {ok: bool}` | Enforce a min/max on a numeric value (inclusive). |
| check_enum_membership | `(value: Any, allowed: list) -> {ok: bool}` | Check membership in an allowed set. |
| check_pattern_match_all_fields | `(data: dict, patterns: dict[str, str]) -> {violations: list}` | Regex each string field against its assigned pattern. |
| list_schema_violations | `(data: Any, schema: dict) -> {violations: list}` | Return every schema violation with JSON-pointer path. |
| count_schema_violations | `(data: Any, schema: dict) -> {count: int}` | Count violations against a schema. |
| group_violations_by_field | `(violations: list) -> {grouped: dict[str, list]}` | Group violation records by field path. |
| summarize_schema_conformance | `(data: Any, schema: dict) -> {pct_valid_fields: float, top_errors: list}` | Compact summary of how conformant the payload is. |
| score_schema_completeness | `(data: dict, schema: dict) -> {score: float}` | 0–1 score of how many optional fields are populated. |

### A.4 Type coercion with fallbacks (15)

| Name | Signature | Description |
|---|---|---|
| coerce_to_int_or_default | `(value: Any, default: int = 0) -> {value: int, coerced: bool}` | Best-effort int coercion with fallback. |
| coerce_to_float_or_default | `(value: Any, default: float = 0.0) -> {value: float, coerced: bool}` | Best-effort float coercion with fallback. |
| coerce_to_bool_or_default | `(value: Any, default: bool = False) -> {value: bool, coerced: bool}` | Best-effort bool coercion (accepts yes/no/true/false/1/0). |
| coerce_to_date_or_default | `(value: Any, default: str or None = None) -> {value: str, coerced: bool}` | Best-effort ISO date coercion from freeform strings. |
| coerce_to_iso_datetime_or_default | `(value: Any, default: str or None = None) -> {value: str, coerced: bool}` | Best-effort ISO 8601 datetime coercion. |
| coerce_str_to_list_csv | `(text: str, separator: str = ",") -> {value: list[str]}` | Split a delimited string into a trimmed list. |
| coerce_str_to_list_newline | `(text: str) -> {value: list[str]}` | Split a string on newlines, drop empty lines. |
| coerce_dict_to_flat | `(data: dict, separator: str = ".") -> {value: dict}` | Flatten a nested dict keeping a reversible separator scheme. |
| coerce_null_variants_to_none | `(value: Any) -> {value: Any, changed: bool}` | Map "null", "NULL", "None", "N/A", "-" to Python `None`. |
| coerce_yes_no_to_bool | `(value: str) -> {value: bool, recognized: bool}` | Coerce natural-language yes/no variants to bool. |
| coerce_fraction_str_to_float | `(text: str) -> {value: float, coerced: bool}` | Parse "1/3" or "3 1/2" as float. |
| coerce_percent_str_to_float | `(text: str) -> {value: float, coerced: bool}` | Parse "42%" as `0.42`. |
| coerce_currency_str_to_float | `(text: str) -> {value: float, currency: str or None}` | Parse "$1,234.50" or "€1.234,50" as float + ISO currency. |
| coerce_scientific_to_float | `(text: str) -> {value: float, coerced: bool}` | Parse "1.2e-3" or "1.2×10^-3". |
| coerce_mixed_list_to_typed | `(items: list, target_type: str) -> {values: list, failures: list[int]}` | Coerce every element to a target type, reporting index-level failures. |

### A.5 Field-level constraint validators (20)

| Name | Signature | Description |
|---|---|---|
| check_field_enum | `(value: Any, allowed: list) -> {ok: bool}` | Reject values outside an enum. |
| check_field_regex | `(value: str, pattern: str) -> {ok: bool}` | Full-match a regex against a field value. |
| check_field_length_min_max | `(value: str, min_len: int, max_len: int) -> {ok: bool}` | Check a string length is within bounds. |
| check_field_numeric_range | `(value: float, min_val: float, max_val: float) -> {ok: bool}` | Check a numeric range (inclusive). |
| check_field_date_range | `(iso_date: str, min_date: str, max_date: str) -> {ok: bool}` | Check an ISO date is within a range. |
| check_field_url_reachable_no_io | `(url: str) -> {ok: bool, reason: str or None}` | Syntactic reachability check (scheme + netloc + path), no HTTP. |
| check_field_email_strict | `(email: str) -> {ok: bool, reason: str or None}` | Stricter email check than stdlib (local-part length, label rules). |
| check_field_uuid_version | `(value: str, version: int or None = None) -> {ok: bool}` | Validate a UUID, optionally enforcing a specific version. |
| check_field_iso_country_code | `(value: str, standard: str = "alpha2") -> {ok: bool}` | Validate against ISO 3166-1 alpha-2/alpha-3/numeric. |
| check_field_iso_currency_code | `(value: str) -> {ok: bool}` | Validate against ISO 4217. |
| check_field_iso_language_code | `(value: str, standard: str = "bcp47") -> {ok: bool}` | Validate against ISO 639 or BCP 47. |
| check_field_iso_timezone | `(value: str) -> {ok: bool}` | Validate against the IANA timezone database. |
| check_field_iso_unit | `(value: str) -> {ok: bool, dimension: str or None}` | Validate a SI unit symbol. |
| check_field_luhn_checksum | `(value: str) -> {ok: bool}` | Luhn-validate a numeric string (credit cards, IMEI, etc.). |
| check_field_iban_format | `(value: str) -> {ok: bool, country: str or None}` | Validate IBAN format + checksum. |
| check_field_credit_card_format | `(value: str) -> {ok: bool, network: str or None}` | Validate card format + network via IIN prefix. |
| check_field_postcode_format | `(value: str, country: str) -> {ok: bool}` | Country-aware postcode format check. |
| check_field_coordinate_latlon | `(lat: float, lon: float) -> {ok: bool}` | Bounds check a lat/lon pair. |
| check_field_ipv4 | `(value: str) -> {ok: bool}` | Validate IPv4 address. |
| check_field_ipv6 | `(value: str) -> {ok: bool}` | Validate IPv6 address. |

### A.6 Code / markdown fence extraction (10)

| Name | Signature | Description |
|---|---|---|
| extract_code_fence_python | `(text: str) -> {blocks: list[str]}` | Extract all `python` fenced code blocks. |
| extract_code_fence_sql | `(text: str) -> {blocks: list[str]}` | Extract all `sql` fenced code blocks. |
| extract_code_fence_shell | `(text: str) -> {blocks: list[str]}` | Extract all `bash`/`sh`/`shell` fenced blocks. |
| extract_code_fence_by_lang | `(text: str, lang: str) -> {blocks: list[str]}` | Extract fenced blocks whose language tag matches. |
| strip_code_fence_markers | `(text: str) -> {text: str}` | Remove all ```` ``` ```` markers leaving raw contents. |
| count_code_fences | `(text: str) -> {count: int}` | Count fenced blocks in the text. |
| list_fence_languages | `(text: str) -> {languages: list[str]}` | Return every distinct language tag used. |
| extract_inline_code | `(text: str) -> {spans: list[str]}` | Return every `` `inline` `` span. |
| detect_language_from_fence | `(block: str) -> {lang: str or None}` | Guess a language when a fence lacks a tag. |
| normalize_fence_backticks | `(text: str) -> {text: str}` | Normalize mixed `~~~` and ```` ``` ```` to a single style. |

### A.7 Output format detection + normalization (10)

| Name | Signature | Description |
|---|---|---|
| detect_output_format | `(text: str) -> {format: str, confidence: float}` | Classify text as JSON, YAML, XML, CSV, markdown, or prose. |
| detect_csv_delimiter | `(text: str) -> {delimiter: str}` | Guess CSV delimiter (comma, semicolon, tab, pipe). |
| detect_line_ending_style | `(text: str) -> {style: str}` | Detect LF, CRLF, or CR. |
| detect_text_encoding | `(blob: bytes) -> {encoding: str, confidence: float}` | Guess encoding (UTF-8, UTF-16, Latin-1). |
| normalize_line_endings | `(text: str, style: str = "lf") -> {text: str}` | Normalize newlines to a single style. |
| normalize_unicode_nfc | `(text: str) -> {text: str}` | Apply NFC normalization for stable comparison. |
| normalize_unicode_nfkc | `(text: str) -> {text: str}` | Apply NFKC normalization (compatibility). |
| strip_unicode_bidi_controls | `(text: str) -> {text: str, stripped: int}` | Remove RTL/LTR override characters. |
| strip_invisible_chars | `(text: str) -> {text: str, stripped: int}` | Remove zero-width, soft-hyphen, and other invisible codepoints. |
| detect_mixed_quote_styles | `(text: str) -> {mixed: bool, styles: list[str]}` | Flag documents that mix straight and curly quotes. |

### A.8 Repair strategies for malformed outputs (10)

| Name | Signature | Description |
|---|---|---|
| close_unbalanced_brackets | `(text: str) -> {text: str, closed: dict}` | Close unbalanced `{}`, `[]`, `()` in a stable order. |
| close_unbalanced_quotes | `(text: str) -> {text: str, closed: int}` | Close unbalanced single/double quotes. |
| remove_duplicate_keys_json | `(text: str, strategy: str = "last") -> {text: str, removed: int}` | Keep first or last occurrence of duplicate JSON keys. |
| deescape_over_escaped_string | `(text: str) -> {text: str}` | Collapse `\\n`, `\\\\`, etc. back to single-escape form. |
| fix_python_dict_to_json | `(text: str) -> {text: str, changed: bool}` | Convert Python `True`/`False`/`None` and single-quoted to JSON. |
| fix_boolean_casing_json | `(text: str) -> {text: str, changed: bool}` | Lowercase `True`/`False` → `true`/`false`. |
| fix_null_casing_json | `(text: str) -> {text: str, changed: bool}` | Lowercase `None`/`NULL` → `null`. |
| fix_infinity_nan_json | `(text: str, strategy: str = "null") -> {text: str, replaced: int}` | Replace `Infinity`/`NaN` with null or string sentinels. |
| truncate_to_last_valid_brace | `(text: str) -> {text: str, truncated: bool}` | Truncate a partial JSON to the last balanced closing brace. |
| strip_reasoning_preamble | `(text: str) -> {text: str, removed_lines: int}` | Remove leading lines before the first opening `{` or `[`. |

---

## B — Hallucination & Faithfulness Scoring (130)

Deterministic primitives for measuring whether an LLM's output is *grounded in the source context* it was given. Covers claim extraction, claim-to-source alignment scoring (BoW, ROUGE, BLEU, n-gram, entity/number match), entailment-style bucketing, per-claim verification against source spans, aggregation into RAG-style faithfulness and context-precision scores, source-span utilities, multi-sample consistency voting, and contradiction detection — both against source and internal to the answer.

### B.1 Claim extraction (15)

| Name | Signature | Description |
|---|---|---|
| split_answer_to_claims_sentence | `(answer: str) -> {claims: list[str]}` | Sentence-boundary split. |
| split_answer_to_claims_semantic | `(answer: str) -> {claims: list[str]}` | Split on clause/discourse boundaries, not just punctuation. |
| split_answer_to_triples_svo | `(answer: str) -> {triples: list[dict]}` | Extract subject-verb-object triples per sentence. |
| extract_numeric_claims | `(answer: str) -> {claims: list[dict]}` | Keep only claims containing numbers/quantities. |
| extract_named_entity_claims | `(answer: str, entity_types: list[str]) -> {claims: list[dict]}` | Keep claims mentioning entities of the given types. |
| extract_quantitative_facts | `(answer: str) -> {facts: list[dict]}` | Extract (entity, attribute, value, unit) quantitative facts. |
| extract_temporal_claims | `(answer: str) -> {claims: list[dict]}` | Keep claims involving dates, durations, or tenses. |
| extract_causal_claims | `(answer: str) -> {claims: list[str]}` | Keep claims using causal markers (because, due to, caused by). |
| extract_comparative_claims | `(answer: str) -> {claims: list[str]}` | Keep comparative/superlative claims. |
| extract_definitional_claims | `(answer: str) -> {claims: list[str]}` | Keep claims of the form "X is Y". |
| extract_citable_assertions | `(answer: str) -> {claims: list[str]}` | Keep claims that would normally carry a citation. |
| deduplicate_claims | `(claims: list[str]) -> {claims: list[str], removed: int}` | Exact-duplicate removal over a claim list. |
| cluster_paraphrased_claims | `(claims: list[str], threshold: float = 0.85) -> {clusters: list[list[str]]}` | Group paraphrase variants of the same assertion. |
| count_atomic_claims | `(answer: str) -> {count: int}` | Count atomic factual claims. |
| flag_non_claim_sentences | `(answer: str) -> {indices: list[int]}` | Mark sentences that are opinion, hedge, or filler. |

### B.2 Claim-source alignment scoring (20)

| Name | Signature | Description |
|---|---|---|
| score_claim_bow_overlap | `(claim: str, source: str) -> {score: float}` | Bag-of-words overlap ratio. |
| score_claim_ngram_overlap | `(claim: str, source: str, n: int = 2) -> {score: float}` | N-gram overlap precision. |
| score_claim_tfidf_similarity | `(claim: str, source: str, vocab: list[str]) -> {score: float}` | Cosine similarity on TF-IDF vectors against a supplied vocab. |
| score_claim_bm25_to_source | `(claim: str, source_chunks: list[str]) -> {best_score: float, best_idx: int}` | BM25 score of the claim against source chunks. |
| score_claim_rouge_l | `(claim: str, source: str) -> {score: float}` | ROUGE-L F1. |
| score_claim_rouge_1 | `(claim: str, source: str) -> {score: float}` | ROUGE-1 F1. |
| score_claim_rouge_2 | `(claim: str, source: str) -> {score: float}` | ROUGE-2 F1. |
| score_claim_bleu | `(claim: str, source: str, max_n: int = 4) -> {score: float}` | Sentence BLEU. |
| score_claim_meteor | `(claim: str, source: str) -> {score: float}` | METEOR score with stemming + synonym table. |
| score_claim_jaccard | `(claim: str, source: str) -> {score: float}` | Token-set Jaccard index. |
| score_claim_chrf | `(claim: str, source: str, n: int = 6) -> {score: float}` | Character n-gram F-score. |
| score_claim_token_precision | `(claim: str, source: str) -> {score: float}` | Fraction of claim tokens present in source. |
| score_claim_token_recall | `(claim: str, source: str) -> {score: float}` | Fraction of source tokens covered by claim (usually low). |
| score_claim_token_f1 | `(claim: str, source: str) -> {score: float}` | F1 of token precision and recall. |
| score_claim_entity_overlap | `(claim: str, source: str) -> {score: float, shared: list[str]}` | Named-entity-level overlap. |
| score_claim_number_match | `(claim: str, source: str) -> {score: float, matched: list[str]}` | Numeric-mention overlap. |
| score_claim_date_match | `(claim: str, source: str) -> {score: float, matched: list[str]}` | Date-mention overlap. |
| score_claim_stopword_free_overlap | `(claim: str, source: str) -> {score: float}` | Overlap after stopword removal. |
| score_claim_embedding_cosine_offline | `(claim_vec: list[float], source_vec: list[float]) -> {score: float}` | Cosine on pre-computed embeddings — brick stays pure. |
| score_claim_longest_common_subseq | `(claim: str, source: str) -> {score: float}` | Normalized LCS length. |

### B.3 Entailment bucketing (15)

| Name | Signature | Description |
|---|---|---|
| bucket_entailment_3way | `(score: float, thresholds: dict) -> {bucket: str}` | Bucket a score as supported / contradicted / not-stated. |
| bucket_entailment_5way | `(score: float, thresholds: dict) -> {bucket: str}` | 5-way bucket: strongly supported → strongly contradicted. |
| bucket_supported_threshold | `(score: float, min_support: float) -> {supported: bool}` | Boolean gate for "supported enough". |
| bucket_contradicted_threshold | `(score: float, max_support: float) -> {contradicted: bool}` | Boolean gate for "actively contradicted". |
| bucket_not_stated_threshold | `(score: float, band: tuple[float, float]) -> {not_stated: bool}` | Boolean gate for "source is silent". |
| flag_partial_support | `(supporting_spans: list, claim_tokens: list) -> {partial: bool, coverage: float}` | Flag claims where only part of the assertion is grounded. |
| flag_unsupported_numeric | `(claim: str, source: str) -> {unsupported_numbers: list}` | Flag numbers in the claim missing from the source. |
| flag_unsupported_entity | `(claim: str, source: str) -> {unsupported_entities: list}` | Flag entities in the claim missing from the source. |
| classify_claim_vs_source | `(claim: str, source: str) -> {label: str, score: float}` | Label a claim supported / contradicted / neutral. |
| assign_evidence_confidence | `(score: float) -> {confidence: str}` | Map a score into a qualitative confidence band. |
| mark_hallucinated | `(claim: str, source: str, threshold: float) -> {hallucinated: bool}` | Hard boolean: was the claim invented? |
| mark_grounded | `(claim: str, source: str, threshold: float) -> {grounded: bool}` | Hard boolean: was the claim supported? |
| mark_inconclusive | `(score: float, band: tuple[float, float]) -> {inconclusive: bool}` | Mark cases where no decision should be made. |
| score_support_strength | `(claim: str, spans: list[str]) -> {score: float}` | Weighted strength score from matched supporting spans. |
| summarize_entailment_distribution | `(labels: list[str]) -> {counts: dict, rate: dict}` | Roll labels up into counts and rates. |

### B.4 Per-claim verification primitives (20)

| Name | Signature | Description |
|---|---|---|
| check_claim_entity_in_source | `(claim: str, source: str) -> {all_present: bool, missing: list[str]}` | Check all entities in the claim appear in the source. |
| check_claim_number_in_source | `(claim: str, source: str) -> {all_present: bool, missing: list[str]}` | Check all numeric mentions appear in the source. |
| check_claim_date_in_source | `(claim: str, source: str) -> {all_present: bool, missing: list[str]}` | Check all date mentions appear in the source. |
| check_claim_quote_in_source | `(claim: str, source: str) -> {quotes_match: bool, mismatched: list[str]}` | Check quoted substrings appear verbatim in source. |
| check_claim_url_in_source | `(claim: str, source: str) -> {all_present: bool, missing: list[str]}` | Check URL mentions exist in the source. |
| check_claim_email_in_source | `(claim: str, source: str) -> {all_present: bool, missing: list[str]}` | Check email mentions exist in the source. |
| check_claim_quantity_match | `(claim: str, source: str) -> {matches: bool, deltas: list[dict]}` | Compare quantities with unit awareness. |
| check_claim_ordinal_match | `(claim: str, source: str) -> {matches: bool}` | Check ordinals ("first", "second") match. |
| check_claim_percentage_match | `(claim: str, source: str, tolerance: float = 0.0) -> {matches: bool}` | Match percentages within a tolerance. |
| check_claim_currency_match | `(claim: str, source: str) -> {matches: bool, currency: str or None}` | Check currency amount + ISO 4217 code match. |
| check_claim_timespan_overlap | `(claim_span: dict, source_span: dict) -> {overlaps: bool}` | Check two timespans overlap. |
| check_claim_person_name_match | `(claim: str, source: str) -> {matches: bool, canonical: str or None}` | Match person names accounting for initials. |
| check_claim_organization_match | `(claim: str, source: str) -> {matches: bool, canonical: str or None}` | Match organizations across abbreviations. |
| check_claim_location_match | `(claim: str, source: str) -> {matches: bool, canonical: str or None}` | Match locations across aliases. |
| check_claim_product_match | `(claim: str, source: str) -> {matches: bool}` | Match product/SKU mentions. |
| check_claim_event_match | `(claim: str, source: str) -> {matches: bool}` | Match event mentions by name + time window. |
| check_claim_relation_triple | `(triple: dict, source: str) -> {supported: bool}` | Verify a (subject, predicate, object) triple against source. |
| check_claim_within_context_window | `(claim_offset: int, window: tuple[int, int]) -> {inside: bool}` | Gate: was the evidence within the window actually given? |
| check_claim_subject_in_source | `(claim: str, source: str) -> {present: bool}` | Check the claim's subject is mentioned in the source. |
| check_claim_predicate_in_source | `(claim: str, source: str) -> {present: bool}` | Check the claim's predicate verb is attested in the source. |

### B.5 Aggregation & faithfulness scoring (15)

| Name | Signature | Description |
|---|---|---|
| compute_faithfulness_score | `(claim_labels: list[str]) -> {score: float}` | Supported-claim ratio (RAGAS-style). |
| compute_faithfulness_weighted | `(claim_labels: list[str], weights: list[float]) -> {score: float}` | Weighted faithfulness (longer/more-central claims count more). |
| compute_faithfulness_micro | `(records: list[dict]) -> {score: float}` | Micro-averaged faithfulness across records. |
| compute_faithfulness_macro | `(records: list[dict]) -> {score: float}` | Macro-averaged faithfulness across records. |
| compute_context_precision_at_k | `(relevant_flags: list[bool], k: int) -> {score: float}` | Context-precision@k metric. |
| compute_context_recall_at_k | `(relevant_flags: list[bool], total_relevant: int, k: int) -> {score: float}` | Context-recall@k metric. |
| compute_context_utilization | `(claim_spans: list, source_tokens: int) -> {score: float}` | Fraction of source actually used by the answer. |
| compute_answer_relevance | `(answer: str, question: str) -> {score: float}` | Approximate answer-relevance with surface signals. |
| compute_claim_density | `(answer: str) -> {claims_per_sentence: float}` | Density of factual claims per sentence. |
| compute_unsupported_ratio | `(claim_labels: list[str]) -> {ratio: float}` | Fraction of claims labelled not-stated. |
| compute_contradicted_ratio | `(claim_labels: list[str]) -> {ratio: float}` | Fraction of claims labelled contradicted. |
| compute_hallucination_rate | `(claim_labels: list[str]) -> {rate: float}` | Combined unsupported + contradicted rate. |
| aggregate_scores_by_claim_type | `(records: list[dict]) -> {by_type: dict}` | Roll scores up by claim type (numeric, entity, temporal, etc.). |
| aggregate_scores_by_source | `(records: list[dict]) -> {by_source: dict}` | Roll scores up by source document id. |
| rank_claims_by_support | `(records: list[dict]) -> {ranked: list[dict]}` | Sort claims strongest-to-weakest support. |

### B.6 Source-span utilities (15)

| Name | Signature | Description |
|---|---|---|
| highlight_supporting_spans | `(source: str, claim: str) -> {spans: list[dict]}` | Return (start, end, text) for spans supporting the claim. |
| highlight_contradicting_spans | `(source: str, claim: str) -> {spans: list[dict]}` | Return spans that contradict the claim. |
| extract_evidence_sentence_for_claim | `(source: str, claim: str) -> {sentence: str or None}` | Best single-sentence evidence. |
| extract_evidence_paragraph_for_claim | `(source: str, claim: str) -> {paragraph: str or None}` | Best paragraph-level evidence. |
| compute_span_offset_map | `(text: str) -> {sentence_offsets: list[tuple]}` | Precompute char offsets for sentence-level span math. |
| merge_overlapping_spans | `(spans: list[dict]) -> {spans: list[dict]}` | Merge adjacent or overlapping (start, end) spans. |
| expand_span_to_sentence | `(text: str, start: int, end: int) -> {start: int, end: int}` | Grow a token-level span to its containing sentence. |
| shrink_span_to_tokens | `(text: str, start: int, end: int, tokens: list[str]) -> {start: int, end: int}` | Trim a span down to the tightest token window. |
| rank_spans_by_support | `(spans: list[dict], claim: str) -> {ranked: list[dict]}` | Rank supporting spans by strength. |
| filter_spans_by_min_overlap | `(spans: list[dict], min_overlap: float) -> {spans: list[dict]}` | Drop spans below a minimum overlap threshold. |
| annotate_span_with_claim_id | `(span: dict, claim_id: str) -> {span: dict}` | Attach a claim id to a span record. |
| list_unsupported_claims | `(records: list[dict]) -> {claims: list[str]}` | Surface all claims without supporting spans. |
| list_orphan_spans | `(spans: list[dict], claims: list[dict]) -> {orphans: list[dict]}` | Surface retrieved spans used to support nothing. |
| score_span_informativeness | `(span: str, question: str) -> {score: float}` | Approximate informativeness of a span relative to a question. |
| count_distinct_supporting_chunks | `(records: list[dict]) -> {count: int}` | Count distinct retrieval chunks that supported any claim. |

### B.7 Consistency voting (15)

| Name | Signature | Description |
|---|---|---|
| vote_majority_across_samples | `(samples: list[str]) -> {answer: str, votes: dict}` | Plurality vote across sample answers. |
| vote_weighted_by_logprob | `(samples: list[dict]) -> {answer: str, weight: float}` | Weight votes by per-sample logprob. |
| compute_sample_agreement_rate | `(samples: list[str]) -> {rate: float}` | Fraction of sample pairs that agree. |
| cluster_samples_by_semantic | `(samples: list[str], threshold: float = 0.8) -> {clusters: list[list[int]]}` | Cluster by offline semantic similarity (embeddings supplied). |
| cluster_samples_by_edit_distance | `(samples: list[str], max_dist: int) -> {clusters: list[list[int]]}` | Cluster by edit distance. |
| pick_modal_answer | `(samples: list[str]) -> {answer: str}` | Return the most common sample. |
| score_sample_dispersion | `(samples: list[str]) -> {score: float}` | Entropy-style dispersion across samples. |
| flag_sample_outliers | `(samples: list[str]) -> {outlier_indices: list[int]}` | Mark samples that disagree with the cluster. |
| compute_self_consistency_score | `(samples: list[str]) -> {score: float}` | Agreement proportion with the modal answer. |
| score_entity_agreement_across_samples | `(samples: list[str]) -> {score: float}` | Fraction of samples that share the same entity set. |
| score_numeric_agreement_across_samples | `(samples: list[str], tolerance: float = 0.0) -> {score: float}` | Fraction of samples agreeing on numeric values. |
| score_ordering_agreement | `(samples: list[list]) -> {kendall_tau: float}` | Kendall's tau across ordered lists. |
| detect_bimodal_disagreement | `(samples: list[str]) -> {bimodal: bool, modes: list[str]}` | Flag 50/50 splits between two clusters. |
| select_highest_support_sample | `(samples: list[dict]) -> {sample: dict}` | Pick the sample with highest faithfulness score. |
| majority_vote_claim_level | `(samples: list[list[str]]) -> {claims: list[str]}` | Claim-level majority vote across samples. |

### B.8 Contradiction detection (15)

| Name | Signature | Description |
|---|---|---|
| detect_internal_contradictions | `(answer: str) -> {pairs: list[dict]}` | Return contradicting sentence pairs within one answer. |
| detect_numeric_contradiction | `(answer: str) -> {pairs: list[dict]}` | Flag conflicting numbers for the same attribute. |
| detect_temporal_contradiction | `(answer: str) -> {pairs: list[dict]}` | Flag conflicting dates/durations. |
| detect_entity_contradiction | `(answer: str) -> {pairs: list[dict]}` | Flag conflicting entity attributes. |
| detect_negation_contradiction | `(answer: str) -> {pairs: list[dict]}` | Detect a claim and its negation co-occurring. |
| detect_unit_mismatch | `(answer: str) -> {issues: list[dict]}` | Flag same-attribute claims stated in incompatible units. |
| detect_magnitude_mismatch | `(answer: str) -> {issues: list[dict]}` | Flag order-of-magnitude contradictions. |
| detect_comparative_flip | `(answer: str) -> {flips: list[dict]}` | Flag A>B then B>A in the same answer. |
| detect_quantifier_mismatch | `(answer: str) -> {issues: list[dict]}` | Flag "all" vs "some" conflicts. |
| detect_causal_direction_flip | `(answer: str) -> {flips: list[dict]}` | Flag X causes Y then Y causes X. |
| list_contradictory_claim_pairs | `(claims: list[str]) -> {pairs: list[tuple]}` | Return all pairwise contradictions in a claim list. |
| score_internal_consistency | `(answer: str) -> {score: float}` | 0–1 score of internal consistency. |
| flag_self_contradiction | `(answer: str) -> {has_contradiction: bool}` | Cheap boolean gate for self-contradiction. |
| flag_conflicting_evidence_spans | `(spans: list[str]) -> {pairs: list[tuple]}` | Flag pairs of retrieved spans that disagree. |
| summarize_contradiction_report | `(records: list[dict]) -> {summary: dict}` | Aggregate contradictions by type and severity. |

---

## C — Citation & Provenance Tracking (70)

Primitives for parsing citations out of generated text, mapping claims to supporting evidence spans, validating source URLs and content hashes, stamping run-level provenance, detecting watermarks, measuring attribution completeness, and normalizing between citation formats.

### C.1 Citation parsing (15)

| Name | Signature | Description |
|---|---|---|
| parse_citations_numeric_brackets | `(text: str) -> {citations: list[dict]}` | Parse `[1]`, `[2,3]`, `[4-7]` style. |
| parse_citations_numeric_parens | `(text: str) -> {citations: list[dict]}` | Parse `(1)`, `(2, 3)` style. |
| parse_citations_author_year | `(text: str) -> {citations: list[dict]}` | Parse "(Smith, 2023)" and "Smith et al., 2024". |
| parse_citations_footnote_superscript | `(text: str) -> {citations: list[dict]}` | Parse superscript footnote markers. |
| parse_citations_markdown_refs | `(text: str) -> {citations: list[dict]}` | Parse markdown `[text][1]` reference-style links. |
| parse_citations_named_ids | `(text: str) -> {citations: list[dict]}` | Parse `[@smith2023]` Pandoc-style IDs. |
| parse_citations_inline_urls | `(text: str) -> {citations: list[dict]}` | Parse inline URL citations. |
| parse_citations_bibtex | `(bib_text: str) -> {entries: list[dict]}` | Parse a BibTeX bibliography. |
| parse_citations_ris | `(ris_text: str) -> {entries: list[dict]}` | Parse RIS citation format. |
| parse_citations_endnote | `(text: str) -> {entries: list[dict]}` | Parse EndNote XML citation export. |
| parse_citations_doi | `(text: str) -> {dois: list[str]}` | Extract all DOIs from text. |
| parse_citations_arxiv_id | `(text: str) -> {ids: list[str]}` | Extract arXiv identifiers. |
| parse_citations_pubmed_id | `(text: str) -> {pmids: list[str]}` | Extract PubMed IDs. |
| parse_citations_isbn | `(text: str) -> {isbns: list[str]}` | Extract ISBN-10 / ISBN-13 values. |
| extract_citation_spans | `(text: str) -> {spans: list[dict]}` | Return (start, end, citation_id) for every in-text citation. |

### C.2 Claim → evidence mapping (10)

| Name | Signature | Description |
|---|---|---|
| map_citation_to_source_doc | `(citations: list[dict], registry: dict) -> {mapping: dict}` | Resolve each citation id to a source document record. |
| map_claim_to_citation_ids | `(claim: str, text: str) -> {citation_ids: list[str]}` | Return citation ids attached to a claim. |
| map_citation_to_chunk | `(citation_id: str, chunk_registry: dict) -> {chunk: dict or None}` | Map a citation id to the specific retrieval chunk used. |
| compute_claim_citation_coverage | `(claims: list[dict]) -> {rate: float}` | Fraction of claims with at least one citation. |
| list_claims_without_citation | `(claims: list[dict]) -> {claims: list[str]}` | Surface uncited claims for review. |
| list_citations_without_claim | `(text: str) -> {citations: list[str]}` | Surface floating citations not attached to a claim. |
| compute_citation_density | `(text: str) -> {per_sentence: float}` | Citations per sentence. |
| rank_citations_by_support_strength | `(citations: list[dict]) -> {ranked: list[dict]}` | Rank citations by underlying evidence strength. |
| flag_citation_reuse | `(citations: list[dict]) -> {overused: list[str]}` | Flag citation ids reused more than N times. |
| group_claims_by_source | `(claims: list[dict]) -> {by_source: dict}` | Group claims under the source document that supports them. |

### C.3 Source URL / content checks (10)

| Name | Signature | Description |
|---|---|---|
| hash_source_content_sha256 | `(content: str) -> {hash: str}` | Stable SHA-256 of source content for provenance stamping. |
| compare_source_hash_to_snapshot | `(content: str, expected: str) -> {match: bool}` | Compare content hash to a stored snapshot hash. |
| extract_canonical_url | `(url: str) -> {url: str}` | Apply scheme/host lowering, default-port stripping. |
| strip_tracking_params_from_url | `(url: str, deny_params: list[str]) -> {url: str, stripped: list[str]}` | Remove UTM and tracker params. |
| normalize_url_percent_encoding | `(url: str) -> {url: str}` | Re-encode reserved characters consistently. |
| detect_redirect_chain_signal | `(url_chain: list[str]) -> {hops: int, final: str}` | Summarize a recorded redirect chain (no I/O). |
| extract_domain_from_url | `(url: str) -> {domain: str, subdomain: str or None}` | Split host into domain / subdomain. |
| check_url_is_http_or_https | `(url: str) -> {ok: bool, scheme: str}` | Require http/https. |
| check_url_matches_allowlist | `(url: str, allowlist: list[str]) -> {ok: bool}` | Check domain is on an approved list. |
| check_url_matches_denylist | `(url: str, denylist: list[str]) -> {ok: bool}` | Block domains on a denylist. |

### C.4 Provenance stamping (10)

| Name | Signature | Description |
|---|---|---|
| stamp_run_id | `(record: dict, run_id: str) -> {record: dict}` | Attach a run id to a record. |
| stamp_model_id_and_version | `(record: dict, model: str, version: str) -> {record: dict}` | Attach model id + version. |
| stamp_source_id | `(record: dict, source_id: str) -> {record: dict}` | Attach source document id. |
| stamp_timestamp_utc | `(record: dict) -> {record: dict}` | Attach UTC ISO timestamp. |
| stamp_prompt_hash | `(record: dict, prompt: str) -> {record: dict}` | Attach SHA-256 of the prompt text. |
| stamp_retrieval_context_hash | `(record: dict, context: str) -> {record: dict}` | Attach SHA-256 of the retrieval context. |
| stamp_blueprint_version | `(record: dict, version: str) -> {record: dict}` | Attach blueprint version for reproducibility. |
| stamp_brick_registry_version | `(record: dict, version: str) -> {record: dict}` | Attach brick stdlib version. |
| build_provenance_envelope | `(stamps: dict) -> {envelope: dict}` | Assemble a complete provenance envelope. |
| merge_provenance_stamps | `(records: list[dict]) -> {record: dict}` | Merge per-step stamps into a single envelope. |

### C.5 Watermark detection (5)

| Name | Signature | Description |
|---|---|---|
| detect_text_watermark_zero_width | `(text: str) -> {found: bool, chars: list[str]}` | Detect zero-width characters used as watermarks. |
| detect_token_watermark_distribution | `(tokens: list[int], greenlist: list[int]) -> {score: float}` | Statistical test for greenlist-biased token distribution. |
| detect_watermark_via_redlist | `(tokens: list[int], redlist: list[int]) -> {score: float}` | Statistical test against a redlist variant. |
| score_watermark_confidence | `(z: float) -> {confidence: float}` | Convert a z-score into a calibrated watermark confidence. |
| strip_detected_watermark_chars | `(text: str) -> {text: str, stripped: int}` | Remove zero-width watermark characters from text. |

### C.6 Attribution completeness (10)

| Name | Signature | Description |
|---|---|---|
| count_claims_with_citation | `(claims: list[dict]) -> {count: int}` | Count claims attached to at least one citation. |
| count_claims_without_citation | `(claims: list[dict]) -> {count: int}` | Count uncited claims. |
| compute_attribution_rate | `(claims: list[dict]) -> {rate: float}` | Cited-claim ratio. |
| flag_over_cited_claims | `(claims: list[dict], max_cites: int) -> {flagged: list[str]}` | Flag claims with excessive citations. |
| flag_under_cited_claims | `(claims: list[dict], min_cites: int) -> {flagged: list[str]}` | Flag claims with too few citations. |
| classify_citation_style | `(text: str) -> {style: str}` | Classify overall citation style (numeric, author-year, footnote). |
| validate_citation_id_is_registered | `(cid: str, registry: dict) -> {ok: bool}` | Check a citation id exists in the bibliography. |
| detect_orphan_citation_ids | `(text: str, registry: dict) -> {orphans: list[str]}` | Find in-text citations not in the bibliography. |
| detect_duplicate_citation_ids | `(registry: dict) -> {duplicates: list[str]}` | Find repeat ids in the bibliography. |
| score_citation_diversity | `(citations: list[dict]) -> {score: float}` | Source-diversity score (unique sources / total). |

### C.7 Citation format normalization (10)

| Name | Signature | Description |
|---|---|---|
| convert_citations_to_apa | `(entries: list[dict]) -> {text: list[str]}` | Format entries in APA style. |
| convert_citations_to_mla | `(entries: list[dict]) -> {text: list[str]}` | Format entries in MLA style. |
| convert_citations_to_chicago | `(entries: list[dict]) -> {text: list[str]}` | Format entries in Chicago style. |
| convert_citations_to_ieee | `(entries: list[dict]) -> {text: list[str]}` | Format entries in IEEE style. |
| convert_citations_to_bibtex | `(entries: list[dict]) -> {bib: str}` | Serialize entries into BibTeX. |
| convert_citations_to_csl_json | `(entries: list[dict]) -> {csl: list[dict]}` | Serialize into CSL-JSON. |
| normalize_author_names_initial | `(entries: list[dict]) -> {entries: list[dict]}` | Normalize to "First Last" with initials. |
| normalize_journal_abbreviations | `(entries: list[dict]) -> {entries: list[dict]}` | Normalize journal names via an abbreviation table. |
| normalize_page_range | `(entries: list[dict]) -> {entries: list[dict]}` | Standardize page ranges (e.g., "12-18"). |
| strip_duplicate_citations | `(entries: list[dict]) -> {entries: list[dict], removed: int}` | Remove duplicate bibliography entries. |

---

## D — Confidence & Uncertainty Signals (80)

Deterministic primitives over per-token logprobs, multi-sample outputs, and natural-language hedging — converting raw model signals into confidence scores, calibration buckets, and abstain-or-answer gates. Covers token-level logprob aggregation, perplexity, multi-sample agreement, semantic entropy (offline, on supplied embeddings), calibration methods, and hedging-phrase detection.

### D.1 Token logprob aggregation (15)

| Name | Signature | Description |
|---|---|---|
| compute_logprob_mean | `(logprobs: list[float]) -> {value: float}` | Mean logprob across tokens. |
| compute_logprob_median | `(logprobs: list[float]) -> {value: float}` | Median logprob. |
| compute_logprob_min | `(logprobs: list[float]) -> {value: float}` | Minimum logprob (worst token). |
| compute_logprob_max | `(logprobs: list[float]) -> {value: float}` | Maximum logprob (best token). |
| compute_logprob_std | `(logprobs: list[float]) -> {value: float}` | Standard deviation across tokens. |
| compute_logprob_variance | `(logprobs: list[float]) -> {value: float}` | Variance across tokens. |
| compute_logprob_range | `(logprobs: list[float]) -> {value: float}` | max - min logprob. |
| compute_logprob_percentile | `(logprobs: list[float], pct: float) -> {value: float}` | Logprob at a given percentile. |
| compute_logprob_entropy_normalized | `(logprobs: list[float]) -> {value: float}` | Length-normalized entropy of token distribution. |
| compute_logprob_weighted_by_length | `(logprobs: list[float]) -> {value: float}` | Length-weighted logprob sum. |
| compute_logprob_weighted_by_token_type | `(logprobs: list[float], token_types: list[str], weights: dict[str, float]) -> {value: float}` | Weight logprobs by token type (content vs stopword). |
| compute_logprob_first_n_tokens | `(logprobs: list[float], n: int) -> {value: float}` | Mean logprob over the first N tokens. |
| compute_logprob_last_n_tokens | `(logprobs: list[float], n: int) -> {value: float}` | Mean logprob over the last N tokens. |
| compute_logprob_span | `(logprobs: list[float], start: int, end: int) -> {value: float}` | Mean logprob over a specific span. |
| sum_logprobs_over_tokens | `(logprobs: list[float]) -> {value: float}` | Raw sum of logprobs. |

### D.2 Perplexity and related (10)

| Name | Signature | Description |
|---|---|---|
| compute_perplexity | `(logprobs: list[float]) -> {value: float}` | exp(-mean logprob). |
| compute_perplexity_delta_vs_baseline | `(logprobs: list[float], baseline: float) -> {delta: float}` | Perplexity delta versus a stored baseline. |
| compute_perplexity_per_sentence | `(logprobs: list[float], sentence_offsets: list[tuple]) -> {values: list[float]}` | Per-sentence perplexity. |
| compute_perplexity_per_claim | `(logprobs: list[float], claim_offsets: list[tuple]) -> {values: list[float]}` | Per-claim perplexity. |
| compute_token_surprise | `(logprobs: list[float]) -> {values: list[float]}` | -logprob per token (surprise signal). |
| compute_rank_of_top_token | `(token_distributions: list[dict]) -> {ranks: list[int]}` | Rank of the chosen token within the top-k distribution. |
| compute_margin_top1_top2 | `(token_distributions: list[dict]) -> {margins: list[float]}` | Gap between top-1 and top-2 probabilities per token. |
| compute_topk_probability_mass | `(token_distributions: list[dict], k: int) -> {masses: list[float]}` | Probability mass captured by top-k tokens. |
| compute_renyi_entropy | `(probs: list[float], alpha: float = 2.0) -> {value: float}` | Rényi entropy at a given α. |
| compute_gini_over_token_probs | `(probs: list[float]) -> {value: float}` | Gini coefficient of the token probability distribution. |

### D.3 Multi-sample agreement signals (15)

| Name | Signature | Description |
|---|---|---|
| compute_sample_agreement_rate_exact | `(samples: list[str]) -> {rate: float}` | Pairwise exact-match agreement. |
| compute_sample_agreement_rate_fuzzy | `(samples: list[str], threshold: float) -> {rate: float}` | Pairwise fuzzy agreement via edit distance. |
| compute_sample_entropy | `(samples: list[str]) -> {value: float}` | Shannon entropy over sample frequencies. |
| compute_cluster_count_over_samples | `(samples: list[str], threshold: float) -> {count: int}` | Number of semantic clusters across samples. |
| compute_intra_cluster_sim | `(clusters: list[list[str]]) -> {value: float}` | Mean intra-cluster similarity. |
| compute_inter_cluster_sim | `(clusters: list[list[str]]) -> {value: float}` | Mean inter-cluster similarity. |
| compute_sample_diversity_score | `(samples: list[str]) -> {score: float}` | 1 - intra-sample similarity. |
| compute_kendall_tau_across_samples | `(rankings: list[list]) -> {value: float}` | Kendall's tau across ranked outputs. |
| compute_spearman_across_samples | `(rankings: list[list]) -> {value: float}` | Spearman rank correlation across samples. |
| compute_bleu_self_similarity | `(samples: list[str]) -> {value: float}` | Self-BLEU. |
| score_answer_stability | `(samples: list[str]) -> {score: float}` | Composite stability metric across samples. |
| score_entity_stability_across_samples | `(samples: list[str]) -> {score: float}` | Agreement on entity set. |
| score_length_stability_across_samples | `(samples: list[str]) -> {score: float}` | Agreement on response length. |
| detect_mode_collapse | `(samples: list[str]) -> {collapsed: bool}` | Flag when samples are near-identical. |
| detect_high_variance_answers | `(samples: list[str], threshold: float) -> {high_variance: bool}` | Flag high-dispersion sample sets. |

### D.4 Semantic entropy (10)

| Name | Signature | Description |
|---|---|---|
| compute_semantic_entropy | `(clusters: list[list[str]]) -> {value: float}` | Semantic entropy over meaning clusters. |
| compute_semantic_entropy_discrete | `(cluster_counts: list[int]) -> {value: float}` | Semantic entropy from discrete counts. |
| cluster_answers_by_meaning_offline | `(embeddings: list[list[float]], threshold: float) -> {clusters: list[list[int]]}` | Cluster pre-computed embeddings by cosine threshold. |
| estimate_meaning_cluster_probs | `(cluster_sizes: list[int]) -> {probs: list[float]}` | Empirical probabilities per cluster. |
| compute_conditional_semantic_entropy | `(clusters: list[list[str]], condition_key: str) -> {value: float}` | Conditional semantic entropy given a field. |
| compute_semantic_entropy_normalized | `(clusters: list[list[str]]) -> {value: float}` | Normalized to 0-1 range. |
| detect_meaning_divergence | `(samples: list[str], threshold: float) -> {diverged: bool}` | Flag when samples split across incompatible meanings. |
| score_meaning_coherence | `(samples: list[str]) -> {score: float}` | Coherence score across sample meanings. |
| compute_semantic_uncertainty_rank | `(samples: list[dict]) -> {rank: int}` | Rank a sample against its peers by uncertainty. |
| score_semantic_duplicates | `(samples: list[str], threshold: float) -> {pct_duplicate: float}` | Fraction of samples duplicated in meaning. |

### D.5 Calibration & bucketing (10)

| Name | Signature | Description |
|---|---|---|
| bucket_confidence_3tier | `(score: float) -> {bucket: str}` | Low / medium / high bucket. |
| bucket_confidence_5tier | `(score: float) -> {bucket: str}` | 5-tier confidence bucket. |
| bucket_uncertainty_above_threshold | `(score: float, threshold: float) -> {uncertain: bool}` | Binary gate on uncertainty. |
| apply_temperature_scaling_offline | `(logits: list[float], T: float) -> {probs: list[float]}` | Temperature-scaling calibration. |
| apply_platt_scaling_offline | `(scores: list[float], a: float, b: float) -> {probs: list[float]}` | Platt scaling with fitted coefficients. |
| apply_isotonic_scaling_offline | `(scores: list[float], anchors: list[tuple]) -> {probs: list[float]}` | Isotonic calibration via stored anchor pairs. |
| compute_expected_calibration_error | `(probs: list[float], labels: list[bool], n_bins: int = 10) -> {ece: float}` | ECE over a held-out set. |
| compute_maximum_calibration_error | `(probs: list[float], labels: list[bool], n_bins: int = 10) -> {mce: float}` | MCE over a held-out set. |
| compute_brier_score | `(probs: list[float], labels: list[bool]) -> {value: float}` | Brier score. |
| compute_reliability_diagram_bins | `(probs: list[float], labels: list[bool], n_bins: int = 10) -> {bins: list[dict]}` | Per-bin reliability statistics. |

### D.6 Abstain-or-answer gates (10)

| Name | Signature | Description |
|---|---|---|
| gate_answer_min_confidence | `(confidence: float, threshold: float) -> {allow: bool}` | Allow the answer only above a confidence threshold. |
| gate_answer_max_entropy | `(entropy: float, max_allowed: float) -> {allow: bool}` | Allow only below an entropy cap. |
| gate_answer_agreement_threshold | `(agreement: float, threshold: float) -> {allow: bool}` | Allow only when multi-sample agreement is sufficient. |
| gate_answer_support_threshold | `(support: float, threshold: float) -> {allow: bool}` | Allow only when source support exceeds threshold. |
| gate_answer_source_hit_required | `(source_hits: int) -> {allow: bool}` | Require at least one retrieved chunk was used. |
| emit_abstain_if_below_threshold | `(confidence: float, threshold: float) -> {answer: str or None}` | Emit `None` below threshold, original answer above. |
| emit_clarify_request_if_ambiguous | `(ambiguity_score: float, threshold: float) -> {ask_clarify: bool}` | Suggest a clarification instead of answering. |
| flag_low_confidence_claims | `(claims: list[dict], threshold: float) -> {flagged: list[str]}` | Mark per-claim low-confidence items. |
| route_to_human_review | `(record: dict, rules: dict) -> {route: str}` | Route record to human review if rule conditions match. |
| score_answer_quality_composite | `(signals: dict, weights: dict) -> {score: float}` | Composite score from confidence, support, consistency. |

### D.7 Hedging detection in NL (10)

| Name | Signature | Description |
|---|---|---|
| detect_hedging_words | `(text: str) -> {count: int, words: list[str]}` | Count hedging words (might, possibly, perhaps). |
| count_hedging_modifiers | `(text: str) -> {count: int}` | Count hedging modifiers per sentence. |
| detect_uncertainty_phrases | `(text: str) -> {phrases: list[str]}` | Detect "I'm not sure", "it seems", etc. |
| detect_speculative_verbs | `(text: str) -> {verbs: list[str]}` | Detect speculative verbs (suppose, guess, assume). |
| detect_qualifier_clauses | `(text: str) -> {clauses: list[str]}` | Detect qualifying clauses ("assuming...", "if..."). |
| score_assertion_strength | `(text: str) -> {score: float}` | 0-1 assertion-strength score. |
| detect_i_dont_know_pattern | `(text: str) -> {matched: bool}` | Detect explicit "I don't know" patterns. |
| detect_refusal_pattern | `(text: str) -> {matched: bool}` | Detect safety-refusal patterns. |
| detect_partial_knowledge_marker | `(text: str) -> {matched: bool}` | Detect "I only know X" style partial-knowledge markers. |
| score_certainty_language | `(text: str) -> {score: float}` | Composite certainty-of-language score. |

---

## E — Data Quality, Dedup & Canonicalization (100)

Post-LLM record cleaning, entity canonicalization, class-specific PII detection, cross-source reconciliation, anomaly and drift detection, and taxonomy mapping. These bricks run after model output lands in the data layer — they turn "a model said this" into something the downstream pipeline can trust.

### E.1 Fuzzy dedup algorithms (15)

| Name | Signature | Description |
|---|---|---|
| dedup_jaro_winkler | `(items: list[str], threshold: float = 0.9) -> {groups: list[list[int]]}` | Group by Jaro-Winkler similarity. |
| dedup_levenshtein_threshold | `(items: list[str], max_dist: int) -> {groups: list[list[int]]}` | Group by edit-distance threshold. |
| dedup_damerau_levenshtein | `(items: list[str], max_dist: int) -> {groups: list[list[int]]}` | Damerau-Levenshtein (adjacent transpositions). |
| dedup_hamming | `(items: list[str], max_dist: int) -> {groups: list[list[int]]}` | Hamming distance (equal-length strings). |
| dedup_jaccard_ngram | `(items: list[str], n: int, threshold: float) -> {groups: list[list[int]]}` | Group by Jaccard over character n-grams. |
| dedup_soundex | `(items: list[str]) -> {groups: list[list[int]]}` | Phonetic grouping via Soundex. |
| dedup_metaphone | `(items: list[str]) -> {groups: list[list[int]]}` | Phonetic grouping via Metaphone. |
| dedup_double_metaphone | `(items: list[str]) -> {groups: list[list[int]]}` | Double Metaphone for multilingual names. |
| dedup_simhash | `(items: list[str], hamming_threshold: int = 3) -> {groups: list[list[int]]}` | Near-duplicate via SimHash fingerprints. |
| dedup_minhash_lsh | `(items: list[str], num_perm: int = 128, threshold: float = 0.8) -> {groups: list[list[int]]}` | MinHash LSH near-duplicate grouping. |
| dedup_cosine_tfidf | `(items: list[str], threshold: float = 0.85) -> {groups: list[list[int]]}` | Cosine similarity on TF-IDF vectors. |
| dedup_fingerprint | `(items: list[str]) -> {groups: list[list[int]]}` | OpenRefine-style fingerprint clustering. |
| dedup_ngram_fingerprint | `(items: list[str], n: int = 2) -> {groups: list[list[int]]}` | N-gram fingerprint clustering. |
| dedup_by_canonical_key | `(items: list[dict], key_fn_name: str) -> {groups: list[list[int]]}` | Group by a registered canonical-key transform. |
| dedup_by_composite_signature | `(items: list[dict], fields: list[str]) -> {groups: list[list[int]]}` | Group by concatenated field signature. |

### E.2 Canonicalization — names / organizations (10)

| Name | Signature | Description |
|---|---|---|
| canonicalize_person_name | `(name: str) -> {canonical: str}` | Normalize casing, suffixes, titles, whitespace. |
| canonicalize_company_legal_suffix | `(name: str) -> {canonical: str, suffix: str or None}` | Normalize Inc, LLC, Ltd, GmbH, S.A. |
| canonicalize_company_brand | `(name: str, alias_table: dict) -> {canonical: str}` | Map brand variants to a canonical brand. |
| split_full_name_parts | `(name: str) -> {first: str, middle: str or None, last: str, suffix: str or None}` | Split a full name into parts. |
| normalize_title_honorific | `(title: str) -> {canonical: str}` | Normalize Dr / Mr / Mrs / Prof. |
| expand_initials | `(name: str, expansion_table: dict) -> {name: str}` | Expand initials via a lookup table. |
| collapse_initials | `(name: str) -> {name: str}` | Collapse "John Robert Smith" to "J. R. Smith". |
| unicode_fold_name | `(name: str) -> {name: str}` | Apply Unicode case folding for comparison. |
| strip_accents_name | `(name: str) -> {name: str}` | Remove diacritics. |
| assign_person_canonical_id | `(name_parts: dict) -> {canonical_id: str}` | Deterministic canonical id from name parts + DOB. |

### E.3 Canonicalization — places / addresses (10)

| Name | Signature | Description |
|---|---|---|
| canonicalize_street_abbreviations | `(address: str) -> {address: str}` | St → Street, Ave → Avenue, etc. |
| canonicalize_postcode_format | `(postcode: str, country: str) -> {postcode: str}` | Normalize postcode formatting per country. |
| canonicalize_state_to_iso | `(state: str, country: str) -> {iso_code: str or None}` | Map state/province names to ISO 3166-2. |
| canonicalize_country_to_iso_alpha2 | `(country: str) -> {iso: str or None}` | Map country name to ISO 3166-1 alpha-2. |
| canonicalize_country_to_iso_alpha3 | `(country: str) -> {iso: str or None}` | Map country name to ISO 3166-1 alpha-3. |
| split_address_components | `(address: str) -> {street: str, city: str, region: str, postcode: str, country: str}` | Split a freeform address. |
| normalize_city_casing | `(city: str) -> {city: str}` | Title-case with small-word rules. |
| geohash_from_latlon | `(lat: float, lon: float, precision: int = 7) -> {geohash: str}` | Compute geohash for clustering. |
| canonicalize_timezone_iana | `(tz: str) -> {tz: str or None}` | Map aliases (e.g., "EST") to IANA names. |
| canonicalize_place_name_via_alias | `(place: str, alias_table: dict) -> {canonical: str}` | Map alternate place names to canonical. |

### E.4 Canonicalization — currency / units / dates (10)

| Name | Signature | Description |
|---|---|---|
| canonicalize_currency_to_iso4217 | `(currency: str) -> {iso: str or None}` | Map $/€/USD/EUR to ISO 4217 codes. |
| convert_currency_static_rate | `(amount: float, from_ccy: str, to_ccy: str, rate_table: dict) -> {amount: float}` | Convert with a supplied rate table. |
| canonicalize_number_separators | `(text: str, locale: str) -> {text: str}` | Normalize 1,234.56 vs 1.234,56. |
| canonicalize_unit_si | `(value: float, unit: str) -> {value: float, unit: str}` | Convert to SI units via a reference table. |
| canonicalize_unit_imperial | `(value: float, unit: str) -> {value: float, unit: str}` | Convert to imperial units via a reference table. |
| convert_unit_offline_table | `(value: float, from_unit: str, to_unit: str, table: dict) -> {value: float}` | Convert via supplied conversion table. |
| canonicalize_date_to_iso8601 | `(text: str) -> {iso: str or None}` | Parse and normalize freeform dates to ISO 8601. |
| canonicalize_datetime_to_utc | `(iso_datetime: str, tz: str) -> {utc: str}` | Shift datetime to UTC. |
| canonicalize_duration_to_seconds | `(duration: str) -> {seconds: float}` | Parse "2h30m" or "PT2H30M" to seconds. |
| canonicalize_quantity_unit_pair | `(text: str) -> {quantity: float, unit: str}` | Split "5 kg" into quantity + unit. |

### E.5 PII class-specific detection (15)

| Name | Signature | Description |
|---|---|---|
| detect_pii_ssn_us | `(text: str) -> {found: list[str]}` | Detect US Social Security Numbers. |
| detect_pii_nino_uk | `(text: str) -> {found: list[str]}` | Detect UK National Insurance Numbers. |
| detect_pii_passport_generic | `(text: str) -> {found: list[dict]}` | Detect passport-number-shaped values. |
| detect_pii_drivers_license_us | `(text: str) -> {found: list[dict]}` | Detect US driver's license patterns by state. |
| detect_pii_iban | `(text: str) -> {found: list[str]}` | Detect IBANs. |
| detect_pii_swift_bic | `(text: str) -> {found: list[str]}` | Detect SWIFT/BIC codes. |
| detect_pii_credit_card | `(text: str) -> {found: list[dict]}` | Detect credit card numbers with network. |
| detect_pii_cvv | `(text: str) -> {found: list[str]}` | Detect CVV patterns (context-aware). |
| detect_pii_date_of_birth | `(text: str) -> {found: list[str]}` | Detect date-of-birth mentions. |
| detect_pii_medical_record_number | `(text: str) -> {found: list[str]}` | Detect MRN patterns. |
| detect_pii_icd10_code | `(text: str) -> {found: list[str]}` | Detect ICD-10 codes. |
| detect_pii_ip_address | `(text: str) -> {found: list[str]}` | Detect IPv4/IPv6 addresses. |
| detect_pii_mac_address | `(text: str) -> {found: list[str]}` | Detect MAC addresses. |
| detect_pii_geocoordinate | `(text: str) -> {found: list[tuple]}` | Detect lat/lon pairs. |
| detect_pii_biometric_id | `(text: str) -> {found: list[str]}` | Detect biometric identifier patterns. |

### E.6 Cross-source reconciliation (10)

| Name | Signature | Description |
|---|---|---|
| fuzzy_join_records | `(left: list[dict], right: list[dict], key_fn: str, threshold: float) -> {joined: list[dict]}` | Fuzzy-join on a canonical key. |
| resolve_conflict_latest_wins | `(values: list[dict]) -> {value: Any}` | Pick the latest-timestamp value. |
| resolve_conflict_source_priority | `(values: list[dict], priority: list[str]) -> {value: Any}` | Pick by source-priority order. |
| resolve_conflict_majority_wins | `(values: list[Any]) -> {value: Any, votes: dict}` | Pick the most common value. |
| resolve_conflict_longest_string | `(values: list[str]) -> {value: str}` | Pick the longest string (often most complete). |
| resolve_conflict_highest_confidence | `(values: list[dict]) -> {value: Any}` | Pick the highest-confidence value. |
| merge_record_union | `(records: list[dict]) -> {record: dict}` | Union-merge records, last-write-wins on conflicts. |
| merge_record_coalesce | `(records: list[dict]) -> {record: dict}` | Coalesce fields, keeping the first non-null. |
| flag_field_disagreements | `(records: list[dict]) -> {fields: list[str]}` | Surface fields where sources disagree. |
| compute_source_agreement_rate | `(records: list[dict]) -> {rate: float}` | Fraction of fields where all sources agree. |

### E.7 Anomaly detection (10)

| Name | Signature | Description |
|---|---|---|
| flag_numeric_z_score_outlier | `(value: float, mean: float, std: float, threshold: float = 3.0) -> {outlier: bool}` | Z-score threshold. |
| flag_numeric_iqr_outlier | `(value: float, q1: float, q3: float, k: float = 1.5) -> {outlier: bool}` | Tukey IQR rule. |
| flag_numeric_mad_outlier | `(value: float, median: float, mad: float, threshold: float = 3.5) -> {outlier: bool}` | Median absolute deviation rule. |
| flag_categorical_rare_value | `(value: str, freq_table: dict, threshold: float) -> {rare: bool}` | Flag rare category values. |
| flag_string_length_outlier | `(value: str, mean_len: float, std_len: float, threshold: float = 3.0) -> {outlier: bool}` | String-length z-score. |
| flag_date_out_of_range | `(iso_date: str, min_date: str, max_date: str) -> {out_of_range: bool}` | Reject dates outside a window. |
| flag_duplicate_primary_key | `(records: list[dict], key: str) -> {duplicates: list[Any]}` | Flag duplicate primary-key values. |
| flag_unexpected_null | `(record: dict, required_fields: list[str]) -> {nulls: list[str]}` | Flag nulls in fields that shouldn't be null. |
| flag_cross_field_violation | `(record: dict, rule_name: str) -> {violated: bool}` | Run a registered cross-field validation rule. |
| flag_value_outside_enum | `(value: Any, allowed: list) -> {outside: bool}` | Flag enum-violating values. |

### E.8 Field drift / profiling (10)

| Name | Signature | Description |
|---|---|---|
| profile_cardinality | `(values: list) -> {distinct: int, ratio: float}` | Distinct-value count and ratio. |
| profile_null_rate | `(values: list) -> {rate: float}` | Fraction of nulls. |
| profile_min_max | `(values: list[float]) -> {min: float, max: float}` | Min/max of a numeric column. |
| profile_mean_median_mode | `(values: list[float]) -> {mean: float, median: float, mode: float}` | Central-tendency summary. |
| profile_value_distribution | `(values: list) -> {histogram: dict}` | Frequency histogram of values. |
| profile_string_length_stats | `(values: list[str]) -> {mean: float, min: int, max: int}` | String-length stats. |
| compute_distribution_psi | `(baseline: list[float], current: list[float], n_bins: int = 10) -> {psi: float}` | Population Stability Index. |
| compute_distribution_ks_stat | `(baseline: list[float], current: list[float]) -> {stat: float, pvalue: float}` | Kolmogorov-Smirnov two-sample test. |
| detect_schema_drift | `(baseline_schema: dict, current_schema: dict) -> {added: list, removed: list, type_changed: list}` | Compare two schemas. |
| detect_category_drift | `(baseline_counts: dict, current_counts: dict, threshold: float) -> {drifted: bool, changes: dict}` | Detect category-distribution drift. |

### E.9 Taxonomy / category mapping (10)

| Name | Signature | Description |
|---|---|---|
| map_category_via_alias_table | `(value: str, aliases: dict) -> {canonical: str or None}` | Map via alias lookup. |
| map_category_via_regex_rules | `(value: str, rules: list[dict]) -> {canonical: str or None}` | Map via ordered regex rules. |
| collapse_rare_categories | `(values: list[str], min_count: int, label: str = "other") -> {values: list[str]}` | Fold rare categories into "other". |
| expand_hierarchical_category | `(value: str, hierarchy: dict) -> {path: list[str]}` | Expand a leaf category to its full hierarchy path. |
| validate_category_in_taxonomy | `(value: str, taxonomy: dict) -> {ok: bool}` | Check membership in a taxonomy. |
| reconcile_categories_across_sources | `(records: list[dict], mapping: dict) -> {records: list[dict]}` | Map each source's categories to a shared taxonomy. |
| compute_category_coverage | `(values: list[str], taxonomy: dict) -> {coverage: float}` | Fraction of taxonomy leaves observed. |
| flag_uncategorized_records | `(records: list[dict], field: str) -> {indices: list[int]}` | Flag records with missing/unknown category. |
| normalize_category_casing | `(values: list[str]) -> {values: list[str]}` | Case-normalize category labels. |
| assign_parent_category | `(value: str, hierarchy: dict) -> {parent: str or None}` | Return parent category of a leaf. |

---

## End of catalog

500 rows across A (120), B (130), C (70), D (80), E (100). Every row is a candidate — promotion to a real `proposals/brick-<category>-<name>.md` goes through the RA workflow at the top of this file.
