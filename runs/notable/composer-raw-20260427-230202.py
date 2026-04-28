@flow
def analyze_log_lines(log_lines):
    # --- severity counts ---
    info_checks  = for_each(items=log_lines, do=lambda line: step.matches_pattern(text=line, pattern=r"^\S+ INFO \S+ - "))
    info_hits    = step.filter_dict_list(items=info_checks.output, key="result", value=True)
    info_count   = step.count_dict_list(items=info_hits.output)

    warn_checks  = for_each(items=log_lines, do=lambda line: step.matches_pattern(text=line, pattern=r"^\S+ WARN \S+ - "))
    warn_hits    = step.filter_dict_list(items=warn_checks.output, key="result", value=True)
    warn_count   = step.count_dict_list(items=warn_hits.output)

    error_checks = for_each(items=log_lines, do=lambda line: step.matches_pattern(text=line, pattern=r"^\S+ ERROR \S+ - "))
    error_hits   = step.filter_dict_list(items=error_checks.output, key="result", value=True)
    error_count  = step.count_dict_list(items=error_hits.output)

    debug_checks = for_each(items=log_lines, do=lambda line: step.matches_pattern(text=line, pattern=r"^\S+ DEBUG \S+ - "))
    debug_hits   = step.filter_dict_list(items=debug_checks.output, key="result", value=True)
    debug_count  = step.count_dict_list(items=debug_hits.output)

    sc1 = step.set_dict_field(data={},         field="INFO",  value=info_count.output)
    sc2 = step.set_dict_field(data=sc1.output, field="WARN",  value=warn_count.output)
    sc3 = step.set_dict_field(data=sc2.output, field="ERROR", value=error_count.output)
    sc4 = step.set_dict_field(data=sc3.output, field="DEBUG", value=debug_count.output)

    # --- top error patterns ---
    # Extract the message portion from ERROR lines; non-ERROR lines yield empty lists
    raw_extracts = for_each(items=log_lines, do=lambda line: step.extract_regex_pattern(text=line, pattern=r"^\S+ ERROR \S+ - (.+)$"))
    msg_lists    = step.map_values(items=raw_extracts.output, key="result")
    flat_msgs    = step.flatten_list(nested=msg_lists.output)

    # Wrap each message string into {"pattern": msg} so dict-based bricks can operate on it
    msg_wrapped  = for_each(items=flat_msgs.output, do=lambda msg: step.set_dict_field(data={}, field="pattern", value=msg))
    msg_dicts    = step.map_values(items=msg_wrapped.output, key="result")

    # Deduplicate to get one entry per distinct pattern
    unique_pats  = step.deduplicate_dict_list(items=msg_dicts.output, key="pattern")

    # For each unique pattern, filter the full message-dict list to isolate occurrences
    filtered_per = for_each(items=unique_pats.output, do=lambda pat: step.filter_dict_list(items=msg_dicts.output, key="pattern", value=pat["pattern"]))

    # Count occurrences for each pattern (fr["result"] is the filtered list from the previous for_each)
    counts_per   = for_each(items=filtered_per.output, do=lambda fr: step.count_dict_list(items=fr["result"]))

    # Pair each unique-pattern dict with its count result dict
    zipped       = step.zip_lists(a=unique_pats.output, b=counts_per.output)

    # Merge into {pattern, count} dicts
    merged       = for_each(items=zipped.output, do=lambda z: step.merge_dictionaries(base=z["a"], override={"count": z["b"]["result"]}))
    pat_counts   = step.map_values(items=merged.output, key="result")

    # Stable two-key sort: primary = count desc, secondary = pattern asc
    # Python sort is stable, so sorting by pattern first then by count preserves the tie-break order
    by_pattern   = step.sort_dict_list(items=pat_counts.output, key="pattern", reverse=False)
    by_count     = step.sort_dict_list(items=by_pattern.output, key="count", reverse=True)
    top3         = step.take_first_n(items=by_count.output, n=3)

    return {"severity_counts": sc4, "top_error_patterns": top3}