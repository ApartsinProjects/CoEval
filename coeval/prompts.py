"""Canonical prompt templates (§9) and resolution logic."""
from __future__ import annotations

# Six canonical prompt IDs defined in REQ-9.1
TEMPLATES: dict[str, str] = {
    'map_target_attrs': (
        "Generate synthetic data specifications for the {task_description} task by defining an "
        "attribute space that characterizes possible outputs. Return a JSON object mapping each "
        "attribute name to a list of possible values, and output only the JSON."
    ),
    'map_nuanced_attrs': (
        "Define synthetic data specifications for the {task_description} task by creating a nuanced "
        "variability-focused attribute space. Include only attributes that change document phrasing, "
        "structure, noise, and context—without changing the underlying outputs. Return a single JSON "
        "object mapping each attribute name to a list of allowed values, and output only the JSON."
    ),
    'autorubric': (
        "For the task {task_description}, where the model's output is {output_description}, create an "
        "evaluation rubric. Return only a JSON object where each key is a quality factor, and each "
        "value is a concise description of that factor. Output only the JSON."
    ),
    'sample': (
        "Generate a natural benchmark data point for the task {task_description} and produce a "
        "response {output_description}, where the response is specified with {target_attributes}. "
        "To make the datapoint naturalistic, use the following nuance parameters: "
        "{nuanced_attributes}. Return as JSON with exactly two keys: \"prompt\" and \"response\"."
    ),
    'test': (
        "Given the datapoint: {input}\n"
        "Perform the following task: {task_description}\n"
        "Produce the response: {output_description}"
    ),
    # evaluate_single and evaluate_per_factor are looked up by a combined key
    'evaluate_single': (
        "Evaluate the following student response for the task \"{task_description}\" that produces "
        "\"{output_description}\", given input \"{input}\" and known attributes {target_attributes}.\n\n"
        "Reference answer: {reference_response}\n"
        "Student response: {response}\n\n"
        "Score the student response against each of the following rubric factors:\n"
        "{rubric}\n\n"
        "Return only a JSON object where each key is a rubric factor name and each value is one of: "
        "\"High\", \"Medium\", or \"Low\". Output only the JSON."
    ),
    'evaluate_per_factor': (
        "Evaluate the following student response for the task \"{task_description}\" that produces "
        "\"{output_description}\", with input \"{input}\" and known attributes {target_attributes}.\n\n"
        "Reference answer: {reference_response}\n"
        "Student response: {response}\n\n"
        "According to rubric factor \"{rubric_factor_name}\": \"{rubric_factor_description}\".\n"
        "Return one word: High, Medium, or Low."
    ),
}


def get_prompt(
    prompt_id: str,
    task_prompt_library: dict[str, str],
    model_name: str,
    variables: dict[str, str],
) -> str:
    """Resolve the prompt template for the given prompt_id, applying overrides.

    Resolution order (REQ-9.3, REQ-9.4):
      1. {prompt_id}.{model_name}  — model-specific override
      2. {prompt_id}               — task-level override
      3. canonical TEMPLATES[prompt_id]
    """
    model_key = f'{prompt_id}.{model_name}'
    if model_key in task_prompt_library:
        template = task_prompt_library[model_key]
    elif prompt_id in task_prompt_library:
        template = task_prompt_library[prompt_id]
    else:
        template = TEMPLATES[prompt_id]
    return template.format(**variables)
