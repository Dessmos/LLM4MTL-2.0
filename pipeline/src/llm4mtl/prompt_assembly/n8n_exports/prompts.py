"""What the models are asked, in every n8n export.

This module holds the system messages and user turns sent to the
prompt-generation, transformation-generation, and semantic-test-generation
models, so the exact wording can be reviewed in one place. The user turns are
n8n expressions that read item fields and the output of a few named nodes.
This module builds no nodes and no connections.

Each purpose has one instruction for all languages. Only the parts in
:class:`WorkflowInputs` differ, so every language is asked for the same thing.

The semantic-test output contract is stated in one place only. The system
message points at the REQUIRED OUTPUT CONTRACT section and must not paraphrase
it: a paraphrase in the system message wins over the contract, and the model
follows the paraphrase.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from llm4mtl.prompt_assembly.n8n_exports.node_names import (
    EXAMPLES_TEXT_NODE,
    GRAMMAR_TEXT_NODE,
    HELPER_METHODS_TEXT_NODE,
)

# Item fields that the generated workflows set and the user turns read.
ASSEMBLED_PROMPT_FIELD = "assembled_prompt"
OUTPUT_CONTRACT_FIELD = "output_contract"

QWEN_MODEL = "qwen2.5-coder:7b"
NO_METAMODEL_TEXT = "(no external metamodel file is required by the task contract)"


@dataclass(frozen=True)
class WorkflowInputs:
    display_name: str
    reference_extension: str
    # The only parts of the transformation instruction that differ between
    # languages: the grammar clause, the names of declared entities, and one
    # optional extra rule.
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


# The frozen task prompt is written for the transformation generator. Test
# generation must say that it describes the code under test, or the model
# implements the task instead of testing it.
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
# Plain text with no escaping: ``refinement.py`` also uses it outside any n8n
# expression.
PREREQUISITES_SECTION_HEADER = (
    "Reactions that run beside this one (their tasks, not yours to implement; "
    "a test builds its pre-state through the changes they react to)"
)


def transformation_system_message(language: str) -> str:
    """The same instruction and numbered rule list for every language.

    Only the :class:`WorkflowInputs` parts differ between languages.
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
    """The user turn, identical in every language.

    The namespace URIs come from the task contract (``metamodel_uri_text``).
    """
    return (
        "={{ $json.prompt }}\n\n"
        "-- End of request.\n"
        "Here are the authoritative metamodel files:\n"
        "{{ $json.metamodel_text }}\n\n"
        "The metamodel namespace URIs for this task are:\n"
        "{{ $json.metamodel_uri_text }}\n\n"
        + "\n\n".join(
            (
                _template_section_if_ran(
                    EXAMPLES_TEXT_NODE,
                    "Here are some examples as guideline:",
                    "examples",
                ),
                _template_section_if_ran(
                    GRAMMAR_TEXT_NODE,
                    "Here is the grammar of the Language:",
                    "grammar",
                ),
                _template_section_if_ran(
                    HELPER_METHODS_TEXT_NODE,
                    "Here are helper methods you can use:",
                    "helper_methods",
                ),
            )
        )
    )


