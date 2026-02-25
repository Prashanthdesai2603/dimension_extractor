def validate_dimensions(candidates: list, img_width: int, img_height: int) -> tuple:
    """
    Validates candidate dimensions by filtering out noise based on spatial location.
    Typically removes title block entries and other non-dimension text.

    Args:
        candidates: List of candidate dicts with 'text' and 'bbox'.
        img_width: Width of the image.
        img_height: Height of the image.

    Returns:
        Tuple of (valid_dimensions, noise_count)
    """
    valid_dimensions = []
    noise_count = 0

    # Define title block region (bottom 25% and right 40% of the image)
    title_block_y_threshold = img_height * 0.75
    title_block_x_threshold = img_width * 0.6

    for cand in candidates:
        bbox = cand['bbox']
        x0, y0, x1, y1 = bbox

        # Check if bbox is in title block area
        if y0 > title_block_y_threshold and x0 > title_block_x_threshold:
            noise_count += 1
            continue

        # Additional filters can be added here, e.g., size checks
        bbox_width = x1 - x0
        bbox_height = y1 - y0

        # Skip very small or very large bboxes (likely noise)
        if bbox_width < 10 or bbox_height < 5 or bbox_width > img_width * 0.5 or bbox_height > img_height * 0.5:
            noise_count += 1
            continue

        # If passes all filters, it's valid
        valid_dimensions.append(cand)

    return valid_dimensions, noise_count