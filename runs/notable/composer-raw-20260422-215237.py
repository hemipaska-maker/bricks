@flow
def sum_values(values):
    total = step.reduce_sum(values=values)
    return {"sum": total}