def _template_section_if_ran(node: str, heading: str, field: str) -> str:
    """A template part: ``heading`` and a field of ``node``, only if that node ran."""
    return (
        f"{{{{ $if($('{node}').isExecuted, "
        f'"{heading}\\n" + '
        f"$('{node}').item.json.{field}, \"\") }}}}"
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
        f"{{{{ $json.metamodel_text || '{NO_METAMODEL_TEXT}' }}}}\n\n"
        f"{inputs.display_name} grammar:\n{{{{ $json.grammar.content }}}}\n\n"
        "Reconstruct the concise natural-language developer request that could "
        "have produced this reference transformation. Preserve the task's "
        "observable intent and explicitly name its transformation rules, "
        "mappings, or reactions. Do not generate code or tests. Do not add facts "
        "that are absent from these inputs. State verbatim every literal string, "
        "prefix, and separator the reference writes into a target attribute. "
        "Keep the request under 150 words.\n\n"
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
    requirements = json.dumps(
        _prompt_language_requirements(language), ensure_ascii=False
    )
    user_content = (
        "'Task name: ' + ($json.task || '') + "
        "'\\n\\nReference transformation (' + ($json.reference.path || '') + '):\\n' + "
        "($json.reference.content || '') + "
        "'\\n\\nExact task-specific metamodel files:\\n' + "
        f"($json.metamodel_text || '{NO_METAMODEL_TEXT}') + "
        "'\\n\\nGrammar:\\n' + (($json.grammar || {}).content || '') + "
        "'\\n\\nReconstruct the concise natural-language developer request that "
        "could have produced this reference. Preserve observable intent and "
        "explicitly name its rules, mappings, or reactions. Do not generate code "
        "or tests, do not invent facts, and keep it under 100 words. "
        f"Language-specific requirements: ' + {requirements} + "
        "'\\n\\nReturn only the task prompt text.'"
    )
    return _qwen_chat_request(prompt_generation_system_message(language), user_content)


def _qwen_chat_request(system_message: str, user_content: str) -> str:
    """The JSON body of one local-Qwen chat request, as an n8n expression."""
    system = json.dumps(system_message, ensure_ascii=False)
    return (
        f"={{{{ JSON.stringify({{ model: '{QWEN_MODEL}', stream: false, "
        f"messages: [{{ role: 'system', content: {system} }}, "
        f"{{ role: 'user', content: {user_content} }}], "
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
    grammar_heading = (
        f"\\n\\n## {INPUTS[language].display_name} grammar (syntax guidance only)\\n"
    )
    examples = _concatenated_section_if_ran(
        EXAMPLES_TEXT_NODE, FEW_SHOT_SECTION_HEADER, "examples"
    )
    grammar = _concatenated_section_if_ran(
        GRAMMAR_TEXT_NODE, grammar_heading, "grammar"
    )
    helper_methods = _concatenated_section_if_ran(
        HELPER_METHODS_TEXT_NODE,
        "\\n\\n## Existing helper methods (background only)\\n",
        "helper_methods",
    )
    return (
        f'={{{{ "{TASK_SPECIFICATION_HEADER}" + $json.prompt + '
        '"\\n\\n## Authoritative metamodel files\\n" + '
        '($json.metamodel_text || "") + '
        '$if(($json.prerequisite_prompt_text || "") != "", '
        f'"\\n\\n## {PREREQUISITES_SECTION_HEADER}\\n" + '
        '$json.prerequisite_prompt_text, "") + '
        f'"{CONTRACT_SECTION_HEADER}" + ($json.{OUTPUT_CONTRACT_FIELD} || "") + '
        f"{examples} + {grammar} + {helper_methods} }}}}"
    )


def _concatenated_section_if_ran(node: str, heading: str, field: str) -> str:
    """An expression part: ``heading`` and a field of ``node``, only if it ran."""
    return (
        f'$if($("{node}").isExecuted, "{heading}" + '
        f'$("{node}").item.json.{field}, "")'
    )


def qwen_assembled_prompt() -> str:
    """The local-Qwen variant has no examples, grammar, or helper sections."""
    return (
        f'={{{{ "{TASK_SPECIFICATION_HEADER}" + ($json.prompt || "") + '
        '"\\n\\n## Authoritative metamodel files\\n" + '
        '($json.metamodel_text || "") + '
        f'"{CONTRACT_SECTION_HEADER}" + ($json.{OUTPUT_CONTRACT_FIELD} || "") }}}}'
    )


def test_generation_system_message(language: str) -> str:
    """The test-generation system message. It points at the contract.

    Do not describe the ``semantic_cases.json`` shape here. The system message
    has the highest priority, so any paraphrase of the contract here would win
    over the contract itself, and generated suites would follow its mistakes.
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
    return _qwen_chat_request(
        test_generation_system_message(language),
        f"($json.{ASSEMBLED_PROMPT_FIELD} || '')",
    )
