from langsmith.evaluation import evaluate

evaluate(
    partial(get_baseline_chain, llm=basic_llm),
    data=dataset_name,
    metadata={**run_metadata, "model": "3.5"},
    evaluators=[eval_general],
)
