@flow
def compute_statistics(values):
    wrapped = for_each(items=values, do=lambda item: step.set_dict_field(data={}, field="v", value=item))
    nums    = step.map_values(items=wrapped.output, key="result")
    total   = step.calculate_aggregates(items=nums.output, field="v", operation="sum")
    count   = step.calculate_aggregates(items=nums.output, field="v", operation="count")
    minimum = step.calculate_aggregates(items=nums.output, field="v", operation="min")
    maximum = step.calculate_aggregates(items=nums.output, field="v", operation="max")
    mean    = step.divide(a=total.output, b=count.output)
    return {"sum": total, "mean": mean, "min": minimum, "max": maximum, "count": count}