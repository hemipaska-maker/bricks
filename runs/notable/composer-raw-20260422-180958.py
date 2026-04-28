@flow
def summarize_numbers(values):
    wrapped = for_each(items=values, do=lambda item: step.set_dict_field(data={}, field="v", value=item))
    total   = step.calculate_aggregates(items=wrapped.output, field="v", operation="sum")
    mean    = step.calculate_aggregates(items=wrapped.output, field="v", operation="avg")
    minimum = step.calculate_aggregates(items=wrapped.output, field="v", operation="min")
    maximum = step.calculate_aggregates(items=wrapped.output, field="v", operation="max")
    count   = step.count_dict_list(items=wrapped.output)
    return {"sum": total, "mean": mean, "min": minimum, "max": maximum, "count": count}