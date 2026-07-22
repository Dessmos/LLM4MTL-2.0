# Configure LLM4MTLs_Generate_Reactions_for_all_Configurations workflow
The workflow allows the simple configuration of desired LLMs and strategies using a JSON config file.
One for the selection of LLMs and one for the selection of the strategies.
The workflow then builds the cartesian product of llm X strategy and executes them for each prompt file provided.

Besides configuring the API-keys for the chosen LLMs, the read-/write- paths must be updated appropriately. 
This depends on the setup and the mounted volume.

The strategy and configuration JSON can be simply pasted in the "Define strategies" and "Define LLM models to use" nodes at the beginning of the workflow.

### LLM configuration example

```json
{
  "llms": [
    {
      "name": "claude-sonnet-4",
      "node": "Anthropic Chat Model"
    },
    {
      "name": "gemini-2.5-pro",
      "node": "Google Gemini Chat Model"
    },
    {
      "name": "gpt-5",
      "node": "OpenAI Chat Model"
    }
  ]
}
```
### Strategy configuration example
```json
{
  "strategies": [
    {
      "name": "only_prompt",
      "Few_shot": false,
      "Grammar": false,
      "Helper_methods": false
    },
    {
      "name": "grammar",
      "Few_shot": false,
      "Grammar": true,
      "Helper_methods": false
    },
    {
      "name": "few_shot",
      "Few_shot": true,
      "Grammar": false,
      "Helper_methods": false
    },
    {
      "name": "few_shot_AND_grammar",
      "Few_shot": true,
      "Grammar": true,
      "Helper_methods": false
    },
    {
      "name": "few_shot_AND_grammar_AND_helper",
      "Few_shot": true,
      "Grammar": true,
      "Helper_methods": true
    }
  ]
}
```