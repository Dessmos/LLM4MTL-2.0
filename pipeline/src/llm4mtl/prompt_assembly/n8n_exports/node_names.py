"""Names of the n8n nodes that the export generator reads, rewrites, or wires.

n8n connections and expressions refer to a node by its name. Each name here
must match the exported workflows exactly, including upper and lower case.
"""

from __future__ import annotations

# Nodes found in several workflow families.
LOOP_OVER_ITEMS_NODE = "Loop Over Items"
SAVE_FILE_NAME_NODE = "Save file name"
SAVE_REACTION_NAME_NODE = "Save reaction name"
PROMPT_INPUT_NODE = "Resolve exact task inputs"
READ_PROMPT_FILES_NODE = "Read prompt files"
WRITE_PROMPT_NODE = "Write prompt to disk"
WRITE_RESPONSE_NODE = "Write response to disk"
MERGE_NODE = "Merge"

# Optional prompt sections. Prompts read the output of the text nodes.
READ_EXAMPLES_NODE = "Read few shot examples"
READ_GRAMMAR_NODE = "Read Grammar"
READ_HELPER_METHODS_NODE = "Read helper methods"
EXAMPLES_TEXT_NODE = "Extract text from examples file"
GRAMMAR_TEXT_NODE = "Extract text from grammar"
HELPER_METHODS_TEXT_NODE = "Extract text from helper methods"

# The old language-wide model inputs. The exact task inputs replace them.
READ_MODEL_FILES_NODE = "Read model files"
EXTRACT_MODEL_TEXT_NODE = "Extract text from model files"
SUMMARIZE_NODE = "Summarize"
SUMMARIZE_MODELS_NODE = "Summarize models"

# Prompt generation.
READ_REFERENCE_FILE_NODE = "Read reference file"
EXTRACT_REFERENCE_TEXT_NODE = "Extract text from reference file"
MERGE_MODELS_REFERENCE_GRAMMAR_NODE = "Merge models, reference and grammar"
GENERATE_PROMPT_NODE = "Generate Prompt from Input"
GENERATE_PROMPT_QWEN_NODE = "Generate Prompt with local Qwen"
EXTRACT_QWEN_PROMPT_NODE = "Extract Qwen prompt text"
WRITE_DRAFT_PROMPT_NODE = "Write draft prompt to disk"
# Lower-case "file". Turns a generated candidate prompt into a file.
CONVERT_CANDIDATE_PROMPT_NODE = "Convert prompt to file"

# Test generation.
READ_QWEN_PROMPT_FILES_NODE = "Read Qwen prompt files"
SAVE_TASK_NAME_NODE = "Save task name"
GENERATE_TEST_SUITE_NODE = "(Re-)Generate test suite"
GENERATE_TEST_SUITE_QWEN_NODE = "Generate Test Suite with local Qwen"
MERGE_QWEN_TEST_INPUTS_NODE = "Merge prompt, task and models"
READ_OUTPUT_CONTRACT_NODE = "Read output contract"
EXTRACT_CONTRACT_TEXT_NODE = "Extract text from contract"
ASSEMBLE_PROMPT_NODE = "Assemble prompt"
# Upper-case "File". Turns the assembled test prompt into a file for the archive.
CONVERT_ASSEMBLED_PROMPT_NODE = "Convert prompt to File"

# Transformation generation.
GENERATE_CODE_NODE = "(Re-)Generate code"

# The multi-model Reactions matrix.
EXTRACT_PROMPT_TEXT_NODE = "Extract text from prompt file"
MERGE_PROMPT_INPUTS_NODE = "Merge prompt and exact inputs"
UPDATE_STRUCTURE_NODE = "Update-Structure"
STATIC_FILES_READY_NODE = "Static-Files-Ready"
CONVERT_RESPONSE_NODE = "Convert response to File"
