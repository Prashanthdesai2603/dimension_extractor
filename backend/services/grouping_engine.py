def group_tokens(tokens: list, gap_x: int = 50, gap_y: int = 15) -> list:
    """
    Groups individual text tokens into candidate dimension strings based on spatial proximity.
    
    Args:
        tokens: List of dicts with 'text' and 'bbox' (x0, y0, x1, y1).
        gap_x: Max horizontal distance between tokens.
        gap_y: Max vertical distance between baselines.
    """
    if not tokens:
        return []

    # Sort tokens primarily by Y (top) and then by X (left)
    sorted_tokens = sorted(tokens, key=lambda x: (x['bbox'][1], x['bbox'][0]))

    groups = []
    if not sorted_tokens:
        return []
        
    current_group = [sorted_tokens[0]]

    for i in range(1, len(sorted_tokens)):
        token = sorted_tokens[i]
        prev = current_group[-1]
        
        # Calculate centers
        y_center_curr = (token['bbox'][1] + token['bbox'][3]) / 2
        y_center_prev = (prev['bbox'][1] + prev['bbox'][3]) / 2
        
        # Same line check
        same_line = abs(y_center_curr - y_center_prev) <= gap_y
        
        # Horizontal distance check
        h_dist = token['bbox'][0] - prev['bbox'][2]
        
        # Tolerance symbols often have slightly larger gaps
        effective_gap = gap_x
        if any(s in token['text'] for s in ['±', '+', '-', 'Ø']):
            effective_gap = gap_x * 1.5

        if same_line and h_dist <= effective_gap:
            current_group.append(token)
        else:
            groups.append(current_group)
            current_group = [token]

    if current_group:
        groups.append(current_group)

    # Process groups into candidate objects
    candidates = []
    for g in groups:
        # Join with space to keep tokens distinct but parsable
        combined_text = " ".join([t['text'] for t in g])
        combined_text = combined_text.replace('± ', '±').replace(' +', '+').replace(' -', '-')
        
        x0 = min(t['bbox'][0] for t in g)
        y0 = min(t['bbox'][1] for t in g)
        x1 = max(t['bbox'][2] for t in g)
        y1 = max(t['bbox'][3] for t in g)
        
        candidates.append({
            'text': combined_text,
            'bbox': (x0, y0, x1, y1),
            'tokens': g
        })
        
    return candidates
