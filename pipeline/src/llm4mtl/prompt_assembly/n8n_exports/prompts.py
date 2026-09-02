"""What the models are asked, in every n8n export.

This module is text and the facts that text interpolates — nothing else. It
holds the system messages and user turns sent to the prompt-generation,
transformation-generation, and semantic-test-generation models. It knows
nothing about n8n nodes, connections, or files, so the exact wording a model
receives can be reviewed here without reading any workflow plumbing.

One instruction per purpose, shared by every language. Only a language's
grammar clause, the names of its declared entities, and one optional extra
rule may differ; everything around them is identical, so a model is asked for
the same thing in every language.

The semantic-test contract is deliberately stated in one place only. The
system message points at the REQUIRED OUTPUT CONTRACT section instead of
paraphrasing it: when the two disagreed, the paraphrase won, and every
generated suite reproduced it rather than the contract.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowInputs:
    display_name: str
    reference_extension: str
    # What "follow the grammar exactly" means in this language, and what its
    # named entities are called. These are the only parts of the transformation
    # instruction that may differ between languages; everything around them is
    # shared, so a model is asked for the same thing in every language.
    grammar_constructs: str
    named_entities: str
    extra_rule: str = ""


INPUTS = {
    "etl": WorkflowInputs(
        display_name="Epsilon Transformation Language (ETL)",
        reference_extension="etl",
        grammar_constructs=(
            "transformation rules with transform/to, @lazy/@greedy/@abstract/"
            "@primary annotations, guard conditions, pre/post blocks, "
            "operations, EOL expressions, equivalent operator ::=, etc."
        ),
        named_entities="transformation and rule",
    ),
    "atl": WorkflowInputs(
        display_name="ATLAS Transformation Language (ATL)",
        reference_extension="atl",
        grammar_constructs=(
            "module header, create section, matched/called rules, helpers, "
            "OCL expressions, etc."
        ),
        named_entities="module, transformation, and rule",
    ),
    "qvto": WorkflowInputs(
        display_name="QVT Operational (QVT-O)",
        reference_extension="qvto",
        grammar_constructs=(
            "modeltype declarations, transformation header with in/out "
            "parameters, main() entry point, mapping declarations with "
            "optional when clauses, init blocks, constructors, mapping "
            "extensions such as inherits/merges/disjuncts, resolve "
            "expressions, object literals, etc."
        ),
        named_entities="transformation and mapping",
        extra_rule=(
            "Every `modeltype` declaration must quote one of the namespace "
            "URIs given above verbatim in its `uses` clause; never leave that "
            "string empty."
        ),
    ),
    "reactions": WorkflowInputs(
        display_name="Vitruv Reactions Language",
        reference_extension="reactions",
        grammar_constructs=(
            "imports, transformation block, reactions, routines, guards, "
            "create/update sections, persistence paths, correspondence links, "
            "etc."
        ),
        named_entities="transformation, reaction, and routine",
        extra_rule=(
            "Use as much of the Reactions Language as possible and fall back "
            "to Xtend only where the language cannot express the change. Never "
            "name a `val` after a word the grammar itself uses -- `root`, "
            "`element`, `attribute`, `change`, `reaction`, `routine`, `match`, "
            "`create`, `update`, `retrieve`, `check` -- because the parser "
            "reads it as that keyword and reports a syntax error; prefix such a "
            "name instead, as in `mRoot`."
        ),
    ),
}


# The frozen task prompt describes the transformation under test. It is written
# for the transformation generator, so test generation has to say out loud what
# role it plays here, or the model answers it instead of testing it.
TASK_SPECIFICATION_HEADER = (
    "## Task specification (describes the transformation under test: "
    "write tests for it, do not implement it)\\n"
)
CONTRACT_SECTION_HEADER = (
    "\\n\\n## REQUIRED OUTPUT CONTRACT " "(binding, overrides every other section)\\n"
)
FEW_SHOT_SECTION_HEADER = (
    "\\n\\n## Few-shot examples (they illustrate the binding contract above; "
    "on any conflict the contract wins)\\n"
)


def transformation_system_message(language: str) -> str:
    """One instruction, one rule list, for every language.

    The four languages' instructions had drifted into four different texts:
    different rule numbering (ATL skipped rule 4), different punctuation, and a
    QVT-O display name used nowhere else. Only the grammar clause, the names of
    a language's declared entities, and one optional extra rule may differ.
    """
    inputs = INPUTS[language]
    rules = [
        f"Follow the {inputs.display_name} grammar exactly "
        f"({inputs.grammar_constructs}).",
        f"Use the {inputs.named_entities} names provided by the user whenever "
        "they are specified.",
        "If a name is missing, invent a concise, CamelCase name that matches "
        "the intent.",
        "Reference only the metamodel namespace URIs given in the request; do "
        "not invent, rename, or substitute a namespace.",
    ]
    if inputs.extra_rule:
        rules.append(inputs.extra_rule)
    rules.append(
        "Do **not** wrap the result in Markdown fences, and do **not** add "
        "commentary, explanations, or blank lines beyond what the language "
        "requires."
    )
    numbered = "\n".join(f"{index}. {rule}" for index, rule in enumerate(rules, 1))
    return (
        f"You are an expert developer for the **{inputs.display_name}** "
        "(model transformation DSL).\n"
        "Your job is to translate the user's natural-language specification "
        f"into a complete, syntactically valid .{inputs.reference_extension} "
        "file.\n\nRules\n"
        f"{numbered}"
    )


def transformation_request() -> str:
    """The user turn. Identical in every language, including the namespaces.

    The namespace line used to be a hardcoded Vitruv URI in every workflow,
    which was simply untrue for ETL and ATL. It now comes from the contract.
    """
    return (
        "={{ $json.prompt }}\n\n"
        "-- End of request.\n"
        "Here are the authoritative metamodel files:\n"
        "{{ $json.metamodel_text }}\n\n"
        "The metamodel namespace URIs for this task are:\n"
        "{{ $json.metamodel_uri_text }}\n\n"
        "{{ $if($('Extract text from examples file').isExecuted, "
        '"Here are some examples as guideline:\\n" + '
        "$('Extract text from examples file').item.json.examples, \"\") }}\n\n"
        "{{ $if($('Extract text from grammar').isExecuted, "
        '"Here is the grammar of the Language:\\n" + '
        "$('Extract text from grammar').item.json.grammar, \"\") }}\n\n"
        "{{ $if($('Extract text from helper methods').isExecuted, "
        '"Here are helper methods you can use:\\n" + '
        "$('Extract text from helper methods').item.json.helper_methods, \"\") }}"
    )


def cloud_prompt_request(language: str) -> str:
    inputs = INPUTS[language]
    special = _prompt_language_requirements(language)
    return (
        f"=Task name: {{{{ $json.task }}}}\n\n"
        "Reference transformation (authoritative):\n"
        "File: {{ $json.reference.path }}\n"
        "{{ $json.reference.content }}\n\n"
        "Exact task-specific metamodel files selected by the task contract:\n"
        "{{ $json.metamodel_text || '(no external metamodel file is required by the task contract)' }}\n\n"
        f"{inputs.display_name} grammar:\n{{{{ $json.grammar.content }}}}\n\n"
        "Reconstruct the concise natural-language developer request that could "
        "have produced this reference transformation. Preserve the task's "
        "observable intent and explicitly name its transformation rules, "
        "mappings, or reactions. Do not generate code or tests. Do not add facts "
        "that are absent from these inputs. Keep the request under 100 words.\n\n"
        f"{special}\n\nReturn only the task prompt text."
    )


def prompt_generation_system_message(language: str) -> str:
    return (
        "You reconstruct one reusable natural-language task prompt for "
        f"{INPUTS[language].display_name}. The same reviewed prompt will be used "
        "for transformation generation and semantic-test generation. Use only "
        "the current reference, its task-contract-selected metamodels, the "
        "grammar, and the task name. Do not generate either artifact here."
    )


def qwen_prompt_request(language: str) -> str:
    system = json.dumps(
        prompt_generation_system_message(language),
        ensure_ascii=False,
    )
    requirements = json.dumps(
        _prompt_language_requirements(language), ensure_ascii=False
    )
    return (
        "={{ JSON.stringify({ model: 'qwen2.5-coder:7b', stream: false, "
        f"messages: [{{ role: 'system', content: {system} }}, "
        "{ role: 'user', content: "
        "'Task name: ' + ($json.task || '') + "
        "'\\n\\nReference transformation (' + ($json.reference.path || '') + '):\\n' + "
        "($json.reference.content || '') + "
        "'\\n\\nExact task-specific metamodel files:\\n' + "
        "($json.metamodel_text || '(no external metamodel file is required by the task contract)') + "
        "'\\n\\nGrammar:\\n' + (($json.grammar || {}).content || '') + "
        "'\\n\\nReconstruct the concise natural-language developer request that "
        "could have produced this reference. Preserve observable intent and "
        "explicitly name its rules, mappings, or reactions. Do not generate code "
        "or tests, do not invent facts, and keep it under 100 words. "
        f"Language-specific requirements: ' + {requirements} + "
        "'\\n\\nReturn only the task prompt text.' }], "
        "options: { temperature: 0.1, top_p: 1 } }) }}"
    )


def _prompt_language_requirements(language: str) -> str:
    if language == "reactions":
        return (
            "Describe the reaction-triggered change and its propagated effect; "
            "do not reinterpret it as a source-to-target batch transformation."
        )
    return (
        "Describe the source-to-target transformation intent at a high level "
        "without metamodel-qualified type prefixes."
    )


def cloud_test_request(language: str) -> str:
    grammar_name = INPUTS[language].display_name
    return (
        f'={{{{ "{TASK_SPECIFICATION_HEADER}" + $json.prompt + '
        '"\\n\\n## Authoritative metamodel files\\n" + '
        '($json.metamodel_text || "") + '
        '$if(($json.prerequisite_prompt_text || "") != "", '
        '"\\n\\n## Reactions that run beside this one (their tasks, not yours to '
        "implement; a test builds its pre-state through the changes they react "
        'to)\\n" + $json.prerequisite_prompt_text, "") + '
        f'"{CONTRACT_SECTION_HEADER}" + ($json.output_contract || "") + '
        '$if($("Extract text from examples file").isExecuted, '
        f'"{FEW_SHOT_SECTION_HEADER}" + '
        '$("Extract text from examples file").item.json.examples, "") + '
        '$if($("Extract text from grammar").isExecuted, '
        f'"\\n\\n## {grammar_name} grammar (syntax guidance only)\\n" + '
        '$("Extract text from grammar").item.json.grammar, "") + '
        '$if($("Extract text from helper methods").isExecuted, '
        '"\\n\\n## Existing helper methods (background only)\\n" + '
        '$("Extract text from helper methods").item.json.helper_methods, "") }}'
    )


def qwen_assembled_prompt() -> str:
    """The local-Qwen variant has no examples, grammar, or helper sections."""
    return (
        f'={{{{ "{TASK_SPECIFICATION_HEADER}" + ($json.prompt || "") + '
        '"\\n\\n## Authoritative metamodel files\\n" + '
        '($json.metamodel_text || "") + '
        f'"{CONTRACT_SECTION_HEADER}" + ($json.output_contract || "") }}}}'
    )


def test_generation_system_message(language: str) -> str:
    """Defer to the contract instead of paraphrasing it.

    This message used to restate the artifact shape in its own words, and the
    two texts disagreed. It listed the model fields as "name, kind, role, path,
    generated, and metamodelUri only for EMF", which reads as the literal value
    ``"EMF"``; it named neither the closed ``kind``/``role`` vocabularies nor
    the mandatory ``model`` and ``type`` fields of an assertion. Being the
    highest-priority instruction, it won over the contract that stated all of
    them, and every generated ATL suite reproduced this message rather than the
    contract. One authority now states the shape, and this message points at it.
    """
    message = (
        f"Generate semantic test artifacts for {INPUTS[language].display_name} "
        "from the reviewed shared task prompt. The task specification describes "
        "the transformation under test: write tests for it, do not implement "
        "it. Use the exact task-specific metamodel files.\n\n"
        "The user message contains a section titled REQUIRED OUTPUT CONTRACT. "
        "That section is binding and complete: it lists every allowed field "
        "name and every allowed field value of semantic_cases.json. Follow it "
        "literally. Do not introduce a field name or a field value that it does "
        "not list, and do not substitute a synonym for one that it does list. "
        "Where any other section of the prompt appears to disagree with it, the "
        "contract wins.\n\n"
        "Return only fenced file blocks: exactly one "
        "```json file=semantic_cases.json block and the model file blocks that "
        "it references. Never generate Java, JUnit, transformation code, Maven "
        "files, helper classes, or prose outside file blocks."
    )
    if language == "reactions":
        message += (
            ' Every test must use scenarioKind "change_propagation", model role '
            '"inout", and the closed declarative tests[].changes vocabulary. '
            "Do not reinterpret Reactions as a batch source-to-target transform."
        )
    return message


def qwen_test_request(language: str) -> str:
    system = json.dumps(
        test_generation_system_message(language),
        ensure_ascii=False,
    )
    return (
        "={{ JSON.stringify({ model: 'qwen2.5-coder:7b', stream: false, "
        f"messages: [{{ role: 'system', content: {system} }}, "
        "{ role: 'user', content: ($json.assembled_prompt || '') }], "
        "options: { temperature: 0.1, top_p: 1 } }) }}"
    )
