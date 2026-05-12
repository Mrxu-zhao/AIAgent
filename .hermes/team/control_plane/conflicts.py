def detect_conflict(left, right):
    file_conflicts = sorted(set(left.files) & set(right.files))
    module_conflicts = sorted(set(left.modules) & set(right.modules))
    contract_conflicts = sorted(set(left.contracts) & set(right.contracts))

    if file_conflicts:
        return {"level": "hard", "conflicts": {"files": file_conflicts}}
    if contract_conflicts:
        return {"level": "review", "conflicts": {"contracts": contract_conflicts}}
    if module_conflicts:
        return {"level": "soft", "conflicts": {"modules": module_conflicts}}
    return {"level": "none", "conflicts": {}}
