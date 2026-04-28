@flow
def compute_statistics(values):
    wrapped = for_each(items=values, do=lambda item: step.set_dict_field(data={}, field="v", value=item))
    total   = step.calculate_aggregates(items=wrapped.output, field="v", operation="sum")
    avg     = step.calculate_aggregates(items=wrapped.output, field="v", operation="avg")
    minimum = step.calculate_aggregates(items=wrapped.output, field="v", operation="min")
    maximum = step.calculate_aggregates(items=wrapped.output, field="v", operation="max")
    count   = step.calculate_aggregates(items=wrapped.output, field="v", operation="count")
    return {"sum": total, "mean": avg, "min": minimum, "max": maximum, "count": count}