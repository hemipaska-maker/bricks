@flow
def count_values(values):
    count = step.count_dict_list(items=values)
    return {"count": count}