def group_tokens(tokens: list, gap_x: int = 50, gap_y: int = 20) -> list:
    """
    Groups individual text tokens into candidate dimension strings based on spatial proximity.
    Supports both horizontal and vertical grouping.
    """
    if not tokens:
        return []

    # --- Phase 1: Horizontal Line Grouping ---
    lines = []
    # Sort initially by center Y
    sorted_y = sorted(tokens, key=lambda x: (x['bbox'][1] + x['bbox'][3]) / 2)
    
    current_line = [sorted_y[0]] if sorted_y else []
    for i in range(1, len(sorted_y)):
        token = sorted_y[i]
        prev = current_line[-1] # or median of line
        
        y_center_curr = (token['bbox'][1] + token['bbox'][3]) / 2
        y_center_line = sum((t['bbox'][1] + t['bbox'][3]) / 2 for t in current_line) / len(current_line)
        
        if abs(y_center_curr - y_center_line) <= gap_y:
            current_line.append(token)
        else:
            lines.append(current_line)
            current_line = [token]
    if current_line:
        lines.append(current_line)

    h_groups = []
    for line in lines:
        line.sort(key=lambda x: x['bbox'][0])
        current_h = [line[0]]
        for i in range(1, len(line)):
            token = line[i]
            prev = current_h[-1]
            h_dist = token['bbox'][0] - prev['bbox'][2]
            
            # Since sorted by X, h_dist is horizontal gap.
            # Allow some overlap but limit max distance gap_x.
            if h_dist <= gap_x:
                current_h.append(token)
            else:
                h_groups.append(current_h)
                current_h = [token]
        if current_h:
            h_groups.append(current_h)

    # --- Phase 2: Vertical Grouping ---
    cols = []
    sorted_x = sorted(tokens, key=lambda x: (x['bbox'][0] + x['bbox'][2]) / 2)
    
    current_col = [sorted_x[0]] if sorted_x else []
    for i in range(1, len(sorted_x)):
        token = sorted_x[i]
        
        x_center_curr = (token['bbox'][0] + token['bbox'][2]) / 2
        x_center_col = sum((t['bbox'][0] + t['bbox'][2]) / 2 for t in current_col) / len(current_col)
        
        if abs(x_center_curr - x_center_col) <= gap_y * 1.5:
            current_col.append(token)
        else:
            cols.append(current_col)
            current_col = [token]
    if current_col:
        cols.append(current_col)

    v_groups = []
    for col in cols:
        col.sort(key=lambda x: x['bbox'][1])
        current_v = [col[0]]
        for i in range(1, len(col)):
            token = col[i]
            prev = current_v[-1]
            v_dist = token['bbox'][1] - prev['bbox'][3]
            
            if v_dist <= gap_x:
                current_v.append(token)
            else:
                v_groups.append(current_v)
                current_v = [token]
        if current_v:
            v_groups.append(current_v)

    # Combine results and deduplicate
    final_candidates = []
    seen_bboxes = set()

    for g in (h_groups + v_groups):
        if not g: continue
        
        # Merge tokens physically close without space to fix docTR fragmentation
        combined_text = ""
        is_vertical_group = (g in v_groups and len(g) > 1 and abs(g[0]['bbox'][0] - g[-1]['bbox'][0]) < gap_y)
        
        for i, t in enumerate(g):
            if i == 0:
                combined_text = t['text']
            else:
                prev = g[i-1]
                if is_vertical_group:
                    dist = t['bbox'][1] - prev['bbox'][3]
                else:
                    dist = t['bbox'][0] - prev['bbox'][2]
                
                # Join tightly packed fragments without spaces
                if dist < 8:
                    combined_text += t['text']
                else:
                    combined_text += " " + t['text']
                    
        # Minor normalization
        combined_text = combined_text.replace('± ', '±').replace(' +', '+').replace(' -', '-')
        
        x0 = min(t['bbox'][0] for t in g)
        y0 = min(t['bbox'][1] for t in g)
        x1 = max(t['bbox'][2] for t in g)
        y1 = max(t['bbox'][3] for t in g)
        
        bbox = (x0, y0, x1, y1)
        if bbox not in seen_bboxes:
            final_candidates.append({
                'text': combined_text,
                'bbox': bbox,
                'tokens': g
            })
            seen_bboxes.add(bbox)
        
    return final_candidates
