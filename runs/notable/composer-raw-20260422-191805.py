@flow
def find_max(values):
    wrapped = for_each(items=values, do=lambda item: step.set_dict_field(data={}, field="v", value=item))
    dicts   = step.map_values(items=wrapped.output, key="result")
    max_val = step.calculate_aggregates(items=dicts.output, field="v", operation="max")
    return {"max": max_val}