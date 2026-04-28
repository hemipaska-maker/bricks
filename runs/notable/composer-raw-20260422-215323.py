@flow
def find_max_value(values):
    wrapped   = for_each(items=values, do=lambda item: step.set_dict_field(data={}, field="v", value=item))
    extracted = step.map_values(items=wrapped.output, key="result")
    max_val   = step.calculate_aggregates(items=extracted.output, field="v", operation="max")
    return {"max": max_val}